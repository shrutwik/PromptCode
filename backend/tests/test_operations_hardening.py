"""Behavior checks for shared quotas, retained source, and durable monitoring."""
import asyncio
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.metrics import operational_metrics
from app.db.base import Base
from app.models.interview_grading import InterviewGradingJob
from app.models.interview_session import InterviewSession
from app.models.user import User
from app.services.interview.cleanup import cleanup_interview_resources
from app.services.interview.grading_admission import require_grading_capacity
from app.services.interview.snapshot import freeze_submission
from app.services.interview.workspace import create_workspace, write_file


@pytest.fixture
def storage_root(tmp_path, monkeypatch):
    root = tmp_path / 'artifacts'
    root.mkdir()
    monkeypatch.setenv('PROMPTCODE_DEBUG', 'true')
    monkeypatch.setenv('PROMPTCODE_INTERVIEW_WORKSPACE_ROOT', str(root))
    monkeypatch.setenv('PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES', '0')
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_cross_session_writes_share_storage_budget(storage_root, monkeypatch):
    monkeypatch.setenv('PROMPTCODE_INTERVIEW_STORAGE_MAX_BYTES', '10')
    get_settings.cache_clear()
    workspaces = [storage_root / str(uuid.uuid4()) for _ in range(2)]
    for workspace in workspaces:
        workspace.mkdir()
    def upload(workspace):
        try:
            write_file(workspace, 'main.py', '123456')
            return True
        except HTTPException as error:
            assert error.status_code == 507
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(upload, workspaces)) == 1
    assert sum(path.stat().st_size for path in storage_root.rglob('main.py')) == 6


def test_freeze_and_creation_fail_before_storage_growth(storage_root, monkeypatch):
    monkeypatch.setenv('PROMPTCODE_INTERVIEW_STORAGE_MAX_BYTES', '6')
    get_settings.cache_clear()
    sid = str(uuid.uuid4())
    workspace = storage_root / sid
    workspace.mkdir()
    (workspace / 'main.py').write_text('123456')
    with pytest.raises(HTTPException) as error:
        freeze_submission(workspace, sid)
    assert error.value.status_code == 507
    assert not (storage_root / '.submitted').exists()
    fresh = str(uuid.uuid4())
    with pytest.raises(HTTPException):
        create_workspace(fresh, 'order-hold-reason')
    assert not (storage_root / fresh).exists()


def test_disk_reserve_rejects_upload_before_write(storage_root, monkeypatch):
    import app.services.interview.workspace_quota as quota
    monkeypatch.setattr(quota.shutil, 'disk_usage', lambda _: type('Disk', (), {'free': 2})())
    workspace = storage_root / str(uuid.uuid4())
    workspace.mkdir()
    with pytest.raises(HTTPException) as error:
        write_file(workspace, 'main.py', '123')
    assert error.value.status_code == 507
    assert not (workspace / 'main.py').exists()


def test_cleanup_preserves_active_and_referenced_history_and_recent_orphans(storage_root, tmp_path):
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///' + str(tmp_path / 'cleanup.db'))
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            async with factory() as db:
                owner = User(email='cleanup@test', username='cleanup', password_hash='unused')
                db.add(owner)
                await db.flush()
                rows = []
                for state in ('active', 'failed', 'expired'):
                    sid = uuid.uuid4()
                    workspace = storage_root / str(sid)
                    workspace.mkdir()
                    (workspace / 'main.py').write_text('retained source')
                    (storage_root / f'{sid}.starter').mkdir()
                    row = InterviewSession(id=sid, user_id=owner.id, owner_token=str(uuid.uuid4()),
                        status=state, challenge_slug='order-hold-reason', challenge_version='1', workspace_path=str(workspace))
                    db.add(row)
                    rows.append(row)
                await db.flush()
                db.add(InterviewGradingJob(session_id=rows[1].id, source_digest='a' * 64,
                    snapshot_path='/immutable/source', challenge_slug='order-hold-reason', challenge_version='1', status='failed'))
                await db.commit()
                recent = storage_root / str(uuid.uuid4())
                old = storage_root / str(uuid.uuid4())
                recent.mkdir()
                old.mkdir()
                os.utime(old, (time.time() - 7200, time.time() - 7200))
                report = await cleanup_interview_resources(db, cleanup_docker=False)
                assert report.workspaces_removed == 1 and report.orphan_dirs_removed == 1
                assert (storage_root / str(rows[0].id)).exists()
                assert (storage_root / str(rows[1].id)).exists()
                assert not (storage_root / str(rows[2].id)).exists()
                assert recent.exists() and not old.exists()
        finally:
            await engine.dispose()
    asyncio.run(check())


