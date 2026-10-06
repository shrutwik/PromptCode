import asyncio
import uuid
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.db.base import Base
import app.models
from app.models.user import User
from app.models.interview_session import InterviewSession, InterviewEvaluation, InterviewSessionEvent
from app.models.interview_grading import InterviewGradingJob, InterviewGradeReview
from app.services.interview.grading import pending_assessment, DIMENSIONS, HumanReview
from app.services.interview.grading_review import review_context, append_review
from app.services.interview.trusted_evaluator import sign_result, VERSION
from app.services.interview.trusted_cases import cases_for, inventory_digest, MANUAL_REQUIREMENTS
from app.api.routes.interview_grading import router
from app.core.deps import get_current_user
from app.db.session import get_db

KEY='test-grading-signing-key-at-least-32-bytes'

async def setup(tmp_path, monkeypatch, slug="order-hold-reason"):
    monkeypatch.setattr('app.services.interview.grading_calibration.publication_allowed', lambda:True)
    monkeypatch.setattr('app.services.interview.grading_review.get_settings', lambda:SimpleNamespace(grading_signing_key=KEY))
    engine=create_async_engine('sqlite+aiosqlite:///'+str(tmp_path/'review.db'))
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    from app.services.interview.snapshot import _manifest, manifest_digest
    scratch=tmp_path/'source';scratch.mkdir();(scratch/'app.py').write_text('print(1)')
    manifest=_manifest(scratch);digest=manifest_digest(manifest)
    snapshot=tmp_path/digest/'source';snapshot.parent.mkdir();scratch.rename(snapshot)
    async with factory() as db:
        users=[User(email=f'u{i}@test.com',username=f'u{i}',password_hash='hash',role='interviewer' if i else None) for i in range(3)]
        db.add_all(users);await db.flush()
        session=InterviewSession(user_id=users[0].id,owner_token='token',challenge_slug=slug,workspace_path='/no')
        db.add(session);await db.flush()
        assessment=pending_assessment(session_id=str(session.id),challenge_slug=session.challenge_slug,challenge_version='1',events=[],test_summary={},defend_answers={'0':'I verified the persistence change and release regression.'})
        evaluation=InterviewEvaluation(session_id=session.id,metrics={'assessment':assessment})
        job=InterviewGradingJob(session_id=session.id,source_digest=digest,snapshot_path=str(snapshot),snapshot_manifest={'files':manifest},challenge_slug=session.challenge_slug,challenge_version='1',lease_token='f'*64,status='completed')
        db.add_all([evaluation,job]);await db.flush()
        cases=cases_for(session.challenge_slug);total=sum(c.weight for c in cases)
        payload={'session_id':str(session.id),'job_id':str(job.id),'challenge_slug':session.challenge_slug,'source_digest':job.source_digest,'challenge_version':job.challenge_version,'lease_token':job.lease_token,'evaluator_version':VERSION,'inventory_digest':inventory_digest(session.challenge_slug),'complete':True,'cases':[{'id':c.id,'weight':c.weight,'passed':True,'error':None} for c in cases],'earned_weight':total,'total_weight':total,'score_percent':100.0,'manual_requirements':MANUAL_REQUIREMENTS.get(session.challenge_slug,[])}
        job.result=sign_result(payload,signing_key=KEY);await db.commit()
    return engine,factory,users,session,job


def review(assessment,user):
    return HumanReview(reviewer_id=str(user.id),reviewer_kind='human',packet_digest=assessment['packet_digest'],rubric_version='v3-evidence',dimensions={key:{'rating':3,'rationale':'Examined the submitted source and verified evaluation evidence.','evidence_ids':['evaluation:trusted'] if key=='A_correctness' else ['defend:0'] if key=='F_communication' else ['source:submitted']} for key in DIMENSIONS if key!='D_ai_leverage'})


def test_reviews_reject_candidate_selfreview_forged_provenance_stale_and_append(tmp_path,monkeypatch):
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            for user in [users[0],User(id=users[0].id,role='interviewer')]:
                with pytest.raises(Exception) as exc: await review_context(db,session.id,user)
                assert exc.value.status_code==403
            _,row,_,assessment=await review_context(db,session.id,users[1])
            stale=review(assessment,users[1]);stale.packet_digest='b'*64
            with pytest.raises(Exception) as exc: await append_review(db,session.id,users[1],stale)
            assert exc.value.status_code==422
            first=await append_review(db,session.id,users[1],review(assessment,users[1]));await db.commit()
            second=await append_review(db,session.id,users[2],review(assessment,users[2]));await db.commit()
            assert second.revision==2 and second.supersedes_id==first.id
            assert len((await db.execute(select(InterviewGradeReview))).scalars().all())==2
            row.result={**row.result,'signature':'f'*64};await db.commit()
            with pytest.raises(Exception) as exc: await review_context(db,session.id,users[1])
            assert exc.value.status_code==409
        await engine.dispose()
    asyncio.run(run())


