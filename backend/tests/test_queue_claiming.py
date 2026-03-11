from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.models.evaluation_job import EvaluationJob
from app.models.submission import Submission
from app.models.worker_heartbeat import WorkerHeartbeat
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


def test_recover_stuck_running_job_retries_submission(monkeypatch: pytest.MonkeyPatch):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setattr(queue, "_stuck_job_recovery_seconds", lambda: 10.0)

        now = datetime.now(timezone.utc)
        async with session_factory() as db:
            submission = Submission(
                challenge_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                status="running",
                code="print('retry')",
                entrypoint="main.py",
            )
            db.add(submission)
            await db.flush()

            job = EvaluationJob(
                submission_id=submission.id,
                status="running",
                attempts=1,
                max_attempts=3,
                started_at=now - timedelta(seconds=30),
                available_at=now - timedelta(seconds=30),
            )
            db.add(job)
            await db.commit()

            recovered = await queue._recover_stuck_jobs(db)
            assert recovered == 1

        async with session_factory() as db:
            saved_submission = await db.get(Submission, submission.id)
            saved_job = await db.get(EvaluationJob, job.id)
            assert saved_submission is not None
            assert saved_job is not None
            assert saved_submission.status == "failed"
            assert saved_job.status == "retry"
            assert saved_job.finished_at is None
            assert saved_job.available_at is not None
            assert saved_job.started_at is not None
            assert saved_job.available_at > saved_job.started_at
            assert saved_job.last_error is not None
            assert "Recovered stuck evaluation job" in saved_job.last_error

        await engine.dispose()

    asyncio.run(_run())


def test_recover_stuck_running_job_finalizes_completed_submission(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setattr(queue, "_stuck_job_recovery_seconds", lambda: 10.0)

        completed_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        async with session_factory() as db:
            submission = Submission(
                challenge_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                status="completed",
                code="print('done')",
                entrypoint="main.py",
                completed_at=completed_at,
            )
            db.add(submission)
            await db.flush()

            job = EvaluationJob(
                submission_id=submission.id,
                status="running",
                attempts=1,
                max_attempts=3,
                started_at=completed_at - timedelta(seconds=30),
            )
            db.add(job)
            await db.commit()

            recovered = await queue._recover_stuck_jobs(db)
            assert recovered == 1

        async with session_factory() as db:
            saved_submission = await db.get(Submission, submission.id)
            saved_job = await db.get(EvaluationJob, job.id)
            assert saved_submission is not None
            assert saved_job is not None
            assert saved_job.status == "completed"
            assert saved_job.finished_at is not None
            assert saved_job.finished_at == saved_submission.completed_at
            assert saved_job.last_error is None

        await engine.dispose()

    asyncio.run(_run())


def test_run_job_times_out_and_retries(monkeypatch: pytest.MonkeyPatch):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setattr(queue, "_evaluation_job_timeout_seconds", lambda: 0.01)

        async def fake_run_evaluation_pipeline(submission_id: str) -> bool:
            await asyncio.sleep(0.05)
            return True

        monkeypatch.setattr(queue, "run_evaluation_pipeline", fake_run_evaluation_pipeline)

        async with session_factory() as db:
            submission = Submission(
                challenge_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                status="running",
                code="print('timeout')",
                entrypoint="main.py",
            )
            db.add(submission)
            await db.flush()

            job = EvaluationJob(
                submission_id=submission.id,
                status="running",
                attempts=1,
                max_attempts=3,
                started_at=datetime.now(timezone.utc),
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

            await queue._run_job(db, job)

        async with session_factory() as db:
            saved_job = await db.get(EvaluationJob, job.id)
            assert saved_job is not None
            assert saved_job.status == "retry"
            assert saved_job.finished_at is None
            assert saved_job.available_at is not None
            assert saved_job.last_error is not None
            assert "Evaluation timed out after" in saved_job.last_error

        await engine.dispose()

    asyncio.run(_run())


def test_write_worker_heartbeat_inserts_and_updates(monkeypatch: pytest.MonkeyPatch):
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        monkeypatch.setattr(queue, "async_session_factory", session_factory)

        worker_state = queue._WorkerState(
            worker_id="worker-a",
            hostname="host-a",
            status="idle",
        )
        await queue._write_worker_heartbeat(worker_state)

        async with session_factory() as db:
            heartbeat = await db.get(WorkerHeartbeat, "worker-a")
            assert heartbeat is not None
            assert heartbeat.hostname == "host-a"
            assert heartbeat.status == "idle"
            assert heartbeat.current_job_id is None

        worker_state.status = "running"
        worker_state.current_job_id = str(uuid.uuid4())
        worker_state.last_error = "still healthy"
        await queue._write_worker_heartbeat(worker_state)

        async with session_factory() as db:
            heartbeat = await db.get(WorkerHeartbeat, "worker-a")
            assert heartbeat is not None
            assert heartbeat.status == "running"
            assert heartbeat.current_job_id == worker_state.current_job_id
            assert heartbeat.last_error == "still healthy"

        await engine.dispose()

    asyncio.run(_run())
