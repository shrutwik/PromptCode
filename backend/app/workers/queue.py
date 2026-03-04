from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

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
) -> EvaluationJob:
    job = EvaluationJob(
        submission_id=submission_id,
        status="queued",
        max_attempts=max_attempts,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def process_job(job_id: str) -> None:
    """Process one queued job by id. Safe to call from BackgroundTasks."""
    async with async_session_factory() as db:
        job = await db.get(EvaluationJob, uuid.UUID(job_id))
        if not job:
            return
        if job.status not in ("queued", "retry"):
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
        .order_by(EvaluationJob.created_at.asc())
        .limit(1)
    )


async def _claim_next_job(db: AsyncSession) -> EvaluationJob | None:
    result = await db.execute(_queue_query())
    job = result.scalar_one_or_none()
    if not job:
        return None
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.attempts = (job.attempts or 0) + 1
    await db.commit()
    await db.refresh(job)
    return job


async def _run_job(db: AsyncSession, job: EvaluationJob) -> None:
    try:
        ok = await run_evaluation_pipeline(str(job.submission_id))
        submission = await db.get(Submission, job.submission_id)
        is_completed = bool(ok and submission and submission.status == "completed")
        if is_completed:
            job.status = "completed"
            job.finished_at = datetime.now(timezone.utc)
            job.last_error = None
        else:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.finished_at = datetime.now(timezone.utc)
            else:
                job.status = "retry"
                backoff = min(60, 2 ** max(1, job.attempts))
                job.available_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
            job.last_error = "Submission evaluation did not complete successfully."
    except Exception as exc:
        logger.exception("Evaluation job failed: %s", job.id)
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.finished_at = datetime.now(timezone.utc)
        else:
            job.status = "retry"
            backoff = min(60, 2 ** max(1, job.attempts))
            job.available_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
        job.last_error = str(exc)[:1500]
    finally:
        await db.commit()
