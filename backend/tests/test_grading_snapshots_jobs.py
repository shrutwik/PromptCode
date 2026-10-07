import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.interview_grading import InterviewGradingJob
from app.models.interview_session import InterviewEvaluation, InterviewSession
from app.models.user import User
from app.services.interview import snapshot, workspace
from app.services.interview.grading import pending_assessment
from app.workers import interview_grading as jobs


@pytest.fixture
def owned_workspace(tmp_path, monkeypatch):
    sid = str(uuid.uuid4())
    monkeypatch.setattr(snapshot, "workspace_root", lambda: tmp_path)
    monkeypatch.setattr(workspace, "workspace_root", lambda: tmp_path)
    source = tmp_path / sid
    source.mkdir()
    (source / "src").mkdir()
    (source / "src/solution.py").write_text("answer = 42\n")
    (source / "SOLUTION.md").write_text("private answer")
    return sid, source


def test_submission_freezes_exact_bytes_and_rejects_later_writes(owned_workspace):
    sid, source = owned_workspace
    frozen = snapshot.freeze_submission(source, sid)
    assert [row["path"] for row in frozen.manifest] == ["src/solution.py"]
    assert frozen.source_path != source
    assert snapshot.verify_snapshot(frozen.source_path, frozen.source_digest) == frozen.manifest
    with pytest.raises(ValueError, match="frozen"):
        workspace.write_file(source, "src/solution.py", "answer = 0")
    assert snapshot.freeze_submission(source, sid) == frozen
    # Even a direct host mutation of the live workspace cannot change graded bytes.
    (source / "src/solution.py").write_text("answer = 0")
    assert (frozen.source_path / "src/solution.py").read_text() == "answer = 42\n"


def test_snapshot_tampering_and_inventory_changes_detected(owned_workspace):
    sid, source = owned_workspace
    frozen = snapshot.freeze_submission(source, sid)
    file = frozen.source_path / "src/solution.py"
    file.chmod(0o644)
    file.write_text("answer = 0\n")
    with pytest.raises(ValueError, match="integrity"):
        snapshot.verify_snapshot(frozen.source_path, frozen.source_digest)


@pytest.mark.parametrize("kind", ["file", "directory"])
def test_source_symlinks_cannot_escape_into_snapshot(owned_workspace, tmp_path, kind):
    sid, source = owned_workspace
    outside = tmp_path / "private"
    outside.mkdir()
    (outside / "key").write_text("secret")
    (source / "link").symlink_to(outside if kind == "directory" else outside / "key")
    with pytest.raises(ValueError):
        snapshot.freeze_submission(source, sid)
    assert not Path(str(source) + ".submitted").exists()


def test_snapshot_quota_failure_keeps_source_editable(owned_workspace, monkeypatch):
    sid, source = owned_workspace
    monkeypatch.setattr(snapshot, "SOURCE_BYTES", 2)
    with pytest.raises(ValueError, match="quota"):
        snapshot.freeze_submission(source, sid)
    workspace.write_file(source, "src/solution.py", "x")


