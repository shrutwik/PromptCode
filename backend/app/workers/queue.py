from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.auth_rate_limit import AuthRateLimitEvent
from app.models.evaluation_job import EvaluationJob
from app.models.revoked_token import RevokedToken
from app.models.submission import Submission
from app.models.worker_heartbeat import WorkerHeartbeat
from app.workers.evaluate import run_evaluation_pipeline

logger = logging.getLogger(__name__)


@dataclass
class _WorkerState:
    worker_id: str
    hostname: str
    status: str = "idle"
    current_job_id: str | None = None
    last_error: str | None = None


async def enqueue_evaluation_job(
    db: AsyncSession,
    submission_id: uuid.UUID,
    *,
    max_attempts: int = 3,
    commit: bool = True,
) -> EvaluationJob:
    job = EvaluationJob(
        submission_id=submission_id,
        status="queued",
        max_attempts=max_attempts,
    )
    db.add(job)
    if commit:
        await db.commit()
        await db.refresh(job)
    else:
        await db.flush()
    return job


async def process_job(job_id: str) -> None:
    """Process one queued job by id. Safe to call from BackgroundTasks."""
    async with async_session_factory() as db:
        job_uuid = uuid.UUID(job_id)
        await _recover_stuck_jobs(db, job_id=job_uuid)
        job = await _claim_job_by_id(db, job_uuid)
        if not job:
            return
        await _run_job(db, job)


async def worker_loop(*, poll_interval_seconds: float = 1.0) -> None:
    """Queue worker loop for persistent processing outside request lifecycle."""
    worker_state = _WorkerState(
        worker_id=_worker_identity(),
        hostname=socket.gethostname(),
    )
    heartbeat_task = asyncio.create_task(_heartbeat_loop(worker_state))
    cleanup_task = asyncio.create_task(_rate_limit_cleanup_loop())
    logger.info("Evaluation queue worker started", extra={"worker_id": worker_state.worker_id})
    _consecutive_errors = 0
    _MAX_BACKOFF = 60.0
    try:
        while True:
            try:
                worker_state.last_error = None
                processed = await _process_one_available_job(worker_state=worker_state)
                _consecutive_errors = 0
                if not processed:
                    await asyncio.sleep(poll_interval_seconds)
            except Exception as exc:  # pragma: no cover
                _consecutive_errors += 1
                worker_state.status = "error"
                worker_state.current_job_id = None
                worker_state.last_error = str(exc)[:1500]
                backoff = min(_MAX_BACKOFF, poll_interval_seconds * (2 ** min(_consecutive_errors - 1, 6)))
                logger.exception(
                    "Queue worker iteration failed (consecutive=%d, backoff=%.1fs)",
                    _consecutive_errors,
                    backoff,
                )
                await asyncio.sleep(backoff)
    finally:
        heartbeat_task.cancel()
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
        with suppress(asyncio.CancelledError):
            await cleanup_task


async def _process_one_available_job(
    *,
    worker_state: _WorkerState | None = None,
) -> bool:
    async with async_session_factory() as db:
        await _recover_stuck_jobs(db)
        job = await _claim_next_job(db)
        if not job:
            if worker_state is not None:
                worker_state.status = "idle"
                worker_state.current_job_id = None
            return False
        if worker_state is not None:
            worker_state.status = "running"
            worker_state.current_job_id = str(job.id)
            worker_state.last_error = None
        try:
            await _run_job(db, job)
        finally:
            if worker_state is not None:
                worker_state.status = "idle"
                worker_state.current_job_id = None
        return True


def _queue_query() -> Select[tuple[uuid.UUID]]:
    now = datetime.now(timezone.utc)
    return (
        select(EvaluationJob.id)
        .where(
            EvaluationJob.status.in_(("queued", "retry")),
            EvaluationJob.available_at <= now,
        )
        .with_for_update(skip_locked=True)
        .order_by(EvaluationJob.created_at.asc())
        .limit(1)
    )


async def _claim_next_job(db: AsyncSession) -> EvaluationJob | None:
    result = await db.execute(_queue_query())
    job_id = result.scalar_one_or_none()
    if not job_id:
        return None
    return await _claim_job_by_id(db, job_id)


async def _claim_job_by_id(db: AsyncSession, job_id: uuid.UUID) -> EvaluationJob | None:
    now = datetime.now(timezone.utc)
    claim_stmt = (
        update(EvaluationJob)
        .where(
            EvaluationJob.id == job_id,
            EvaluationJob.status.in_(("queued", "retry")),
            EvaluationJob.available_at <= now,
        )
        .values(
            status="running",
            started_at=now,
            attempts=EvaluationJob.attempts + 1,
        )
        .returning(EvaluationJob.id)
    )
    result = await db.execute(claim_stmt)
    claimed_id = result.scalar_one_or_none()
    if not claimed_id:
        await db.rollback()
        return None
    await db.commit()
    return await db.get(EvaluationJob, claimed_id)


def _evaluation_job_timeout_seconds() -> float:
    configured = float(get_settings().evaluation_job_timeout_seconds or 0)
    return max(60.0, configured)


def _worker_identity() -> str:
    configured = str(get_settings().worker_id or "").strip()
    return configured or socket.gethostname()


def _worker_heartbeat_interval_seconds() -> float:
    configured = float(get_settings().worker_heartbeat_interval_seconds or 0)
    return max(1.0, configured)


def _worker_heartbeat_timeout_seconds() -> float:
    configured = float(get_settings().worker_heartbeat_timeout_seconds or 0)
    return max(_worker_heartbeat_interval_seconds(), configured)


def _stuck_job_recovery_seconds() -> float:
    timeout_seconds = _evaluation_job_timeout_seconds()
    return max(timeout_seconds * 2.0, timeout_seconds + 300.0)


