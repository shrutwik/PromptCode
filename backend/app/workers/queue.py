from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.evaluation_job import EvaluationJob
from app.models.submission import Submission
from app.workers.evaluate import run_evaluation_pipeline

logger = logging.getLogger(__name__)


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
    logger.info("Evaluation queue worker started")
    while True:
        try:
            processed = await _process_one_available_job()
            if not processed:
                await asyncio.sleep(poll_interval_seconds)
        except Exception:  # pragma: no cover
            logger.exception("Queue worker iteration failed")
            await asyncio.sleep(poll_interval_seconds)


async def _process_one_available_job() -> bool:
    async with async_session_factory() as db:
        await _recover_stuck_jobs(db)
        job = await _claim_next_job(db)
        if not job:
            return False
        await _run_job(db, job)
        return True


def _queue_query() -> Select[tuple[EvaluationJob]]:
    now = datetime.now(timezone.utc)
    return (
        select(EvaluationJob)
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
    job = result.scalar_one_or_none()
    if not job:
        return None
    return await _claim_job_by_id(db, job.id)


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