def test_http_auth_appeal_ownership_independence_and_single_decision(tmp_path,monkeypatch):
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            _,_,_,assessment=await review_context(db,session.id,users[1])
            row=await append_review(db,session.id,users[1],review(assessment,users[1]));await db.commit()
        app=FastAPI();app.include_router(router)
        current=[users[0]]
        app.dependency_overrides[get_current_user]=lambda:current[0]
        async def db_dep():
            async with factory() as db: yield db
        app.dependency_overrides[get_db]=db_dep
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            base=f'/interview/grading/sessions/{session.id}'
            assert (await client.get(base+'/evidence')).status_code==403
            assert (await client.post(base+'/reviews',json={'packet_digest':'a'*64,'dimensions':{},'result':job.result})).status_code==422
            current[0]=users[2]
            assert (await client.post(base+'/appeals',json={'review_id':str(row.id),'reason':'This is a detailed candidate appeal.'})).status_code==404
            current[0]=users[0]
            response=await client.post(base+'/appeals',json={'review_id':str(row.id),'reason':'This is a detailed candidate appeal.'})
            assert response.status_code==200;appeal=response.json()['id']
            assert (await client.post(base+'/appeals',json={'review_id':str(row.id),'reason':'This is a detailed candidate appeal.'})).status_code==409
            current[0]=users[1]
            path=f'/interview/grading/appeals/{appeal}/decision';body={'disposition':'re_review_required','reason':'Independent review found an evidence discrepancy.'}
            assert (await client.post(path,json=body)).status_code==403
            current[0]=users[2]
            assert (await client.post(path,json=body)).status_code==200
            assert (await client.post(path,json=body)).status_code==409
            current[0]=users[0]
            result=(await client.get(base+'/appeals')).json()
            assert result['appeals'][0]['status']=='re_review_required'
        await engine.dispose()
    asyncio.run(run())


def test_publication_gate_defense_revision_and_appeal_invalidate_outcome(tmp_path,monkeypatch):
    from app.services.interview.grading_review import candidate_review_status
    from app.services.interview.grading import revise_defense
    from app.models.interview_grading import InterviewGradeAppeal
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            _,_,evaluation,assessment=await review_context(db,session.id,users[1])
            row=await append_review(db,session.id,users[1],review(assessment,users[1]));await db.commit()
            assert (await candidate_review_status(db,session.id))['review_id']==str(row.id)
            monkeypatch.setattr('app.services.interview.grading_calibration.publication_allowed',lambda:False)
            assert await candidate_review_status(db,session.id) is None
            monkeypatch.setattr('app.services.interview.grading_calibration.publication_allowed',lambda:True)
            db.add(InterviewGradeAppeal(session_id=session.id,review_id=row.id,candidate_id=users[0].id,reason='I dispute the evidence evaluation.'))
            await db.commit()
            assert await candidate_review_status(db,session.id) is None
            appeal=(await db.execute(select(InterviewGradeAppeal))).scalar_one();appeal.status='upheld';await db.commit()
            assert await candidate_review_status(db,session.id)
            metrics=dict(evaluation.metrics);metrics['assessment']=revise_defense(metrics['assessment'],{'0':'A materially different defense answer.'});evaluation.metrics=metrics;await db.commit()
            assert await candidate_review_status(db,session.id) is None
        await engine.dispose()
    asyncio.run(run())


@pytest.mark.parametrize('all_failed', [False, True])
def test_signed_functional_failures_cannot_be_overridden_by_reviewer(tmp_path,monkeypatch,all_failed):
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            stored=await db.get(InterviewGradingJob,job.id)
            payload=dict(stored.result['payload']);payload['cases']=[dict(c) for c in payload['cases']]
            for index,case in enumerate(payload['cases']):
                if all_failed or index==0: case['passed']=False
            payload['earned_weight']=sum(c['weight'] for c in payload['cases'] if c['passed'])
            payload['score_percent']=round(100*payload['earned_weight']/payload['total_weight'],2)
            stored.result=sign_result(payload,signing_key=KEY);await db.commit()
            _,_,_,assessment=await review_context(db,session.id,users[1])
            proposed=review(assessment,users[1])
            with pytest.raises(Exception) as exc: await append_review(db,session.id,users[1],proposed)
            assert exc.value.status_code==422
            proposed.dimensions['A_correctness'].rating=0 if all_failed else 2
            await append_review(db,session.id,users[1],proposed)
        await engine.dispose()
    asyncio.run(run())


def test_manual_coverage_gaps_must_be_reviewed_and_cannot_be_overridden(tmp_path,monkeypatch):
    from app.services.interview.grading import DimensionReview
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch,'pricing-rule-extract')
        async with factory() as db:
            _,_,_,assessment=await review_context(db,session.id,users[1])
            proposed=review(assessment,users[1])
            with pytest.raises(Exception) as exc: await append_review(db,session.id,users[1],proposed)
            assert exc.value.status_code==422
            checks={gap:DimensionReview(rating=2,rationale='Reviewed submitted source; delegation requirement is only partially met.',evidence_ids=['source:submitted']) for gap in MANUAL_REQUIREMENTS[session.challenge_slug]}
            with pytest.raises(Exception) as exc: await append_review(db,session.id,users[1],proposed,checks)
            assert exc.value.status_code==422
            proposed.dimensions['A_correctness'].rating=2
            await append_review(db,session.id,users[1],proposed,checks)
        await engine.dispose()
    asyncio.run(run())


