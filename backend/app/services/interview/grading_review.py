"""Authenticated review service. External evidence is verified, never accepted by HTTP."""
from __future__ import annotations
import copy
import uuid
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.interview_grading import InterviewGradingJob, InterviewGradeReview
from app.models.interview_session import InterviewEvaluation, InterviewSession, InterviewSessionEvent, InterviewAIMessage
from app.models.user import User
from app.services.interview.grading import DimensionReview, HumanReview, _digest, score_reviewed_assessment


def require_reviewer(user: User) -> None:
    if user.role != "interviewer":
        raise HTTPException(403, "Reviewer access required")


async def review_context(db: AsyncSession, session_id: uuid.UUID, user: User | None) -> tuple:
    if user is not None:
        require_reviewer(user)
    session = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id)
                               .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if session is None:
        raise HTTPException(404, "Session not found")
    if user is not None and session.user_id == user.id:
        raise HTTPException(403, "Self-review is prohibited")
    job = (await db.execute(select(InterviewGradingJob).where(InterviewGradingJob.session_id == session_id))).scalar_one_or_none()
    evaluation = (await db.execute(select(InterviewEvaluation).where(InterviewEvaluation.session_id == session_id)
                                  .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if not job or not evaluation or job.status != "completed" or not job.result:
        raise HTTPException(409, "Verified evaluation is not ready")
    from app.services.interview.calibration import challenge_version_for
    if job.challenge_version != challenge_version_for(job.challenge_slug):
        raise HTTPException(409, "Challenge evaluation version has changed")
    from app.services.interview.trusted_evaluator import verify_result
    settings = get_settings()
    from app.services.interview.snapshot import verify_snapshot
    try:
        verify_snapshot(Path(job.snapshot_path), job.source_digest)
        if job.challenge_version != session.challenge_version:
            raise ValueError("Challenge version mismatch")
        verified = verify_result(job.result, signing_key=settings.grading_signing_key,
                                 session_id=str(session.id), job_id=str(job.id),
                                 challenge_slug=job.challenge_slug, source_digest=job.source_digest,
                                 challenge_version=job.challenge_version, lease_token=job.lease_token)
        if verified is False:
            raise ValueError("Unverified result")
    except (ValueError, KeyError, TypeError, OSError):
        raise HTTPException(409, "External evaluation provenance is invalid") from None
    assessment = copy.deepcopy((evaluation.metrics or {}).get("assessment"))
    if not isinstance(assessment, dict) or "packet" not in assessment:
        raise HTTPException(409, "Evidence packet is unavailable")
    packet = assessment["packet"]
    if (packet.get("session_id") != str(session.id)
            or packet.get("challenge_slug") != job.challenge_slug
            or packet.get("challenge_version") != job.challenge_version):
        raise HTTPException(409, "Evidence packet identity does not match submitted source")
    # Strip even database-injected external facts, then install only authenticated result.
    packet["evidence"] = [e for e in packet["evidence"] if e["kind"] not in {"external_evaluation", "submitted_source"}]
    packet["source_digest"] = job.source_digest
    packet["evidence"] += [
        {"id": "source:submitted", "kind": "submitted_source", "payload_digest": job.source_digest},
        {"id": "evaluation:trusted", "kind": "external_evaluation", "payload_digest": _digest(job.result)},
    ]
    assessment["packet_digest"] = _digest(packet)
    return session, job, evaluation, assessment


async def append_review(db: AsyncSession, session_id: uuid.UUID, user: User, review: HumanReview, manual_checks: dict[str, DimensionReview] | None = None) -> InterviewGradeReview:
    session, job, evaluation, assessment = await review_context(db, session_id, user)
    if review.reviewer_id != str(user.id):
        raise HTTPException(403, "Reviewer identity cannot be supplied by another user")
    try:
        requirements = job.result["payload"].get("manual_requirements", [])
        checks = manual_checks or {}
        if set(checks) != set(requirements):
            raise ValueError("Every evaluator coverage gap requires an explicit manual check")
        evidence_ids = {e["id"] for e in assessment["packet"]["evidence"]}
        for check in checks.values():
            if (len(check.evidence_ids) != len(set(check.evidence_ids))
                    or any(i not in evidence_ids for i in check.evidence_ids)
                    or "source:submitted" not in check.evidence_ids):
                raise ValueError("Manual checks require cited submitted source evidence")
        evidence = {e["id"]: e for e in assessment["packet"]["evidence"]}
        ownership = review.dimensions.get("F_communication")
        if ownership and not any(evidence.get(i, {}).get("kind") == "candidate_statement" for i in ownership.evidence_ids):
            raise ValueError("Explanation and ownership require cited defense answers")
        oversight = review.dimensions.get("D_ai_leverage")
        if oversight and not any(evidence.get(i, {}).get("event_type") == "ai_response" for i in oversight.evidence_ids):
            raise ValueError("AI oversight requires cited assistant interaction evidence")
        correctness = review.dimensions.get("A_correctness")
        external_score = job.result["payload"]["score_percent"]
        if correctness and external_score == 0 and correctness.rating != 0:
            raise ValueError("No passing correctness checks requires correctness rating zero")
        if correctness and correctness.rating > 2 and (external_score < 100 or any(check.rating < 3 for check in checks.values())):
            raise ValueError("Unmet functional or manual requirements cap correctness at partial")
        outcome = score_reviewed_assessment(assessment, review)
        outcome["manual_checks"] = {key: value.model_dump() for key, value in checks.items()}
        if "source:submitted" not in review.dimensions["C_fix_quality"].evidence_ids:
            raise ValueError("Implementation quality requires submitted source evidence")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    previous = (await db.execute(select(InterviewGradeReview).where(InterviewGradeReview.session_id == session_id).order_by(InterviewGradeReview.revision.desc()).limit(1))).scalar_one_or_none()
    row = InterviewGradeReview(session_id=session_id, reviewer_id=user.id,
        revision=(previous.revision + 1) if previous else 1,
        packet_digest=review.packet_digest, source_digest=job.source_digest,
        review={**review.model_dump(), "manual_checks": {key: value.model_dump() for key, value in (manual_checks or {}).items()}}, outcome=outcome, supersedes_id=previous.id if previous else None)
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Another review revision was saved; reload evidence") from None
    # Publication is separately gated; persistence alone does not publish a grade.
    metrics = dict(evaluation.metrics or {})
    metrics["grading_review_id"] = str(row.id)
    evaluation.metrics = metrics
    return row


async def reviewer_evidence(db: AsyncSession, session_id: uuid.UUID, user: User) -> dict:
    session, job, evaluation, assessment = await review_context(db, session_id, user)
    from app.services.interview.snapshot import verify_snapshot
    try:
        manifest = verify_snapshot(Path(job.snapshot_path), job.source_digest)
        if sum(item["size"] for item in manifest) > 2_000_000:
            raise ValueError("Snapshot exceeds review limit")
        source = [{"path": item["path"], "content": (Path(job.snapshot_path) / item["path"]).read_text()} for item in manifest]
    except (ValueError, OSError, UnicodeError):
        raise HTTPException(409, "Submitted source integrity check failed") from None
    events = (await db.execute(select(InterviewSessionEvent).where(InterviewSessionEvent.session_id == session_id).order_by(InterviewSessionEvent.created_at))).scalars().all()
    messages = (await db.execute(select(InterviewAIMessage).where(InterviewAIMessage.session_id == session_id).order_by(InterviewAIMessage.created_at))).scalars().all()
    return {"session_id": str(session.id), "assessment": assessment, "source_digest": job.source_digest,
        "source": source, "external_evaluation": job.result,
        "events": [{"id": str(e.id), "event_type": e.event_type, "payload": e.payload} for e in events],
        "ai_transcript": [{"role": m.role, "content": m.content} for m in messages],
        "defend_answers": (evaluation.metrics or {}).get("defend_answers", {})}


async def candidate_review_status(db: AsyncSession, session_id: uuid.UUID) -> dict | None:
    """Internal candidate projection; no raw evaluator/source/guides are returned."""
    from app.services.interview.grading_calibration import publication_allowed
    from app.models.interview_grading import InterviewGradeAppeal
    if not publication_allowed():
        return None
    try:
        _, job, _, assessment = await review_context(db, session_id, None)
    except HTTPException:
        return None
    latest = (await db.execute(select(InterviewGradeReview).where(InterviewGradeReview.session_id == session_id).order_by(InterviewGradeReview.revision.desc()).limit(1))).scalar_one_or_none()
    if not latest or latest.packet_digest != assessment["packet_digest"] or latest.source_digest != job.source_digest:
        return None
    appeal = (await db.execute(select(InterviewGradeAppeal).where(InterviewGradeAppeal.review_id == latest.id))).scalar_one_or_none()
    if appeal and appeal.status in {"pending", "re_review_required"}:
        return None
    return {"review_id": str(latest.id), "revision": latest.revision, **latest.outcome}
