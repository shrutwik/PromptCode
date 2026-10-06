"""Interview session lifecycle helpers — TTL, status gates, attempt numbers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.interview_session import InterviewSession

SESSION_STATUSES = frozenset({"created", "active", "submitted", "expired", "failed", "abandoned"})
MUTABLE_STATUSES = frozenset({"created", "active"})
READ_STATUSES = frozenset({"created", "active", "submitted", "expired", "failed", "abandoned"})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_expires_at(started_at: datetime | None = None) -> datetime:
    settings = get_settings()
    hours = max(1, int(getattr(settings, "session_ttl_hours", 24) or 24))
    base = started_at or utcnow()
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(hours=hours)


async def next_attempt_number(
    db: AsyncSession, *, user_id, challenge_slug: str
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.challenge_slug == challenge_slug,
        )
    )
    return int(result.scalar_one() or 0) + 1


def maybe_expire_session(session: InterviewSession) -> bool:
    """Transition active/created → expired when TTL elapsed. Returns True if expired now."""
    if session.status in {"submitted", "expired", "failed", "abandoned"}:
        return session.status == "expired"
    expires_at = session.expires_at
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if utcnow() >= expires_at:
        stop_timer(session, now=expires_at)
        session.status = "expired"
        return True
    return False


def require_mutable(session: InterviewSession) -> None:
    maybe_expire_session(session)
    if session.status == "expired":
        raise HTTPException(
            status_code=410,
            detail="Session expired. Report and history remain available if submitted earlier.",
        )
    if session.status == "submitted":
        raise HTTPException(
            status_code=409,
            detail="Session already submitted. Code is immutable.",
        )
    if session.status == "failed":
        raise HTTPException(status_code=409, detail="Session failed and cannot be modified.")
    if session.status not in MUTABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Session is not editable.")


def require_readable(session: InterviewSession) -> None:
    maybe_expire_session(session)
    if session.status not in READ_STATUSES:
        raise HTTPException(status_code=404, detail="Session not found")


TIMER_LEASE_SECONDS = 30


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def timer_snapshot(session: InterviewSession, *, now: datetime | None = None) -> tuple[int, int]:
    """Return elapsed time and remaining editor lease in milliseconds."""
    now = _aware(now or utcnow())
    elapsed = getattr(session, "timer_elapsed_ms", None)
    if elapsed is None:  # Compatibility for rows created before the timer migration.
        elapsed = getattr(session, "active_duration_ms", None)
        if elapsed is None:
            started = getattr(session, "started_at", None)
            end = getattr(session, "submitted_at", None) or now
            expiry = getattr(session, "expires_at", None)
            if expiry is not None:
                end = min(_aware(end), _aware(expiry))
            elapsed = max(0, int((_aware(end) - _aware(started)).total_seconds() * 1000)) if started else 0
    last = getattr(session, "timer_last_seen_at", None)
    if last is None or session.status not in MUTABLE_STATUSES:
        return max(0, elapsed), 0
    delta = max(0, int((now - _aware(last)).total_seconds() * 1000))
    lease = TIMER_LEASE_SECONDS * 1000
    if session.expires_at is not None:
        delta = min(delta, max(0, int((_aware(session.expires_at) - _aware(last)).total_seconds() * 1000)))
    return max(0, elapsed) + min(delta, lease), max(0, lease - delta)


def stop_timer(session: InterviewSession, *, now: datetime | None = None) -> None:
    session.timer_elapsed_ms = timer_snapshot(session, now=now)[0]
    session.timer_last_seen_at = None
    session.timer_editor_token = None


def require_editor(session: InterviewSession, token: str | None) -> None:
    """Older API clients remain supported unless an editor currently owns the lease."""
    _, remaining = timer_snapshot(session)
    if remaining and getattr(session, "timer_editor_token", None) != token:
        raise HTTPException(409, "This session is open for editing in another tab or device.")
    if token and (not remaining or getattr(session, "timer_editor_token", None) != token):
        raise HTTPException(409, "Session paused. Resume before editing.")


def update_timer(session: InterviewSession, action: str, token: str) -> None:
    require_mutable(session)
    now = utcnow()
    elapsed, remaining = timer_snapshot(session, now=now)
    if remaining and getattr(session, "timer_editor_token", None) != token:
        raise HTTPException(409, "This session is open for editing in another tab or device.")
    # A delayed pause from a previous tab must never pause a new editor.
    if action == "pause":
        if session.timer_editor_token == token:
            stop_timer(session, now=now)
        return
    if action == "heartbeat" and (not remaining or getattr(session, "timer_editor_token", None) != token):
        raise HTTPException(409, "Session paused. Resume before editing.")
    session.timer_elapsed_ms = elapsed
    session.timer_last_seen_at = now
    session.timer_editor_token = token
