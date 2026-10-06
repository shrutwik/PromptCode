"""Persistent leased interview jobs; stale workers cannot publish their results."""
from __future__ import annotations

import asyncio
import secrets
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
from sqlalchemy import select, update

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.interview_grading import InterviewGradingJob
from app.models.interview_session import InterviewEvaluation, InterviewSession
from app.services.interview.grading import _digest


async def enqueue_grading_job(db, session, snapshot):
    existing = (await db.execute(select(InterviewGradingJob).where(
        InterviewGradingJob.session_id == session.id))).scalar_one_or_none()
    if existing:
        if existing.source_digest != snapshot.source_digest:
            raise ValueError("Submission already bound to different source")
        return existing
    # The durable job stores the provider-neutral object key, never a host path:
    # a different container must be able to hydrate the source from the key alone.
    from app.services.interview.object_store import submission_prefix
    object_key = getattr(snapshot, "object_key", None) or submission_prefix(
        str(session.id), snapshot.source_digest)
    job = InterviewGradingJob(session_id=session.id, source_digest=snapshot.source_digest,
        snapshot_path=str(snapshot.source_path), snapshot_key=object_key,
        snapshot_manifest={"files": snapshot.manifest},
        challenge_slug=session.challenge_slug, challenge_version=session.challenge_version,
        status="queued", attempts=0, max_attempts=3, available_at=datetime.now(timezone.utc))
    db.add(job)
    await db.flush()
    return job


async def claim_next_job(db):
    now = datetime.now(timezone.utc)
    expired = ((InterviewGradingJob.status == "running")
               & (InterviewGradingJob.lease_expires_at.is_not(None))
               & (InterviewGradingJob.lease_expires_at <= now))
    await db.execute(update(InterviewGradingJob).execution_options(synchronize_session="fetch").where(expired).values(
        status="queued", lease_token=None, lease_expires_at=None,
        available_at=now, last_error="Worker lease expired"))
    exhausted = ((InterviewGradingJob.status == "queued")
                 & (InterviewGradingJob.attempts >= InterviewGradingJob.max_attempts))
    await db.execute(update(InterviewGradingJob).execution_options(synchronize_session="fetch").where(
        exhausted).values(
            status="failed", finished_at=now, last_error="Grading retry limit reached"))
    candidate = (await db.execute(select(InterviewGradingJob.id).where(
        InterviewGradingJob.status == "queued", InterviewGradingJob.available_at <= now,
        InterviewGradingJob.attempts < InterviewGradingJob.max_attempts)
        .order_by(InterviewGradingJob.created_at).limit(1))).scalar_one_or_none()
    if candidate is None:
        await db.commit()
        return None
    token = secrets.token_hex(32)
    claimed = (await db.execute(update(InterviewGradingJob).execution_options(synchronize_session="fetch").where(
        InterviewGradingJob.id == candidate, InterviewGradingJob.status == "queued",
        InterviewGradingJob.available_at <= now,
        InterviewGradingJob.attempts < InterviewGradingJob.max_attempts).values(
            status="running", lease_token=token,
            lease_expires_at=now + timedelta(seconds=_lease_seconds()),
            started_at=now, attempts=InterviewGradingJob.attempts + 1)
        .returning(InterviewGradingJob.id))).scalar_one_or_none()
    await db.commit()
    if claimed is None:
        return None
    return await db.get(InterviewGradingJob, claimed, populate_existing=True)


def _lease_seconds() -> float:
    """Lease lifetime for one grading attempt.

    Must outlast the longest bounded attempt (per-case probes plus the durable
    retry window) or a slow-but-successful job is reclaimed mid-flight and its
    result discarded. Bounded so a crashed worker is still recovered promptly.
    """
    timeout = float(get_settings().grading_job_timeout_seconds)
    return min(max(timeout * 2.0, timeout + 120.0), timeout * 4.0)


@contextmanager
def _resolved_source(job):
    """Yield a verified local copy of the immutable submission.

    Thin wrapper over the shared resolver so the worker, staff review, appeal and
    retry paths all prove submission identity the same way.
    """
    from app.services.interview.workspace_store import verified_job_source

    with verified_job_source(job) as source:
        yield source


def _in_process_execution(settings) -> bool:
    """Whether the trusted evaluator runs inside this worker.

    A broker deployment sets ``execution_broker_url``; a Modal deployment sets
    ``execution_backend=modal`` and has neither a broker nor a sandbox executor
    URL, so selecting on the broker URL alone would fail every claimed job.
    """
    if getattr(settings, "execution_broker_url", ""):
        return True
    return str(getattr(settings, "execution_backend", "")).strip().lower() == "modal"


