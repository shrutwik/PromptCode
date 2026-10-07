"""Disposable PostgreSQL verifies real grading migrations, leases and row locking."""
import asyncio
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_grading_snapshots_jobs import signed_result

from app.models.interview_grading import InterviewGradingJob
from app.models.interview_session import InterviewEvaluation, InterviewSession
from app.models.user import User
from app.services.interview.grading import pending_assessment, revise_defense
from app.workers import interview_grading as jobs

pytestmark = pytest.mark.skipif(os.getenv("PROMPTCODE_AUDIT_DOCKER") != "1",
                               reason="Disposable live PostgreSQL opt-in required")


@pytest.fixture(scope="module")
def migrated_postgres():
    import docker
    client = docker.from_env(timeout=10)
    container = None
    try:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        container = client.containers.run("postgres:16.11-alpine3.23", detach=True,
            environment={"POSTGRES_PASSWORD": "test-only-grading-password", "POSTGRES_DB": "grading_audit"},
            ports={"5432/tcp": ("127.0.0.1", port)},
            tmpfs={"/var/lib/postgresql/data": "rw,nosuid,size=128m"},
            mem_limit="256m", nano_cpus=1000000000, pids_limit=64,
            labels={"promptcode.audit": "test-only-grading"})
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if container.exec_run(["pg_isready", "-h", "127.0.0.1", "-U", "postgres"]).exit_code == 0:
                break
            time.sleep(.2)
        else:
            raise AssertionError("Disposable PostgreSQL startup failed")
        url = f"postgresql+asyncpg://postgres:test-only-grading-password@127.0.0.1:{port}/grading_audit"
        backend = Path(__file__).resolve().parents[1]
        migration = subprocess.run([sys.executable, "-m", "alembic", "-c", str(backend / "alembic.ini"), "upgrade", "head"],
            cwd=backend, env=dict(os.environ, PROMPTCODE_DATABASE_URL=url, PROMPTCODE_DATABASE_SSL_REQUIRE="false"),
            timeout=30, capture_output=True)
        assert migration.returncode == 0, migration.stderr.decode()[-2000:]
        yield url
    finally:
        if container is not None:
            container.remove(force=True, v=True)
        client.close()


async def setup(url, username):
    engine = create_async_engine(url, pool_size=8, max_overflow=0,
                                 connect_args={"ssl": False, "command_timeout": 10})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email=username + "@test.example", username=username, password_hash="test-only")
        db.add(user)
        await db.flush()
        session = InterviewSession(user_id=user.id, owner_token="test-owned", challenge_slug="order-hold-reason",
                                   challenge_version="1", workspace_path="/unused")
        db.add(session)
        await db.flush()
        evaluation = InterviewEvaluation(session_id=session.id, metrics={"assessment": pending_assessment(
            session_id=str(session.id), challenge_slug=session.challenge_slug, challenge_version="1", events=[], test_summary={})})
        db.add(evaluation)
        job = await jobs.enqueue_grading_job(db, session, SimpleNamespace(
            source_digest="a" * 64, source_path=Path("/frozen/source"), manifest=[]))
        await db.commit()
    return engine, factory, job.id, session.id


def identity(job):
    return SimpleNamespace(**{key: getattr(job, key) for key in
        ("id", "session_id", "challenge_slug", "challenge_version", "source_digest", "lease_token", "attempts", "max_attempts")})


