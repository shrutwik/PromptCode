import copy
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from test_grading_review_workflow import setup

from app.models.interview_session import InterviewEvaluation, InterviewSession
from app.services.interview.automated_grading import JudgeResponse
from app.services.interview.grading import DIMENSIONS, RUBRIC_VERSION, revise_defense
from app.workers import interview_ai_grading as worker


async def ready(tmp_path, monkeypatch):
    engine, factory, users, session, job = await setup(tmp_path, monkeypatch)
    monkeypatch.setattr(worker,'async_session_factory',factory)
    monkeypatch.setattr(worker,'get_settings',lambda:SimpleNamespace(grading_auto_enabled=True))
    async with factory() as db:
        stored=await db.get(InterviewSession,session.id)
        stored.status='submitted'
        stored.scoring_version=RUBRIC_VERSION
        evaluation=(await db.execute(select(InterviewEvaluation).where(InterviewEvaluation.session_id==session.id))).scalar_one()
        evaluation.scoring_version=RUBRIC_VERSION
        evaluation.defend_questions=[{'question':'Explain the repair'}]
        evaluation.metrics={**evaluation.metrics,'defend_answers':{'0':'I verified the persistence change and release regression.'}}
        await db.commit()
    return engine,factory,session


def response_for(bundle):
    required={'A_correctness':'external_evaluation','C_fix_quality':'submitted_source',
              'F_communication':'candidate_statement'}
    dimensions={}
    for key in DIMENSIONS:
        if key=='D_ai_leverage' and not bundle['ai_observed']: continue
        item=next(e for e in bundle['evidence'] if e['kind']==required.get(key,'candidate_statement'))
        dimensions[key]={'rating':3,'rationale':'The supplied evidence supports this task-specific rating.',
            'counterevidence':'No exhaustive correctness guarantee.',
            'citations':[{'evidence_id':item['id'],'quote':item['content'][:80]}]}
    return JudgeResponse(dimensions=dimensions,needs_review=False),{'model':'test-model'}


@pytest.mark.asyncio
async def test_completed_job_produces_bound_automatic_report_once(tmp_path,monkeypatch):
    engine,factory,session=await ready(tmp_path,monkeypatch)
    judge=AsyncMock(side_effect=lambda *a,**kw:response_for(kw['bundle']))
    monkeypatch.setattr(worker,'judge_once',judge)
    assert await worker.process_one_ai_grade()
    assert judge.await_count==2
    assert not await worker.process_one_ai_grade()
    async with factory() as db:
        evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
        outcome=worker.candidate_auto_assessment(evaluation)
        assert outcome['status']=='automated_practice'
        assert outcome['total_score']==75
        assert 'passes' not in outcome
        assert len(evaluation.metrics['auto_grading']['passes'])==2
    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_failure_retries_without_failing_candidate(tmp_path,monkeypatch):
    engine,factory,session=await ready(tmp_path,monkeypatch)
    monkeypatch.setattr(worker,'judge_once',AsyncMock(side_effect=TimeoutError()))
    assert await worker.process_one_ai_grade()
    async with factory() as db:
        evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
        assert evaluation.metrics['auto_grading']['status']=='retry_pending'
        assert worker.candidate_auto_assessment(evaluation) is None
        metrics=copy.deepcopy(evaluation.metrics)
        metrics['auto_grading']['next_attempt_at']=0
        evaluation.metrics=metrics
        await db.commit()
    assert await worker.process_one_ai_grade()
    async with factory() as db:
        evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
        assert evaluation.metrics['auto_grading']['status']=='needs_review'
        assert 'outcome' not in evaluation.metrics['auto_grading']
    assert not await worker.process_one_ai_grade()
    await engine.dispose()


@pytest.mark.asyncio
async def test_defense_change_during_grading_discards_stale_result(tmp_path,monkeypatch):
    engine,factory,session=await ready(tmp_path,monkeypatch)
    count=0
    async def judge(*a,**kw):
        nonlocal count
        count+=1
        if count==2:
            async with factory() as db:
                evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
                metrics=copy.deepcopy(evaluation.metrics)
                metrics['assessment']=revise_defense(metrics['assessment'],{'0':'A new defense changes the evidence revision.'})
                metrics['auto_grading']={'status':'queued','attempts':0}
                evaluation.metrics=metrics
                await db.commit()
        return response_for(kw['bundle'])
    monkeypatch.setattr(worker,'judge_once',judge)
    assert await worker.process_one_ai_grade()
    async with factory() as db:
        evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
        assert evaluation.metrics['auto_grading']['status']=='queued'
        assert worker.candidate_auto_assessment(evaluation) is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_missing_defense_and_active_lease_do_not_call_provider(tmp_path,monkeypatch):
    engine,factory,session=await ready(tmp_path,monkeypatch)
    judge=AsyncMock()
    monkeypatch.setattr(worker,'judge_once',judge)
    async with factory() as db:
        evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
        metrics=copy.deepcopy(evaluation.metrics)
        metrics['auto_grading']={'status':'running','lease_until':time.time()+100}
        evaluation.metrics=metrics
        await db.commit()
    assert not await worker.process_one_ai_grade()
    judge.assert_not_awaited()
    async with factory() as db:
        evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
        metrics=copy.deepcopy(evaluation.metrics)
        metrics['defend_answers']={}
        metrics['auto_grading']={'status':'queued'}
        evaluation.metrics=metrics
        await db.commit()
    assert not await worker.process_one_ai_grade()
    judge.assert_not_awaited()
    await engine.dispose()


@pytest.mark.asyncio
async def test_retry_requires_ownership_and_is_bounded(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.api.routes import interview as routes
    from app.models.user import User

    engine, factory, session = await ready(tmp_path, monkeypatch)
    monkeypatch.setattr(routes, 'get_settings', lambda: SimpleNamespace(grading_auto_enabled=True))
    monkeypatch.setattr(routes, 'enforce_rate_limit', AsyncMock())
    request = Request({'type': 'http', 'headers': [], 'method': 'POST', 'path': '/'})
    try:
        async with factory() as db:
            users = (await db.execute(select(User))).scalars().all()
            owner = next(u for u in users if u.id == session.user_id)
            other = next(u for u in users if u.id != session.user_id)
            with pytest.raises(HTTPException) as exc:
                await routes.retry_automatic_grade(session.id, request, db, other)
            assert exc.value.status_code == 404
            evaluation = (await db.execute(select(InterviewEvaluation))).scalar_one()
            metrics = copy.deepcopy(evaluation.metrics)
            metrics['auto_grading'] = {'status': 'needs_review'}
            evaluation.metrics = metrics
            await db.commit()
            assert await routes.retry_automatic_grade(session.id, request, db, owner) == {'status': 'queued'}
            metrics = copy.deepcopy(evaluation.metrics)
            metrics['auto_grading']['status'] = 'needs_review'
            evaluation.metrics = metrics
            await db.commit()
            with pytest.raises(HTTPException) as exc:
                await routes.retry_automatic_grade(session.id, request, db, owner)
            assert exc.value.status_code == 409
    finally:
        await engine.dispose()