async def _execute(job):
    settings = get_settings()
    if _in_process_execution(settings):
        import asyncio

        from app.services.interview.calibration import challenge_version_for
        from app.services.interview.trusted_evaluator import evaluate_snapshot
        if job.challenge_version != challenge_version_for(job.challenge_slug):
            raise ValueError("Challenge evaluation version changed")
        with _resolved_source(job) as source:
            return await asyncio.to_thread(evaluate_snapshot, source, session_id=str(job.session_id),
                job_id=str(job.id), challenge_slug=job.challenge_slug, source_digest=job.source_digest,
                signing_key=settings.grading_signing_key, challenge_version=job.challenge_version,
                lease_token=job.lease_token)
    if not settings.grading_signing_key or not settings.sandbox_executor_url or not settings.sandbox_executor_token:
        raise ValueError("Trusted grading executor is not configured")
    async with httpx.AsyncClient(timeout=settings.grading_job_timeout_seconds) as client:
        response = await client.post(settings.sandbox_executor_url.rstrip("/") + "/v1/interview/grade",
            headers={"Authorization": "Bearer " + settings.sandbox_executor_token},
            json={"job_id": str(job.id), "lease_token": job.lease_token})
    response.raise_for_status()
    envelope = response.json()
    from app.services.interview.trusted_evaluator import verify_result
    verify_result(envelope, signing_key=settings.grading_signing_key,
                  session_id=str(job.session_id), job_id=str(job.id),
                  challenge_slug=job.challenge_slug, source_digest=job.source_digest,
                  challenge_version=job.challenge_version, lease_token=job.lease_token)
    return envelope


async def finish_job(db, job, envelope):
    from app.services.interview.trusted_evaluator import verify_result
    verify_result(envelope, signing_key=get_settings().grading_signing_key,
                  session_id=str(job.session_id), job_id=str(job.id),
                  challenge_slug=job.challenge_slug, source_digest=job.source_digest,
                  challenge_version=job.challenge_version, lease_token=job.lease_token)
    now = datetime.now(timezone.utc)
    await db.execute(select(InterviewSession).where(
        InterviewSession.id == job.session_id).with_for_update().execution_options(populate_existing=True))
    applied = (await db.execute(update(InterviewGradingJob).execution_options(synchronize_session="fetch").where(
        InterviewGradingJob.id == job.id, InterviewGradingJob.status == "running",
        InterviewGradingJob.lease_token == job.lease_token,
        InterviewGradingJob.lease_expires_at > now).values(
            status="completed", result=envelope, finished_at=now, last_error=None,
            lease_expires_at=None).returning(InterviewGradingJob.id))).scalar_one_or_none()
    if applied is None:
        await db.rollback()
        return False
    evaluation = (await db.execute(select(InterviewEvaluation).where(
        InterviewEvaluation.session_id == job.session_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one()
    metrics = dict(evaluation.metrics or {})
    assessment = dict(metrics["assessment"])
    packet = dict(assessment["packet"])
    packet["evidence"] = [e for e in packet["evidence"] if e["kind"] != "external_evaluation"]
    packet["evidence"].append({"id": "external:" + str(job.id), "kind": "external_evaluation",
                               "payload_digest": _digest(envelope["payload"])})
    assessment.update(packet=packet, packet_digest=_digest(packet), execution_status="completed")
    metrics["assessment"] = assessment
    evaluation.metrics = metrics
    await db.commit()
    return True


async def fail_job(db, job):
    now = datetime.now(timezone.utc)
    await db.execute(update(InterviewGradingJob).execution_options(synchronize_session="fetch").where(
        InterviewGradingJob.id == job.id, InterviewGradingJob.status == "running",
        InterviewGradingJob.lease_token == job.lease_token).values(
            status="failed" if job.attempts >= job.max_attempts else "queued",
            available_at=now + timedelta(seconds=min(60, 5 * 2 ** job.attempts)),
            finished_at=now if job.attempts >= job.max_attempts else None,
            last_error="Trusted evaluation unavailable; no grade was issued",
            lease_token=None, lease_expires_at=None))
    await db.commit()


async def process_one_grading_job():
    async with async_session_factory() as db:
        job = await claim_next_job(db)
        if job is None:
            return False
        # Rollback expires ORM state; retain only the immutable lease identity.
        job = SimpleNamespace(**{name: getattr(job, name, None) for name in (
            "id", "session_id", "challenge_slug", "challenge_version", "source_digest", "lease_token",
            "attempts", "max_attempts", "snapshot_path", "snapshot_key", "snapshot_manifest")})
        try:
            envelope = await asyncio.wait_for(_execute(job), get_settings().grading_job_timeout_seconds)
            await finish_job(db, job, envelope)
        except asyncio.CancelledError:
            # Leave durable lease for recovery; never mark a cancelled attempt correct.
            raise
        except Exception:
            await db.rollback()
            await fail_job(db, job)
        return True