def test_live_postgres_atomic_claim_and_stale_result_rejection(migrated_postgres, monkeypatch):
    async def exercise():
        engine, factory, jid, _ = await setup(migrated_postgres, "lease-audit")
        try:
            async def claim():
                async with factory() as db:
                    job = await jobs.claim_next_job(db)
                    return identity(job) if job else None
            claims = await asyncio.gather(*(claim() for _ in range(6)))
            assert sum(item is not None for item in claims) == 1
            first = next(item for item in claims if item)
            assert first.attempts == 1 and first.id == jid
            async with factory() as db:
                await db.execute(update(InterviewGradingJob).where(InterviewGradingJob.id == jid).values(
                    lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
                await db.commit()
            second = await claim()
            assert second.attempts == 2 and second.lease_token != first.lease_token
            async with factory() as db:
                assert await jobs.finish_job(db, first, signed_result(first)) is False
            async with factory() as db:
                current = await db.get(InterviewGradingJob, jid)
                assert current.status == "running" and current.result is None
                assert current.lease_token == second.lease_token
                await jobs.fail_job(db, second)
                await db.execute(update(InterviewGradingJob).where(InterviewGradingJob.id == jid).values(
                    status="failed", available_at=datetime.now(timezone.utc)))
                await db.commit()
        finally:
            await engine.dispose()
    monkeypatch.setattr(jobs, "get_settings", lambda: SimpleNamespace(
        grading_signing_key="k" * 32, grading_job_timeout_seconds=600))
    asyncio.run(exercise())


def test_live_postgres_finish_waits_for_defense_lock_and_preserves_answer(migrated_postgres, monkeypatch):
    async def exercise():
        engine, factory, jid, sid = await setup(migrated_postgres, "defense-lock-audit")
        try:
            async with factory() as db:
                job = identity(await jobs.claim_next_job(db))
            started = asyncio.Event()
            async def finish():
                async with factory() as db:
                    started.set()
                    return await jobs.finish_job(db, job, signed_result(job))
            async with factory() as defense:
                await defense.execute(select(InterviewSession).where(InterviewSession.id == sid).with_for_update())
                evaluation = (await defense.execute(select(InterviewEvaluation).where(
                    InterviewEvaluation.session_id == sid).with_for_update())).scalar_one()
                task = asyncio.create_task(finish())
                await started.wait()
                await asyncio.sleep(.1)
                assert not task.done(), "Worker must wait for candidate defense transaction"
                answers = {"0": "The submitted fix addresses the identified root cause."}
                metrics = dict(evaluation.metrics)
                metrics["defend_answers"] = answers
                metrics["assessment"] = revise_defense(metrics["assessment"], answers)
                evaluation.metrics = metrics
                await defense.commit()
            assert await asyncio.wait_for(task, 5) is True
            async with factory() as db:
                final = (await db.execute(select(InterviewEvaluation).where(InterviewEvaluation.session_id == sid))).scalar_one()
                assert final.metrics["defend_answers"] == answers
                evidence = final.metrics["assessment"]["packet"]["evidence"]
                assert any(item["id"] == "defend:0" for item in evidence)
                assert any(item["kind"] == "external_evaluation" for item in evidence)
                assert (await db.get(InterviewGradingJob, jid)).status == "completed"
                tables = set((await db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))).scalars())
                assert {"interview_grading_jobs", "interview_grade_reviews", "interview_grade_appeals", "interview_appeal_decisions"} <= tables
        finally:
            await engine.dispose()
    monkeypatch.setattr(jobs, "get_settings", lambda: SimpleNamespace(
        grading_signing_key="k" * 32, grading_job_timeout_seconds=600))
    asyncio.run(exercise())


def test_live_postgres_concurrent_grading_admission_has_exact_three_slots(migrated_postgres):
    async def exercise():
        from fastapi import HTTPException

        from app.services.interview.grading_admission import require_grading_capacity
        engine = create_async_engine(migrated_postgres, pool_size=8, max_overflow=0,
                                     connect_args={"ssl": False, "command_timeout": 10})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as db:
                owner = User(email="admission@test.example", username="admission", password_hash="test-only")
                db.add(owner)
                await db.flush()
                sessions = [InterviewSession(user_id=owner.id, owner_token="test-owned",
                    challenge_slug="order-hold-reason", challenge_version="1", workspace_path="/unused")
                    for _ in range(4)]
                db.add_all(sessions)
                await db.commit()
                ids = [session.id for session in sessions]
                owner_id = owner.id
            async def admit(session_id):
                async with factory() as db:
                    session = (await db.execute(select(InterviewSession).where(
                        InterviewSession.id == session_id).with_for_update())).scalar_one()
                    try:
                        await require_grading_capacity(db, owner_id)
                    except HTTPException as exc:
                        assert exc.status_code == 429 and exc.headers["Retry-After"] == "60"
                        await db.rollback()
                        return False
                    await jobs.enqueue_grading_job(db, session, SimpleNamespace(
                        source_digest="a" * 64, source_path=Path("/unused/source"), manifest=[]))
                    await db.commit()
                    return True
            outcomes = await asyncio.gather(*(admit(session_id) for session_id in ids))
            assert sum(outcomes) == 3
            assert outcomes.count(False) == 1
            async with factory() as db:
                admitted = (await db.execute(select(InterviewGradingJob).where(
                    InterviewGradingJob.session_id.in_(ids)))).scalars().all()
                assert len(admitted) == 3
                assert all(job.status == "queued" for job in admitted)
        finally:
            await engine.dispose()
    asyncio.run(exercise())
