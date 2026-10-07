"""Authenticated executor boundary for immutable, attempt-bound grading."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import sandbox_executor as executor
from app.models.interview_grading import InterviewGradingJob
from app.services.interview import snapshot, trusted_evaluator, workspace
from app.services.interview.calibration import challenge_version_for
from app.services.interview.trusted_cases import (
    MANUAL_REQUIREMENTS,
    VERSION,
    cases_for,
    inventory_digest,
)

TOKEN='internal-executor-token'
KEY='separate-grading-signing-key-at-least-32-bytes'
LEASE='a'*64

@pytest.fixture
def grading_boundary(monkeypatch,tmp_path):
    monkeypatch.setattr(executor.settings,'sandbox_executor_token',TOKEN)
    monkeypatch.setattr(executor.settings,'grading_signing_key',KEY)
    monkeypatch.setattr(workspace,'workspace_root',lambda:tmp_path)
    monkeypatch.setattr(snapshot,'workspace_root',lambda:tmp_path)
    monkeypatch.setattr(executor,'_executor_run_limiter',lambda:asyncio.Semaphore(1))
    monkeypatch.setattr('app.services.interview.runner.reap_expired_runners',lambda:None)
    sid=uuid.uuid4();jid=uuid.uuid4()
    source=tmp_path/str(sid);source.mkdir();(source/'candidate.py').write_text('value=7\n')
    frozen=snapshot.freeze_submission(source,str(sid))
    job=SimpleNamespace(id=jid,session_id=sid,source_digest=frozen.source_digest,snapshot_path=str(frozen.source_path),
        challenge_slug='order-hold-reason',challenge_version=challenge_version_for('order-hold-reason'),
        status='running',lease_token=LEASE,lease_expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
    db=SimpleNamespace(get=AsyncMock(return_value=job))
    return job,db,frozen


def request(job,lease=LEASE):
    return executor.InterviewGradeRequest(job_id=job.id,lease_token=lease)

def invoke(job,db,authorization='Bearer '+TOKEN,lease=LEASE):
    return asyncio.run(executor.grade_interview(request(job,lease),authorization=authorization,db=db))

@pytest.mark.parametrize('authorization',[None,'Bearer wrong','Basic '+TOKEN,TOKEN])
def test_unauthorized_rejected_before_database(grading_boundary,authorization):
    job,db,_=grading_boundary
    with pytest.raises(HTTPException) as error:invoke(job,db,authorization)
    assert error.value.status_code==401
    db.get.assert_not_called()

@pytest.mark.parametrize('field',['snapshot_path','source_digest','session_id','challenge_slug','challenge_version','signing_key','image','command','runner_config'])
def test_caller_cannot_choose_source_identity_or_launch_configuration(field):
    with pytest.raises(ValidationError):
        executor.InterviewGradeRequest(job_id=uuid.uuid4(),lease_token=LEASE,**{field:'/arbitrary/host/source'})

@pytest.mark.parametrize('lease',['', 'short', 'g'*64, 'a'*65])
def test_lease_syntax_is_bounded(lease):
    with pytest.raises(ValidationError):executor.InterviewGradeRequest(job_id=uuid.uuid4(),lease_token=lease)

@pytest.mark.parametrize('state',['expired','wrong-token','queued','completed','missing-expiry','missing-token'])
def test_stale_or_unclaimed_lease_never_reaches_evaluation(grading_boundary,monkeypatch,state):
    job,db,_=grading_boundary
    if state=='expired':job.lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    if state=='wrong-token':job.lease_token='b'*64
    if state in {'queued','completed'}:job.status=state
    if state=='missing-expiry':job.lease_expires_at=None
    if state=='missing-token':job.lease_token=None
    monkeypatch.setattr(trusted_evaluator,'evaluate_snapshot',lambda *_args,**_kw:pytest.fail('Invalid lease reached evaluator'))
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code==409

@pytest.mark.parametrize('path_kind',['outside','other-session','symlink'])
def test_owned_snapshot_path_is_required(grading_boundary,monkeypatch,tmp_path,path_kind):
    job,db,frozen=grading_boundary
    if path_kind=='outside':job.snapshot_path='/etc'
    if path_kind=='other-session':job.snapshot_path=str(tmp_path/'.submitted'/str(uuid.uuid4())/job.source_digest/'source')
    if path_kind=='symlink':
        link=tmp_path/'linked';link.symlink_to(frozen.source_path,target_is_directory=True);job.snapshot_path=str(link)
    monkeypatch.setattr(trusted_evaluator,'evaluate_snapshot',lambda *_args,**_kw:pytest.fail('Unowned source reached evaluator'))
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code==400


def test_tampered_frozen_bytes_never_reach_evaluation(grading_boundary,monkeypatch):
    job,db,frozen=grading_boundary
    source=frozen.source_path/'candidate.py';source.chmod(0o644);source.write_text('value=999\n')
    monkeypatch.setattr(trusted_evaluator,'evaluate_snapshot',lambda *_args,**_kw:pytest.fail('Tampered source reached evaluator'))
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code==409


def test_unknown_job_returns_missing(grading_boundary):
    job,db,_=grading_boundary;db.get.return_value=None
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code==404


def test_signing_configuration_fails_closed_before_database(grading_boundary,monkeypatch):
    job,db,_=grading_boundary
    monkeypatch.setattr(executor.settings,'grading_signing_key','')
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code==503
    db.get.assert_not_called()


def test_success_uses_only_job_identity_and_executor_signing_key(grading_boundary,monkeypatch):
    job,db,frozen=grading_boundary
    def evaluate(path,**kw):
        assert path==frozen.source_path
        assert kw==dict(session_id=str(job.session_id),job_id=str(job.id),challenge_slug=job.challenge_slug,
            source_digest=job.source_digest,challenge_version=job.challenge_version,lease_token=LEASE,signing_key=KEY)
        cases=[{'id':c.id,'weight':c.weight,'passed':True,'error':None} for c in cases_for(job.challenge_slug)]
        total=sum(c['weight'] for c in cases)
        payload=dict(session_id=str(job.session_id),job_id=str(job.id),challenge_slug=job.challenge_slug,
            source_digest=job.source_digest,challenge_version=job.challenge_version,lease_token=LEASE,
            evaluator_version=VERSION,inventory_digest=inventory_digest(job.challenge_slug),cases=cases,
            earned_weight=total,total_weight=total,score_percent=100.0,complete=True,
            manual_requirements=MANUAL_REQUIREMENTS.get(job.challenge_slug,[]))
        return trusted_evaluator.sign_result(payload,signing_key=KEY)
    monkeypatch.setattr(trusted_evaluator,'evaluate_snapshot',evaluate)
    envelope=invoke(job,db)
    result=trusted_evaluator.verify_result(envelope,signing_key=KEY,session_id=str(job.session_id),job_id=str(job.id),
        challenge_slug=job.challenge_slug,source_digest=job.source_digest,challenge_version=job.challenge_version,lease_token=LEASE)
    assert result['score_percent']==100
    assert KEY not in str(envelope)
    db.get.assert_awaited_once_with(InterviewGradingJob,job.id)


def test_http_request_cannot_inject_arbitrary_source(grading_boundary):
    job,db,_=grading_boundary
    async def get_db():yield db
    executor.app.dependency_overrides[executor.get_db]=get_db
    try:
        with TestClient(executor.app) as client:
            r=client.post('/v1/interview/grade',headers={'Authorization':'Bearer '+TOKEN},
                json={'job_id':str(job.id),'lease_token':LEASE,'snapshot_path':'/etc','signing_key':'caller'})
        assert r.status_code==422
        db.get.assert_not_called()
    finally:executor.app.dependency_overrides.clear()


def test_current_inventory_cannot_grade_stale_challenge_version(grading_boundary,monkeypatch):
    job,db,_=grading_boundary;job.challenge_version='old-version'
    monkeypatch.setattr(trusted_evaluator,'evaluate_snapshot',lambda *_args,**_kw:pytest.fail('Stale version reached current evaluator'))
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code==409


def test_unknown_challenge_cannot_reach_evaluator(grading_boundary,monkeypatch):
    job,db,_=grading_boundary;job.challenge_slug='not-a-registered-question'
    monkeypatch.setattr(trusted_evaluator,'evaluate_snapshot',lambda *_args,**_kw:pytest.fail('Unknown challenge reached evaluator'))
    with pytest.raises(HTTPException) as error:invoke(job,db)
    assert error.value.status_code in (404,409)