async def setup_jobs(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "grading.db"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as db:
        user = User(email="grading@example.com", username="grading", password_hash="test")
        db.add(user)
        await db.flush()
        session = InterviewSession(user_id=user.id, owner_token="owned", challenge_slug="order-hold-reason",
                                   workspace_path="/unused", challenge_version="1")
        db.add(session)
        await db.flush()
        assessment = pending_assessment(session_id=str(session.id), challenge_slug=session.challenge_slug,
                                       challenge_version="1", events=[], test_summary={})
        evaluation = InterviewEvaluation(session_id=session.id, metrics={"assessment": assessment})
        db.add(evaluation)
        frozen = SimpleNamespace(source_digest="a" * 64, source_path=Path("/frozen/source"), manifest=[])
        job = await jobs.enqueue_grading_job(db, session, frozen)
        same = await jobs.enqueue_grading_job(db, session, frozen)
        assert same.id == job.id
        await db.commit()
        return engine, factory, job.id


def test_atomic_claims_allow_only_one_worker(tmp_path):
    async def run():
        engine, factory, jid = await setup_jobs(tmp_path)
        try:
            async def claim():
                async with factory() as db:
                    return await jobs.claim_next_job(db)
            claimed = await asyncio.gather(claim(), claim())
            assert sum(job is not None for job in claimed) == 1
            job = next(job for job in claimed if job)
            assert job.id == jid and job.attempts == 1 and len(job.lease_token) == 64
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_expired_lease_recovers_and_exhausted_job_stops(tmp_path):
    async def run():
        engine, factory, jid = await setup_jobs(tmp_path)
        try:
            async with factory() as db:
                first = await jobs.claim_next_job(db)
                old_token = first.lease_token
                await db.execute(update(InterviewGradingJob).where(InterviewGradingJob.id == jid).values(
                    lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
                await db.commit()
            async with factory() as db:
                second = await jobs.claim_next_job(db)
                assert second.attempts == 2 and second.lease_token != old_token
                await jobs.fail_job(db, second)
                await db.execute(update(InterviewGradingJob).where(InterviewGradingJob.id == jid).values(
                    attempts=3, available_at=datetime.now(timezone.utc)))
                await db.commit()
            async with factory() as db:
                assert await jobs.claim_next_job(db) is None
                final = await db.get(InterviewGradingJob, jid)
                assert final.status == "failed" and final.result is None
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_unverified_results_never_complete_job(tmp_path, monkeypatch):
    async def run():
        engine, factory, jid = await setup_jobs(tmp_path)
        try:
            async with factory() as db:
                job = await jobs.claim_next_job(db)
                monkeypatch.setattr(jobs, "get_settings", lambda: SimpleNamespace(grading_signing_key="k" * 32))
                with pytest.raises(ValueError):
                    await jobs.finish_job(db, job, {"payload": {"score_percent": 100}, "signature": "0" * 64})
                await db.rollback()
                assert (await db.get(InterviewGradingJob, jid)).status == "running"
        finally:
            await engine.dispose()
    asyncio.run(run())


def signed_result(job):
    from app.services.interview.trusted_cases import (
        MANUAL_REQUIREMENTS,
        VERSION,
        cases_for,
        inventory_digest,
    )
    from app.services.interview.trusted_evaluator import sign_result
    cases = [{"id": case.id, "weight": case.weight, "passed": True, "error": None}
             for case in cases_for(job.challenge_slug)]
    total = sum(case["weight"] for case in cases)
    return sign_result({"session_id": str(job.session_id), "job_id": str(job.id),
        "challenge_slug": job.challenge_slug, "challenge_version": job.challenge_version,
        "source_digest": job.source_digest, "lease_token": job.lease_token,
        "evaluator_version": VERSION, "inventory_digest": inventory_digest(job.challenge_slug),
        "cases": cases, "earned_weight": total, "total_weight": total, "score_percent": 100.0,
        "complete": True, "manual_requirements": MANUAL_REQUIREMENTS.get(job.challenge_slug, [])},
        signing_key="k" * 32)


def test_successful_result_keeps_final_nonce_and_adds_only_verified_evidence(tmp_path, monkeypatch):
    async def run():
        engine, factory, jid = await setup_jobs(tmp_path)
        try:
            async with factory() as db:
                job = await jobs.claim_next_job(db)
                token = job.lease_token
                monkeypatch.setattr(jobs, "get_settings", lambda: SimpleNamespace(grading_signing_key="k" * 32))
                assert await jobs.finish_job(db, job, signed_result(job)) is True
                completed = await db.get(InterviewGradingJob, jid, populate_existing=True)
                assert completed.status == "completed" and completed.lease_token == token
                assert completed.lease_expires_at is None
                evaluation = (await db.execute(select(InterviewEvaluation))).scalar_one()
                assert evaluation.metrics["assessment"]["total_score"] is None
                assert evaluation.metrics["assessment"]["packet"]["evidence"][-1]["kind"] == "external_evaluation"
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_stale_worker_cannot_publish_after_job_is_reclaimed(tmp_path, monkeypatch):
    async def run():
        engine, factory, jid = await setup_jobs(tmp_path)
        try:
            async with factory() as db:
                first = await jobs.claim_next_job(db)
                stale = SimpleNamespace(**{name: getattr(first, name) for name in (
                    "id", "session_id", "source_digest", "challenge_slug", "challenge_version", "lease_token")})
                envelope = signed_result(stale)
                await db.execute(update(InterviewGradingJob).where(InterviewGradingJob.id == jid).values(
                    lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
                await db.commit()
            async with factory() as db:
                current = await jobs.claim_next_job(db)
                assert current.lease_token != stale.lease_token
                monkeypatch.setattr(jobs, "get_settings", lambda: SimpleNamespace(grading_signing_key="k" * 32))
                assert await jobs.finish_job(db, stale, envelope) is False
                evaluation = (await db.execute(select(InterviewEvaluation))).scalar_one()
                assert not any(e["kind"] == "external_evaluation"
                               for e in evaluation.metrics["assessment"]["packet"]["evidence"])
                persisted = await db.get(InterviewGradingJob, jid)
                assert persisted.status == "running" and persisted.result is None
        finally:
            await engine.dispose()
    asyncio.run(run())
