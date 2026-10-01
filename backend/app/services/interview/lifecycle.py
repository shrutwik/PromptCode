"""Interview session lifecycle helpers — TTL, status gates, attempt numbers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.interview_session import InterviewSession

SESSION_STATUSES = frozenset({"created", "active", "submitted", "expired", "failed"})
MUTABLE_STATUSES = frozenset({"created", "active"})
READ_STATUSES = frozenset({"created", "active", "submitted", "expired", "failed"})


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
    if session.status in {"submitted", "expired", "failed"}:
        return session.status == "expired"
    expires_at = session.expires_at
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if utcnow() >= expires_at:
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
