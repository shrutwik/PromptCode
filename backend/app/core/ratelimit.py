from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_rate_limit import AuthRateLimitEvent


async def enforce_rate_limit(
    *,
    db: AsyncSession,
    key: str,
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
) -> None:
    """Persist a sliding-window rate limit so it survives restarts and shared workers."""
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(seconds=window_seconds)

    await db.execute(
        delete(AuthRateLimitEvent).where(
            AuthRateLimitEvent.client_key == key,
            AuthRateLimitEvent.created_at < cutoff,
        )
    )
    count_result = await db.execute(
        select(func.count())
        .select_from(AuthRateLimitEvent)
        .where(AuthRateLimitEvent.client_key == key)
    )
    count = int(count_result.scalar_one() or 0)
    if count >= limit:
        await db.commit()
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry in {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )

    db.add(AuthRateLimitEvent(client_key=key, created_at=current_time))
    await db.commit()
