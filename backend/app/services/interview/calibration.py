"""Calibration tooling: distributions, anomalies, session review payloads."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_ops import HumanReview
from app.models.interview_session import (
    InterviewAIMessage,
    InterviewEvaluation,
    InterviewSession,
    InterviewSessionEvent,
)
from app.services.interview.analytics import _dist
from app.services.interview.registry import get_challenge, load_registry


def challenge_version_for(slug: str) -> str:
    """Persist registry version with challenge; default registry.version."""
    reg = load_registry()
    meta = get_challenge(slug) or {}
    ver = meta.get("version") or reg.get("version") or "1"
    return str(ver)


async def calibration_overview(db: AsyncSession) -> dict[str, Any]:
    sessions = (await db.execute(select(InterviewSession))).scalars().all()
    evals = {
        e.session_id: e
        for e in (await db.execute(select(InterviewEvaluation))).scalars().all()
    }
    reviews = (await db.execute(select(HumanReview))).scalars().all()
    review_by_session = {r.session_id: r for r in reviews}

    by_slug: dict[str, list[InterviewSession]] = {}
    for s in sessions:
        by_slug.setdefault(s.challenge_slug, []).append(s)

    challenges = []
    for slug, items in sorted(by_slug.items()):
        meta = get_challenge(slug) or {}
        intended_minutes = meta.get("estimated_minutes")
        intended_diff = meta.get("difficulty")
        submitted = [s for s in items if s.status == "submitted"]
        scores = [float(evals[s.id].total_score) for s in submitted if s.id in evals]
        times: list[float] = []
        correctness: list[float] = []
        feedback_diff: list[float] = []
        for s in submitted:
            if s.submitted_at and s.started_at:
                ms = s.active_duration_ms
                if ms is None:
                    ms = int((s.submitted_at - s.started_at).total_seconds() * 1000)
                    if s.infra_blocked_ms:
                        ms = max(0, ms - s.infra_blocked_ms)
                times.append(ms / 60000.0)
            ev = evals.get(s.id)
            if ev and isinstance(ev.test_summary, dict):
                correctness.append(1.0 if ev.test_summary.get("ok") else 0.0)
            if s.feedback_difficulty:
                feedback_diff.append(float(s.feedback_difficulty))
        challenges.append(
            {
                "challenge_slug": slug,
                "intended": {
                    "difficulty": intended_diff,
                    "estimated_minutes": intended_minutes,
                },
                "observed": {
                    "n": len(submitted),
                    "score": _dist(scores),
                    "time_minutes": _dist(times),
                    "correctness_rate": round(sum(correctness) / len(correctness), 3)
                    if correctness
                    else None,
                    "feedback_difficulty": _dist(feedback_diff),
                },
                "human_reviews": sum(1 for s in items if s.id in review_by_session),
                "disagreements": sum(
                    1
                    for s in items
                    if s.id in review_by_session and review_by_session[s.id].disagreement
                ),
            }
        )
    return {
        "challenges": challenges,
        "note": "Intended vs observed — for calibration, not ranking.",
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def anomaly_flags(session: InterviewSession, evaluation: InterviewEvaluation | None) -> list[str]:
    flags: list[str] = []
    meta = get_challenge(session.challenge_slug) or {}
    intended = float(meta.get("estimated_minutes") or 30)
    wall_min = None
    if session.submitted_at and session.started_at:
        wall_min = (session.submitted_at - session.started_at).total_seconds() / 60.0
    if wall_min is not None:
        if wall_min < intended * 0.25:
            flags.append("suspiciously_short_time")
        if wall_min > intended * 3:
            flags.append("suspiciously_long_time")
    tags = session.infra_failure_tags or []
    if len(tags) >= 2:
        flags.append("high_infra_fail")
    if evaluation:
        rubric = evaluation.rubric or {}
        scores = [float(v.get("score", 0)) for v in rubric.values() if isinstance(v, dict)]
        if len(scores) >= 3 and len(set(round(s, 1) for s in scores)) == 1:
            flags.append("identical_category_scores")
        ok = bool((evaluation.test_summary or {}).get("ok"))
        total = float(evaluation.total_score or 0)
        if ok and total < 20:
            flags.append("correctness_score_mismatch_low")
        if (not ok) and total > 80:
            flags.append("correctness_score_mismatch_high")
    return flags


async def session_review_payload(
    db: AsyncSession, session_id: uuid.UUID
) -> dict[str, Any] | None:
    session = (
        await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    ).scalar_one_or_none()
    if session is None:
        return None
    evaluation = (
        await db.execute(
            select(InterviewEvaluation).where(InterviewEvaluation.session_id == session.id)
        )
    ).scalar_one_or_none()
    events = (
        await db.execute(
            select(InterviewSessionEvent)
            .where(InterviewSessionEvent.session_id == session.id)
            .order_by(InterviewSessionEvent.created_at)
        )
    ).scalars().all()
    ai = (
        await db.execute(
            select(InterviewAIMessage)
            .where(InterviewAIMessage.session_id == session.id)
            .order_by(InterviewAIMessage.created_at)
        )
    ).scalars().all()
    reviews = (
        await db.execute(select(HumanReview).where(HumanReview.session_id == session.id))
    ).scalars().all()

    duration = None
    if session.submitted_at and session.started_at:
        duration = int((session.submitted_at - session.started_at).total_seconds())

    explain = []
    if evaluation and isinstance(evaluation.rubric, dict):
        for cat, body in evaluation.rubric.items():
            if isinstance(body, dict):
                explain.append(
                    {
                        "category": cat,
                        "score": body.get("score"),
                        "max": body.get("max"),
                        "evidence": body.get("evidence"),
                    }
                )

    return {
        "session": {
            "id": str(session.id),
            "challenge_slug": session.challenge_slug,
            "challenge_version": session.challenge_version,
            "scoring_version": session.scoring_version,
            "status": session.status,
            "attempt_number": session.attempt_number,
            "user_id": str(session.user_id) if session.user_id else None,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
            "wall_duration_s": duration,
            "wall_duration_ms": session.wall_duration_ms,
            "active_duration_ms": session.active_duration_ms,
            "infra_blocked_ms": session.infra_blocked_ms,
            "infra_failure_tags": session.infra_failure_tags or [],
            "abandon_reason": session.abandon_reason,
            "feedback": {
                "realism": session.feedback_realism,
                "difficulty": session.feedback_difficulty,
                "text": session.feedback_text,
                "meta": session.feedback_meta,
            },
        },
        "automated_score": {
            "total_score": evaluation.total_score if evaluation else None,
            "rubric": evaluation.rubric if evaluation else None,
            "metrics": (
                {k: v for k, v in (evaluation.metrics or {}).items() if k != "answer_guides"}
                if evaluation
                else None
            ),
            "test_summary": evaluation.test_summary if evaluation else None,
            "scoring_version": evaluation.scoring_version if evaluation else None,
            "score_explainability": explain,
        },
        "human_reviews": [
            {
                "id": str(r.id),
                "reviewer": r.reviewer,
                "notes": r.notes,
                "category_observations": r.category_observations,
                "disagreement": r.disagreement,
                "observed_difficulty": r.observed_difficulty,
                "observed_time_minutes": r.observed_time_minutes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
        "timeline": [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
        "ai_message_count": len(ai),
        "anomaly_flags": anomaly_flags(session, evaluation),
        "note": "automated_score and human_review are separate; never silently overwrite.",
    }


async def disagreement_report(db: AsyncSession) -> dict[str, Any]:
    reviews = (
        await db.execute(select(HumanReview).where(HumanReview.disagreement.is_(True)))
    ).scalars().all()
    items = []
    for r in reviews:
        session = (
            await db.execute(select(InterviewSession).where(InterviewSession.id == r.session_id))
        ).scalar_one_or_none()
        evaluation = (
            await db.execute(
                select(InterviewEvaluation).where(InterviewEvaluation.session_id == r.session_id)
            )
        ).scalar_one_or_none()
        items.append(
            {
                "session_id": str(r.session_id),
                "challenge_slug": session.challenge_slug if session else None,
                "automated_total": evaluation.total_score if evaluation else None,
                "scoring_version": evaluation.scoring_version if evaluation else None,
                "reviewer": r.reviewer,
                "notes": r.notes,
                "category_observations": r.category_observations,
            }
        )
    return {"disagreements": items, "n": len(items)}


def anonymized_export_row(
    session: InterviewSession,
    evaluation: InterviewEvaluation | None,
    review: HumanReview | None,
) -> dict[str, Any]:
    """No email/name/secrets/full prompts by default."""
    return {
        "session_id_hash": str(session.id)[:8],
        "challenge_slug": session.challenge_slug,
        "challenge_version": session.challenge_version,
        "scoring_version": session.scoring_version,
        "status": session.status,
        "attempt_number": session.attempt_number,
        "wall_duration_ms": session.wall_duration_ms,
        "active_duration_ms": session.active_duration_ms,
        "infra_blocked_ms": session.infra_blocked_ms,
        "infra_failure_tags": session.infra_failure_tags or [],
        "feedback_realism": session.feedback_realism,
        "feedback_difficulty": session.feedback_difficulty,
        "feedback_meta_keys": list((session.feedback_meta or {}).keys()),
        "total_score": evaluation.total_score if evaluation else None,
        "rubric_scores": (
            {
                k: v.get("score")
                for k, v in (evaluation.rubric or {}).items()
                if isinstance(v, dict)
            }
            if evaluation
            else None
        ),
        "tests_ok": (evaluation.test_summary or {}).get("ok") if evaluation else None,
        "human_disagreement": review.disagreement if review else None,
        "cohort_omitted": True,
    }
