"""Bound pending grading work before freezing more submitted source."""
from __future__ import annotations
from fastapi import HTTPException
from sqlalchemy import func, select, text
from app.core.config import get_settings
from app.models.user import User
from app.models.interview_session import InterviewSession
from app.models.interview_grading import InterviewGradingJob
from app.models.evaluation_job import EvaluationJob

MAX_PENDING_GRADING_PER_USER = 3

async def require_global_grading_capacity(db) -> None:
    # One transaction-scoped lock serializes admission across API processes and
    # accounts. It remains held until enqueue/retry commits (or rolls back).
    if hasattr(db, 'get_bind') and db.get_bind().dialect.name == 'postgresql':
        await db.execute(text('SELECT pg_advisory_xact_lock(706726164022)'))
    global_pending = (await db.execute(select(func.count(InterviewGradingJob.id))
        .where(InterviewGradingJob.status.in_(('queued', 'running'))))).scalar_one()
    global_pending += (await db.execute(select(func.count(EvaluationJob.id))
        .where(EvaluationJob.status.in_(('queued', 'retry', 'running'))))).scalar_one()
    if global_pending >= get_settings().grading_max_pending_jobs:
        raise HTTPException(429, 'Grading capacity reached. Try again after a submission finishes.',
                            headers={'Retry-After': '60'})


async def require_grading_capacity(db, user_id) -> None:
    """Hold global then owner locks through enqueue/retry and commit.

    Production uses PostgreSQL transaction locks; SQLite is only supported for
    sequential development/tests. Every queue admission uses the same order.
    """
    if user_id is None:
        raise HTTPException(409, 'Grading requires an owned session')
    await require_global_grading_capacity(db)
    owner = (await db.execute(select(User.id).where(User.id == user_id).with_for_update())).scalar_one_or_none()
    if owner is None:
        raise HTTPException(404, 'Session owner not found')
    pending = (await db.execute(select(func.count(InterviewGradingJob.id))
        .join(InterviewSession, InterviewSession.id == InterviewGradingJob.session_id)
        .where(InterviewSession.user_id == user_id,
               InterviewGradingJob.status.in_(('queued','running'))))).scalar_one()
    if pending >= MAX_PENDING_GRADING_PER_USER:
        raise HTTPException(429, 'Three submissions are already waiting for grading. Try again after one finishes.',
                            headers={'Retry-After':'60'})