def test_snapshot_tampering_prevents_staff_review_and_candidate_publication(tmp_path,monkeypatch):
    from pathlib import Path
    from app.services.interview.grading_review import candidate_review_status
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            _,_,_,assessment=await review_context(db,session.id,users[1])
            await append_review(db,session.id,users[1],review(assessment,users[1]));await db.commit()
            (Path(job.snapshot_path)/'app.py').write_text('tampered')
            with pytest.raises(Exception) as exc: await review_context(db,session.id,users[1])
            assert exc.value.status_code==409
            assert await candidate_review_status(db,session.id) is None
        await engine.dispose()
    asyncio.run(run())


def test_staff_failed_job_retry_auth_bounds_integrity_and_history(tmp_path,monkeypatch):
    from pathlib import Path
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            _,_,evaluation,assessment=await review_context(db,session.id,users[1])
            review_row=await append_review(db,session.id,users[1],review(assessment,users[1]))
            metrics=dict(evaluation.metrics);metrics['defend_answers']={'0':'Retain this submitted defense.'};evaluation.metrics=metrics
            await db.commit()
        app=FastAPI();app.include_router(router);current=[users[0]]
        app.dependency_overrides[get_current_user]=lambda:current[0]
        async def db_dep():
            async with factory() as db: yield db
        app.dependency_overrides[get_db]=db_dep
        path=f'/interview/grading/sessions/{session.id}/retry'
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.post(path)).status_code==403
            current[0]=User(id=users[0].id,role='interviewer')
            assert (await client.post(path)).status_code==403
            current[0]=users[1]
            assert (await client.post(path)).status_code==409
            async with factory() as db:
                stored=await db.get(InterviewGradingJob,job.id);stored.status='failed';stored.attempts=3;stored.max_attempts=99;await db.commit()
            source=Path(job.snapshot_path)/'app.py';original=source.read_text();source.write_text('tampered')
            assert (await client.post(path)).status_code==409
            source.write_text(original)
            response=await client.post(path);assert response.status_code==200 and response.json()['max_attempts']==3
            assert (await client.post(path)).status_code==409
        async with factory() as db:
            stored=await db.get(InterviewGradingJob,job.id)
            assert stored.status=='queued' and stored.attempts==0 and stored.max_attempts==3
            assert stored.result is None and stored.lease_token is None and stored.lease_expires_at is None
            evaluation=(await db.execute(select(InterviewEvaluation))).scalar_one()
            assert evaluation.metrics['defend_answers']['0']=='Retain this submitted defense.'
            assert evaluation.metrics['assessment']['execution_status']=='queued'
            assert (await db.get(InterviewGradeReview,review_row.id)) is not None
            event=(await db.execute(select(InterviewSessionEvent).where(InterviewSessionEvent.event_type=='grading_retry_requested'))).scalar_one()
            assert event.payload=={'actor_id':str(users[1].id),'job_id':str(job.id),'previous_attempts':3}
        await engine.dispose()
    asyncio.run(run())


def test_batch_projection_matches_single_session_projection(tmp_path,monkeypatch):
    """The dashboard batch must answer the same question as the per-session call."""
    from app.models.interview_grading import InterviewGradeAppeal
    from app.services.interview.grading_review import (
        candidate_review_status, published_reviews_for_sessions,
    )
    async def run():
        engine,factory,users,session,job=await setup(tmp_path,monkeypatch)
        async with factory() as db:
            _,_,_,assessment=await review_context(db,session.id,users[1])
            row=await append_review(db,session.id,users[1],review(assessment,users[1]));await db.commit()
            # A session with no graded review at all must be absent, not fabricated.
            absent=InterviewSession(user_id=users[0].id,owner_token='t2',challenge_slug=session.challenge_slug,workspace_path='/no')
            db.add(absent);await db.commit()
            published=await published_reviews_for_sessions(db,[session.id,absent.id])
            assert published[str(session.id)]['review_id']==str(row.id)
            assert str(absent.id) not in published
            # Same value as the single-session projection.
            assert published[str(session.id)]==await candidate_review_status(db,session.id)
            # A pending appeal withholds publication for that session only.
            db.add(InterviewGradeAppeal(session_id=session.id,review_id=row.id,candidate_id=users[0].id,reason='I dispute the evidence evaluation.'))
            await db.commit()
            published=await published_reviews_for_sessions(db,[session.id,absent.id])
            assert str(session.id) not in published
            # And the publication gate short-circuits the whole batch.
            monkeypatch.setattr('app.services.interview.grading_calibration.publication_allowed',lambda:False)
            assert await published_reviews_for_sessions(db,[session.id])=={}
        await engine.dispose()
    asyncio.run(run())
