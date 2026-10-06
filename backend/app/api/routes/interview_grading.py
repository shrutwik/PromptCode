"""Staff evidence review and owner-scoped practice rating appeals."""
from __future__ import annotations
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.interview_session import InterviewSession
from app.models.interview_grading import InterviewGradeReview, InterviewGradeAppeal, InterviewAppealDecision
from app.services.interview.grading import DimensionReview, HumanReview, RUBRIC_VERSION
from app.services.interview.grading_review import append_review, candidate_review_status, require_reviewer, reviewer_evidence

router = APIRouter(prefix="/interview/grading", tags=["interview grading"])

class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packet_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    dimensions: dict[str, DimensionReview]
    manual_checks: dict[str, DimensionReview] = Field(default_factory=dict)

class AppealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    review_id: uuid.UUID
    reason: str = Field(min_length=20, max_length=4000)

class AppealDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    disposition: str = Field(pattern=r"^(upheld|re_review_required)$")
    reason: str = Field(min_length=20, max_length=4000)

@router.get("/sessions/{session_id}/evidence")
async def evidence(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await reviewer_evidence(db, session_id, user)

@router.post("/sessions/{session_id}/reviews")
async def create_review(session_id: uuid.UUID, body: ReviewRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    review = HumanReview(reviewer_id=str(user.id), reviewer_kind="human", rubric_version=RUBRIC_VERSION,
                        packet_digest=body.packet_digest, dimensions=body.dimensions)
    row = await append_review(db, session_id, user, review, body.manual_checks)
    await db.commit()
    return {"id": str(row.id), "revision": row.revision, "outcome": row.outcome,
            "notice": "Stored staff practice review; publication requires calibration approval."}

@router.get("/sessions/{session_id}/reviews")
async def review_history(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    require_reviewer(user)
    session = await db.get(InterviewSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.user_id == user.id:
        raise HTTPException(403, "Self-review is prohibited")
    rows = (await db.execute(select(InterviewGradeReview).where(InterviewGradeReview.session_id == session_id).order_by(InterviewGradeReview.revision))).scalars().all()
    return {"reviews": [{"id": str(r.id), "revision": r.revision, "reviewer_id": str(r.reviewer_id), "outcome": r.outcome, "created_at": r.created_at.isoformat()} for r in rows]}

@router.post("/sessions/{session_id}/appeals")
async def create_appeal(session_id: uuid.UUID, body: AppealRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    session = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id).with_for_update())).scalar_one_or_none()
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")
    review = await db.get(InterviewGradeReview, body.review_id)
    if not review or review.session_id != session_id:
        raise HTTPException(404, "Review not found")
    latest = (await db.execute(select(InterviewGradeReview).where(InterviewGradeReview.session_id == session_id).order_by(InterviewGradeReview.revision.desc()).limit(1))).scalar_one()
    if review.id != latest.id:
        raise HTTPException(409, "Only the current review can be appealed")
    existing = (await db.execute(select(InterviewGradeAppeal).where(InterviewGradeAppeal.review_id == review.id))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "This review already has an appeal")
    published = await candidate_review_status(db, session_id)
    if not published or published["review_id"] != str(review.id):
        raise HTTPException(409, "This review is not published")
    row = InterviewGradeAppeal(session_id=session_id, review_id=review.id, candidate_id=user.id, reason=body.reason)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "This review already has an appeal") from None
    return {"id": str(row.id), "status": "pending"}

@router.get("/sessions/{session_id}/appeals")
async def appeals(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    session = await db.get(InterviewSession, session_id)
    if not session or (session.user_id != user.id and user.role != "interviewer"):
        raise HTTPException(404, "Session not found")
    rows = (await db.execute(select(InterviewGradeAppeal).where(InterviewGradeAppeal.session_id == session_id).order_by(InterviewGradeAppeal.created_at))).scalars().all()
    result = []
    for row in rows:
        decision = (await db.execute(select(InterviewAppealDecision).where(InterviewAppealDecision.appeal_id == row.id))).scalar_one_or_none()
        result.append({"id": str(row.id), "review_id": str(row.review_id), "reason": row.reason, "status": row.status,
            "decision": {"disposition": decision.disposition, "reason": decision.reason} if decision else None})
    return {"appeals": result}

@router.post("/appeals/{appeal_id}/decision")
async def decide_appeal(appeal_id: uuid.UUID, body: AppealDecisionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    require_reviewer(user)
    appeal = (await db.execute(select(InterviewGradeAppeal).where(InterviewGradeAppeal.id == appeal_id).with_for_update())).scalar_one_or_none()
    if not appeal:
        raise HTTPException(404, "Appeal not found")
    review = await db.get(InterviewGradeReview, appeal.review_id)
    if user.id in {appeal.candidate_id, review.reviewer_id}:
        raise HTTPException(403, "Appeals require an independent reviewer")
    if appeal.status != "pending":
        raise HTTPException(409, "Appeal already decided")
    db.add(InterviewAppealDecision(appeal_id=appeal.id, reviewer_id=user.id, disposition=body.disposition, reason=body.reason))
    appeal.status = body.disposition
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Appeal already decided") from None
    return {"id": str(appeal.id), "status": appeal.status,
            "notice": "Re-review requires a new evidence-bound review revision."}


@router.post("/sessions/{session_id}/feedback")
async def feedback(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    from app.core.config import get_settings
    from app.services.interview.grading_feedback import generate_grading_feedback
    from app.services.interview.grading_review import review_context
    from app.models.interview_session import InterviewEvaluation
    if not get_settings().grading_feedback_enabled:
        raise HTTPException(409, "AI review feedback is disabled")
    evidence = await reviewer_evidence(db, session_id, user)
    session, _, evaluation, assessment = await review_context(db, session_id, user)
    # The helper treats source as untrusted supplementary text, never as a rating.
    revision = assessment["packet_digest"]
    transient_metrics = dict(evaluation.metrics or {})
    transient_metrics["assessment"] = assessment
    evaluation.metrics = transient_metrics
    await db.commit()
    source_text = "\n".join(item["path"] + "\n" + item["content"] for item in evidence["source"])[:1800]
    result = await generate_grading_feedback(db, session, evaluation, source_diff=source_text,
                                           external_result=evidence["external_evaluation"])
    await db.refresh(evaluation)
    _, _, _, current = await review_context(db, session_id, user)
    if current["packet_digest"] != revision:
        return {"status": "pending_review", "reason": "evidence_changed"}
    metrics = dict(evaluation.metrics or {})
    metrics["grading_ai_feedback"] = result
    evaluation.metrics = metrics
    await db.commit()
    return result


@router.post("/sessions/{session_id}/retry")
async def retry_grading(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Operator retry of exhausted infrastructure work; never rerun a completed grade."""
    from datetime import datetime, timezone
    from pathlib import Path
    from app.models.interview_grading import InterviewGradingJob
    from app.models.interview_session import InterviewEvaluation, InterviewSessionEvent
    from app.services.interview.snapshot import verify_snapshot
    require_reviewer(user)
    session = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id).with_for_update())).scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if session.user_id == user.id:
        raise HTTPException(403, "Self-review is prohibited")
    job = (await db.execute(select(InterviewGradingJob).where(InterviewGradingJob.session_id == session_id).with_for_update())).scalar_one_or_none()
    if not job or job.status != "failed":
        raise HTTPException(409, "Only failed grading jobs can be retried")
    from app.services.interview.grading_admission import require_grading_capacity
    await require_grading_capacity(db, session.user_id)
    try:
        from app.services.interview.calibration import challenge_version_for
        from app.services.interview.registry import get_challenge
        if (job.challenge_version != session.challenge_version or job.challenge_slug != session.challenge_slug
                or get_challenge(job.challenge_slug) is None
                or job.challenge_version != challenge_version_for(job.challenge_slug)):
            raise ValueError("Challenge identity mismatch")
        verify_snapshot(Path(job.snapshot_path), job.source_digest)
    except (ValueError, OSError):
        raise HTTPException(409, "Frozen submission identity or integrity is invalid") from None
    db.add(InterviewSessionEvent(session_id=session_id, event_type="grading_retry_requested",
        payload={"actor_id": str(user.id), "job_id": str(job.id), "previous_attempts": job.attempts}))
    job.status = "queued"
    job.attempts = 0
    job.max_attempts = 3
    job.lease_token = None
    job.lease_expires_at = None
    job.result = None
    job.available_at = datetime.now(timezone.utc)
    job.started_at = None
    job.finished_at = None
    job.last_error = None
    evaluation = (await db.execute(select(InterviewEvaluation).where(InterviewEvaluation.session_id == session_id).with_for_update())).scalar_one_or_none()
    if evaluation:
        metrics = dict(evaluation.metrics or {})
        assessment = dict(metrics.get("assessment") or {})
        assessment["execution_status"] = "queued"
        assessment["status"] = "pending_review"
        assessment["total_score"] = None
        metrics["assessment"] = assessment
        evaluation.metrics = metrics
    await db.commit()
    return {"job_id": str(job.id), "status": "queued", "max_attempts": 3}
