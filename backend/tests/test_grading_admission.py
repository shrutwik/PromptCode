import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects import postgresql
from app.db.base import Base
from app.models.user import User
from app.models.interview_session import InterviewSession
from app.models.interview_grading import InterviewGradingJob
from app.services.interview.grading_admission import require_grading_capacity


async def populate(tmp_path,statuses,other_statuses=()):
    engine=create_async_engine('sqlite+aiosqlite:///'+str(tmp_path/'admission.db'))
    factory=async_sessionmaker(engine,expire_on_commit=False)
    async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    async with factory() as db:
        owner=User(email='owner@test',username='owner',password_hash='test')
        other=User(email='other@test',username='other',password_hash='test')
        db.add_all([owner,other]);await db.flush()
        for user,states in ((owner,statuses),(other,other_statuses)):
            for state in states:
                session=InterviewSession(user_id=user.id,owner_token=str(uuid.uuid4()),challenge_slug='order-hold-reason',workspace_path='/unused',challenge_version='1')
                db.add(session);await db.flush()
                db.add(InterviewGradingJob(session_id=session.id,source_digest='a'*64,snapshot_path='/unused',challenge_slug=session.challenge_slug,challenge_version='1',status=state))
        await db.commit()
        uid=owner.id
    return engine,factory,uid

@pytest.mark.parametrize('statuses,denied',[
    ([],False),(['queued','running'],False),(['queued','running','queued'],True),
    (['queued','running','completed','failed'],False),
])
def test_persisted_pending_count_only_and_other_owners_excluded(tmp_path,statuses,denied):
    async def check():
        engine,factory,uid=await populate(tmp_path,statuses,['queued']*4)
        try:
            async with factory() as db:
                if denied:
                    with pytest.raises(HTTPException) as error:await require_grading_capacity(db,uid)
                    assert error.value.status_code==429 and error.value.headers=={'Retry-After':'60'}
                else:await require_grading_capacity(db,uid)
        finally:await engine.dispose()
    asyncio.run(check())


def test_owner_lock_is_acquired_before_count():
    statements=[]
    class Result:
        def scalar_one_or_none(self):return uuid.uuid4()
        def scalar_one(self):return 0
    async def execute(statement):statements.append(str(statement.compile(dialect=postgresql.dialect())));return Result()
    asyncio.run(require_grading_capacity(SimpleNamespace(execute=execute),uuid.uuid4()))
    assert 'FOR UPDATE' in statements[2] and 'users' in statements[2]
    assert 'count(' in statements[3] and 'interview_sessions.user_id' in statements[3]


def test_missing_owner_fails_closed_before_count():
    db=SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda:0,scalar_one_or_none=lambda:None)))
    with pytest.raises(HTTPException) as error:asyncio.run(require_grading_capacity(db,uuid.uuid4()))
    assert error.value.status_code==404
    assert db.execute.await_count==3


def test_global_cap_counts_legacy_retry_jobs(monkeypatch):
    from app.services.interview import grading_admission
    monkeypatch.setattr(grading_admission, 'get_settings', lambda: SimpleNamespace(grading_max_pending_jobs=5))
    counts = iter((2, 3))
    statements = []
    async def execute(statement):
        statements.append(str(statement.compile(dialect=postgresql.dialect())))
        return SimpleNamespace(scalar_one=lambda: next(counts))
    with pytest.raises(HTTPException) as error:
        asyncio.run(grading_admission.require_global_grading_capacity(SimpleNamespace(execute=execute)))
    assert error.value.status_code == 429
    assert 'evaluation_jobs' in statements[1]


def test_submit_denied_before_snapshot_and_enqueue(monkeypatch):
    from app.api.routes import interview
    from app.services.interview import grading_admission,snapshot
    from app.workers import interview_grading
    owner=SimpleNamespace(id=uuid.uuid4())
    session=SimpleNamespace(id=uuid.uuid4(),user_id=owner.id,status='active',expires_at=None,challenge_slug='order-hold-reason')
    monkeypatch.setattr(interview,'_load_owned_session',AsyncMock(return_value=session))
    deny=AsyncMock(side_effect=HTTPException(429,'Pending limit'))
    monkeypatch.setattr(grading_admission,'require_grading_capacity',deny)
    monkeypatch.setattr(snapshot,'freeze_submission',lambda *_:pytest.fail('Cap checked after snapshot creation'))
    monkeypatch.setattr(interview_grading,'enqueue_grading_job',AsyncMock(side_effect=AssertionError('Enqueue before cap')))
    db=SimpleNamespace()
    with pytest.raises(HTTPException) as error:
        asyncio.run(interview.submit_session(session.id,request=None,db=db,user=owner))
    assert error.value.status_code==429
    deny.assert_awaited_once_with(db,owner.id)


def test_staff_retry_denied_before_requeue_and_integrity_work(monkeypatch):
    from app.api.routes import interview_grading as route
    from app.services.interview import grading_admission,snapshot
    staff=SimpleNamespace(id=uuid.uuid4(),role='interviewer')
    session=SimpleNamespace(id=uuid.uuid4(),user_id=uuid.uuid4(),challenge_slug='order-hold-reason',challenge_version='1')
    job=SimpleNamespace(status='failed')
    results=iter([session,job])
    async def execute(_):return SimpleNamespace(scalar_one_or_none=lambda:next(results))
    db=SimpleNamespace(execute=execute,commit=AsyncMock())
    deny=AsyncMock(side_effect=HTTPException(429,'Pending limit'))
    monkeypatch.setattr(grading_admission,'require_grading_capacity',deny)
    monkeypatch.setattr(snapshot,'verify_snapshot',lambda *_:pytest.fail('Admission checked after integrity work'))
    with pytest.raises(HTTPException) as error:asyncio.run(route.retry_grading(session.id,user=staff,db=db))
    assert error.value.status_code==429 and job.status=='failed'
    deny.assert_awaited_once_with(db,session.user_id)
    db.commit.assert_not_called()


def test_staff_retry_rejects_registry_version_drift(monkeypatch):
    from app.api.routes import interview_grading as route
    from app.services.interview import grading_admission,snapshot
    staff=SimpleNamespace(id=uuid.uuid4(),role='interviewer')
    session=SimpleNamespace(id=uuid.uuid4(),user_id=uuid.uuid4(),challenge_slug='order-hold-reason',challenge_version='old')
    job=SimpleNamespace(status='failed',challenge_slug=session.challenge_slug,challenge_version='old')
    results=iter([session,job])
    async def execute(_):return SimpleNamespace(scalar_one_or_none=lambda:next(results))
    db=SimpleNamespace(execute=execute,commit=AsyncMock())
    monkeypatch.setattr(grading_admission,'require_grading_capacity',AsyncMock())
    monkeypatch.setattr(snapshot,'verify_snapshot',lambda *_:pytest.fail('Stale version reached snapshot validation'))
    with pytest.raises(HTTPException) as error:asyncio.run(route.retry_grading(session.id,user=staff,db=db))
    assert error.value.status_code==409 and job.status=='failed'
    db.commit.assert_not_called()