def _retry_backoff_seconds(attempts: int) -> int:
    return min(60, 2 ** max(1, attempts))


def _set_retry_or_failed(job: EvaluationJob, *, now: datetime, last_error: str) -> None:
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.finished_at = now
    else:
        job.status = "retry"
        job.available_at = now + timedelta(seconds=_retry_backoff_seconds(job.attempts))
        job.finished_at = None
    job.last_error = last_error[:1500]


def _stuck_job_error(job: EvaluationJob, *, now: datetime) -> str:
    started_at = job.started_at or now
    elapsed_seconds = max(0, int((now - started_at).total_seconds()))
    return (
        "Recovered stuck evaluation job after "
        f"{elapsed_seconds} seconds in 'running'; retrying cleanly."
    )


async def _recover_stuck_jobs(
    db: AsyncSession,
    *,
    job_id: uuid.UUID | None = None,
) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=_stuck_job_recovery_seconds())
    query = (
        select(EvaluationJob)
        .where(
            EvaluationJob.status == "running",
            EvaluationJob.started_at.is_not(None),
            EvaluationJob.started_at <= cutoff,
        )
        .with_for_update(skip_locked=True)
        .order_by(EvaluationJob.started_at.asc())
    )
    if job_id is not None:
        query = query.where(EvaluationJob.id == job_id)

    result = await db.execute(query)
    jobs = list(result.scalars())
    if not jobs:
        await db.rollback()
        return 0

    recovered = 0
    for job in jobs:
        submission = await db.get(Submission, job.submission_id)
        if submission and submission.status == "completed":
            job.status = "completed"
            job.finished_at = submission.completed_at or now
            job.last_error = None
            recovered += 1
            logger.warning(
                "Recovered orphaned completed evaluation job %s for submission %s",
                job.id,
                job.submission_id,
            )
            continue

        _set_retry_or_failed(job, now=now, last_error=_stuck_job_error(job, now=now))
        if submission and submission.status == "running":
            submission.status = "failed"
        recovered += 1
        logger.warning(
            "Recovered stuck evaluation job %s for submission %s",
            job.id,
            job.submission_id,
        )

    await db.commit()
    return recovered


_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS = 300  # run every 5 minutes
_RATE_LIMIT_EVENT_MAX_AGE_SECONDS = 120  # 2× the 60 s rate-limit window; safe to delete


async def _rate_limit_cleanup_loop() -> None:
    """Periodically delete expired auth_rate_limit_events rows for all keys.

    Per-request cleanup only prunes rows for the requesting key, so rows for
    idle keys accumulate indefinitely.  This loop does a global sweep so the
    table stays bounded regardless of traffic patterns.
    """
    while True:
        await asyncio.sleep(_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS)
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(
                seconds=_RATE_LIMIT_EVENT_MAX_AGE_SECONDS
            )
            async with async_session_factory() as db:
                await db.execute(
                    delete(AuthRateLimitEvent).where(AuthRateLimitEvent.created_at < cutoff)
                )
                now = datetime.now(timezone.utc)
                await db.execute(
                    delete(RevokedToken).where(RevokedToken.expires_at < now)
                )
                await db.commit()
                logger.debug("Rate limit event and revoked token cleanup complete")
        except Exception:  # pragma: no cover
            logger.warning("Rate limit event cleanup failed", exc_info=True)


async def _heartbeat_loop(worker_state: _WorkerState) -> None:
    interval_seconds = _worker_heartbeat_interval_seconds()
    while True:
        try:
            await _write_worker_heartbeat(worker_state)
        except Exception:  # pragma: no cover
            logger.exception("Failed to update worker heartbeat for %s", worker_state.worker_id)
        await asyncio.sleep(interval_seconds)


async def _write_worker_heartbeat(worker_state: _WorkerState) -> None:
    now = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        heartbeat = await db.get(WorkerHeartbeat, worker_state.worker_id)
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(
                worker_id=worker_state.worker_id,
                hostname=worker_state.hostname,
                status=worker_state.status,
                current_job_id=worker_state.current_job_id,
                last_error=(worker_state.last_error or "")[:1500] or None,
                started_at=now,
                last_seen_at=now,
            )
            db.add(heartbeat)
        else:
            heartbeat.hostname = worker_state.hostname
            heartbeat.status = worker_state.status
            heartbeat.current_job_id = worker_state.current_job_id
            heartbeat.last_error = (worker_state.last_error or "")[:1500] or None
            heartbeat.last_seen_at = now
        await db.commit()


async def _run_job(db: AsyncSession, job: EvaluationJob) -> None:
    timeout_seconds = _evaluation_job_timeout_seconds()
    try:
        async with asyncio.timeout(timeout_seconds):
            ok = await run_evaluation_pipeline(str(job.submission_id))
        submission = await db.get(Submission, job.submission_id)
        is_completed = bool(ok and submission and submission.status == "completed")
        if is_completed:
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            job.last_error = None
        else:
            _set_retry_or_failed(
                job,
                now=datetime.now(timezone.utc),
                last_error="Submission evaluation did not complete successfully.",
            )
    except TimeoutError:
        logger.warning(
            "Evaluation job %s timed out after %.0f seconds",
            job.id,
            timeout_seconds,
        )
        _set_retry_or_failed(
            job,
            now=datetime.now(timezone.utc),
            last_error=f"Evaluation timed out after {timeout_seconds:.0f} seconds.",
        )
    except Exception as exc:
        logger.exception("Evaluation job failed: %s", job.id)
        _set_retry_or_failed(
            job,
            now=datetime.now(timezone.utc),
            last_error=str(exc),
        )
    finally:
        await db.commit()