def test_grading_metrics_include_stale_jobs_without_source_or_error(storage_root, tmp_path):
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///' + str(tmp_path / 'metrics.db'))
        factory = async_sessionmaker(engine)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            async with factory() as db:
                for state in ('queued', 'running', 'failed'):
                    session = InterviewSession(owner_token=str(uuid.uuid4()), challenge_slug='order-hold-reason',
                                               workspace_path='/private/candidate', challenge_version='1')
                    db.add(session)
                    await db.flush()
                    db.add(InterviewGradingJob(session_id=session.id, source_digest='a' * 64,
                        snapshot_path='/private/candidate', challenge_slug=session.challenge_slug, challenge_version='1',
                        status=state, created_at=datetime.now(timezone.utc) - timedelta(seconds=600),
                        lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=10), last_error='private candidate error'))
                await db.commit()
            metrics = (await operational_metrics(engine)).decode()
            assert 'promptcode_grading_jobs{status="failed"} 1.0' in metrics
            assert 'promptcode_grading_stale_leases 1.0' in metrics
            assert 'promptcode_grading_oldest_queued_seconds' in metrics
            assert 'private' not in metrics
        finally:
            await engine.dispose()
    asyncio.run(check())


@pytest.mark.skipif(not os.getenv('PROMPTCODE_TEST_ADMISSION_DATABASE_URL'), reason='Requires a disposable PostgreSQL database')
def test_postgres_simultaneous_accounts_cannot_overfill_global_queue(monkeypatch):
    """Run with an explicit local test DB; isolate all tables in a random schema."""
    from sqlalchemy import func, select, text
    monkeypatch.setenv('PROMPTCODE_GRADING_MAX_PENDING_JOBS', '3')
    get_settings.cache_clear()
    async def check():
        url = os.environ['PROMPTCODE_TEST_ADMISSION_DATABASE_URL']
        admin = create_async_engine(url)
        schema = 'admission_' + uuid.uuid4().hex
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            ids = []
            async with factory() as db:
                for index in range(12):
                    owner = User(email=f'{index}@admission.test', username=f'owner{index}', password_hash='unused')
                    db.add(owner)
                    await db.flush()
                    session = InterviewSession(user_id=owner.id, owner_token=str(uuid.uuid4()), challenge_slug='order-hold-reason',
                                               workspace_path='/unused', challenge_version='1')
                    db.add(session)
                    await db.flush()
                    ids.append((owner.id, session.id))
                await db.commit()
            async def admit(pair):
                async with factory() as db:
                    try:
                        await require_grading_capacity(db, pair[0])
                        # Force admissions to overlap while the transaction lock is held.
                        await asyncio.sleep(0.03)
                        db.add(InterviewGradingJob(session_id=pair[1], source_digest='a' * 64, snapshot_path='/unused',
                            challenge_slug='order-hold-reason', challenge_version='1', status='queued'))
                        await db.commit()
                        return True
                    except HTTPException as error:
                        assert error.status_code == 429
                        await db.rollback()
                        return False
            assert sum(await asyncio.gather(*(admit(pair) for pair in ids))) == 3
            async with factory() as db:
                assert (await db.execute(select(func.count()).select_from(InterviewGradingJob))).scalar_one() == 3
            # Expiration must skip a session being submitted, then preserve its
            # committed submitted state instead of applying a stale expiration.
            from app.services.interview.cleanup import expire_due_sessions
            async with factory() as db:
                session = await db.get(InterviewSession, ids[0][1])
                session.status = 'active'
                session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
                await db.commit()
            async with factory() as submit:
                session = (await submit.execute(select(InterviewSession)
                    .where(InterviewSession.id == ids[0][1]).with_for_update())).scalar_one()
                session.status = 'submitted'
                async with factory() as cleanup:
                    assert await expire_due_sessions(cleanup) == 0
                await submit.commit()
            async with factory() as cleanup:
                assert await expire_due_sessions(cleanup) == 0
                assert (await cleanup.get(InterviewSession, ids[0][1])).status == 'submitted'
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            await admin.dispose()
    try:
        asyncio.run(check())
    finally:
        get_settings.cache_clear()
