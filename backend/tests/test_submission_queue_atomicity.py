from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
import app.models  # noqa: F401
from app.models.challenge import Challenge
from app.models.evaluation_job import EvaluationJob
from app.models.submission import Submission
from app.models.user import User
from app.workers.queue import enqueue_evaluation_job


def test_submission_and_job_can_commit_together():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as db:
            user = User(
                email="atomic@example.com",
                username="atomic",
                password_hash="hashed",
            )
            challenge = Challenge(
                slug="atomic-challenge",
                title="Atomic Challenge",
                description="Test",
                category="test",
                config={},
            )
            db.add_all([user, challenge])
            await db.flush()

            submission = Submission(
                challenge_id=challenge.id,
                user_id=user.id,
                code="print('ok')",
                entrypoint="main.py",
            )
            db.add(submission)
            await db.flush()
            job = await enqueue_evaluation_job(db, submission.id, commit=False)
            await db.commit()

            assert submission.id is not None
            assert job.id is not None

        async with session_factory() as db:
            saved_submission = await db.get(Submission, submission.id)
            saved_job = await db.get(EvaluationJob, job.id)
            assert saved_submission is not None
            assert saved_job is not None
            assert saved_job.submission_id == saved_submission.id

        await engine.dispose()

    asyncio.run(_run())


def test_rollback_removes_submission_and_job_when_committed_together():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        submission_id: uuid.UUID | None = None
        async with session_factory() as db:
            user = User(
                email="rollback@example.com",
                username="rollback",
                password_hash="hashed",
            )
            challenge = Challenge(
                slug="rollback-challenge",
                title="Rollback Challenge",
                description="Test",
                category="test",
                config={},
            )
            db.add_all([user, challenge])
            await db.flush()

            submission = Submission(
                challenge_id=challenge.id,
                user_id=user.id,
                code="print('rollback')",
                entrypoint="main.py",
            )
            db.add(submission)
            await db.flush()
            submission_id = submission.id
            await enqueue_evaluation_job(db, submission.id, commit=False)
            await db.rollback()

        async with session_factory() as db:
            saved_submission = await db.get(Submission, submission_id)
            jobs = await db.execute(
                select(EvaluationJob).where(EvaluationJob.submission_id == submission_id)
            )
            assert saved_submission is None
            assert jobs.scalar_one_or_none() is None

        await engine.dispose()

    asyncio.run(_run())
