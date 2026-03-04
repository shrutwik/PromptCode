from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
import app.models  # noqa: F401
from app.models.evaluation_job import EvaluationJob
from app.workers import queue


def test_process_job_claims_once(monkeypatch: pytest.MonkeyPatch):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setattr(queue, "async_session_factory", session_factory)

        submission_id = uuid.uuid4()
        async with session_factory() as db:
            job = EvaluationJob(submission_id=submission_id, status="queued")
            db.add(job)
            await db.commit()
            await db.refresh(job)
            job_id = str(job.id)

        calls = {"count": 0}

        async def fake_run_job(db, job):
            calls["count"] += 1
            job.status = "completed"
            await db.commit()

        monkeypatch.setattr(queue, "_run_job", fake_run_job)

        await queue.process_job(job_id)
        await queue.process_job(job_id)

        assert calls["count"] == 1

        async with session_factory() as db:
            saved = await db.get(EvaluationJob, uuid.UUID(job_id))
            assert saved is not None
            assert saved.status == "completed"

        await engine.dispose()

    asyncio.run(_run())


def test_claim_job_by_id_ignores_non_queued(monkeypatch: pytest.MonkeyPatch):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        submission_id = uuid.uuid4()
        async with session_factory() as db:
            job = EvaluationJob(submission_id=submission_id, status="running")
            db.add(job)
            await db.commit()
            await db.refresh(job)
            claimed = await queue._claim_job_by_id(db, job.id)
            assert claimed is None

        await engine.dispose()

    asyncio.run(_run())
