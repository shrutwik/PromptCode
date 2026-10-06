"""Product analytics — funnel events separate from interview timeline."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_ops import ProductAnalyticsEvent
from app.models.interview_session import InterviewEvaluation, InterviewSession

# Product-level only — not Monaco/file/test chatter.
KNOWN_EVENTS = frozenset(
    {
        "user_signed_up",
        "logged_in",
        "challenge_library_viewed",
        "challenge_detail_viewed",
        "session_started",
        "session_abandoned",
        "session_submitted",
        "report_viewed",
        "defend_started",
        "defend_completed",
        "feedback_submitted",
        "grading_reviewer_role_changed",
    }
)

SCORING_VERSION = "v3-evidence"


async def track_event(
    db: AsyncSession,
    *,
    event_name: str,
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    challenge_slug: str | None = None,
    properties: dict | None = None,
    commit: bool = False,
) -> None:
    if event_name not in KNOWN_EVENTS:
        return
    db.add(
        ProductAnalyticsEvent(
            event_name=event_name,
            user_id=user_id,
            session_id=session_id,
            challenge_slug=challenge_slug,
            properties=properties or {},
        )
    )
    if commit:
        await db.commit()


def _pct(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(100.0 * n / d, 1)


def _dist(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "median": None, "p25": None, "p75": None, "min": None, "max": None}
    s = sorted(values)
    n = len(s)

    def _p(p: float) -> float:
        idx = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        return round(s[idx], 2)

    return {
        "n": n,
        "median": round(median(s), 2),
        "p25": _p(25),
        "p75": _p(75),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
    }


async def funnel_aggregates(db: AsyncSession) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(ProductAnalyticsEvent.event_name, func.count())
            .group_by(ProductAnalyticsEvent.event_name)
        )
    ).all()
    counts = {name: int(c) for name, c in rows}
    signed_up = counts.get("user_signed_up", 0)
    started = counts.get("session_started", 0)
    submitted = counts.get("session_submitted", 0)
    reports = counts.get("report_viewed", 0)
    defend = counts.get("defend_completed", 0)
    sample_note = None
    if started < 10:
        sample_note = "Small sample — rates are directional signals only."

    # Median wall times for submitted sessions (exclude infra-blocked where set)
    sess = (
        await db.execute(
            select(InterviewSession).where(InterviewSession.status == "submitted")
        )
    ).scalars().all()
    times: list[float] = []
    for s in sess:
        ms = s.active_duration_ms
        if ms is None and s.wall_duration_ms is not None:
            blocked = s.infra_blocked_ms or 0
            ms = max(0, (s.wall_duration_ms or 0) - blocked)
        if ms is None and s.started_at and s.submitted_at:
            ms = int((s.submitted_at - s.started_at).total_seconds() * 1000)
            if s.infra_blocked_ms:
                ms = max(0, ms - s.infra_blocked_ms)
        if ms is not None and ms > 0:
            times.append(ms / 60000.0)

    return {
        "counts": counts,
        "rates": {
            "signup_to_session_pct": _pct(started, signed_up),
            "completion_pct": _pct(submitted, started),
            "report_view_pct": _pct(reports, submitted),
            "defend_pct": _pct(defend, submitted),
        },
        "median_session_minutes": round(median(times), 2) if times else None,
        "sample_note": sample_note,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


async def challenge_quality_metrics(db: AsyncSession) -> list[dict[str, Any]]:
    sessions = (await db.execute(select(InterviewSession))).scalars().all()
    evals = {
        e.session_id: e
        for e in (await db.execute(select(InterviewEvaluation))).scalars().all()
    }
    by_slug: dict[str, list[InterviewSession]] = defaultdict(list)
    for s in sessions:
        by_slug[s.challenge_slug].append(s)

    out: list[dict[str, Any]] = []
    for slug, items in sorted(by_slug.items()):
        attempts = len(items)
        submitted = [s for s in items if s.status == "submitted"]
        abandoned = [s for s in items if s.status in {"expired", "failed"} or s.abandon_reason]
        scores: list[float] = []
        times: list[float] = []
        ratings: list[float] = []
        runner_fail = 0
        ai_fail = 0
        for s in items:
            tags = s.infra_failure_tags or []
            if any(t.startswith("runner") or t == "docker" for t in tags):
                runner_fail += 1
            if any(t.startswith("ai") for t in tags):
                ai_fail += 1
            if s.feedback_realism:
                ratings.append(float(s.feedback_realism))
            if s.feedback_difficulty:
                ratings.append(float(s.feedback_difficulty))
            ev = evals.get(s.id)
            if ev:
                scores.append(float(ev.total_score))
            if s.submitted_at and s.started_at:
                ms = s.active_duration_ms
                if ms is None:
                    ms = int((s.submitted_at - s.started_at).total_seconds() * 1000)
                    if s.infra_blocked_ms:
                        ms = max(0, ms - s.infra_blocked_ms)
                times.append(ms / 60000.0)
        out.append(
            {
                "challenge_slug": slug,
                "attempts": attempts,
                "completion_pct": _pct(len(submitted), attempts),
                "abandon_pct": _pct(len(abandoned), attempts),
                "score_distribution": _dist(scores),
                "time_minutes_distribution": _dist(times),
                "feedback_rating_distribution": _dist(ratings),
                "runner_fail_rate_pct": _pct(runner_fail, attempts),
                "ai_fail_rate_pct": _pct(ai_fail, attempts),
                "note": "Signals only — not auto-conclusions.",
            }
        )
    return out
