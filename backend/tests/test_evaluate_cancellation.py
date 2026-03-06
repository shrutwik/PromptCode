from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
import app.models  # noqa: F401
from app.models.submission import Submission
from app.workers import evaluate as evaluate_worker


def test_run_evaluation_pipeline_marks_submission_failed_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setattr(evaluate_worker, "async_session_factory", session_factory)

        async with session_factory() as db:
            submission = Submission(
                challenge_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                status="running",
                code="print('cancelled')",
                entrypoint="main.py",
            )
            db.add(submission)
            await db.commit()
            await db.refresh(submission)

        async def fake_evaluate(db, submission_id: str) -> None:
            raise asyncio.CancelledError()

        monkeypatch.setattr(evaluate_worker, "_evaluate", fake_evaluate)

        with pytest.raises(asyncio.CancelledError):
            await evaluate_worker.run_evaluation_pipeline(str(submission.id))

        async with session_factory() as db:
            saved_submission = await db.get(Submission, submission.id)
            assert saved_submission is not None
            assert saved_submission.status == "failed"

        await engine.dispose()

    asyncio.run(_run())
