from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import Insert as PostgreSQLInsert
from sqlalchemy.dialects.sqlite import Insert as SQLiteInsert
from sqlalchemy.ext.asyncio import AsyncSession


def limit_from_env(name: str, default: int) -> int:
    """Read a positive integer limit from the environment, otherwise use default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 1 else default


async def enforce_rate_limit(*, db: AsyncSession, key: str, limit: int,
                             window_seconds: int, now: datetime | None = None) -> None:
    """Atomic fixed-window counter; no advisory lock or event-table scan."""
    import hashlib
    import hmac

    from app.core.config import get_settings
    from app.models.rate_limit_counter import RateLimitCounter
    if limit < 1 or window_seconds < 1:
        raise HTTPException(503, "Invalid rate limit configuration")
    current = int((now or datetime.now(timezone.utc)).timestamp())
    bucket = current // window_seconds * window_seconds
    hashed = hmac.new(get_settings().jwt_secret.encode(), key.encode(), hashlib.sha256).hexdigest()
    dialect = db.get_bind().dialect.name
    stmt: PostgreSQLInsert | SQLiteInsert
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(RateLimitCounter)
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        stmt = sqlite_insert(RateLimitCounter)
    else:
        raise HTTPException(503, "Rate limiter unavailable")
    stmt = stmt.values(key=hashed, window_start=bucket, count=1,
                                         expires_at=bucket + window_seconds)
    returning = stmt.on_conflict_do_update(index_elements=[RateLimitCounter.key, RateLimitCounter.window_start],
                                     set_={"count": RateLimitCounter.count + 1},
                                     where=RateLimitCounter.count < limit).returning(RateLimitCounter.count)
    accepted = (await db.execute(returning)).scalar_one_or_none()
    await db.commit()
    if accepted is None:
        retry = max(1, bucket + window_seconds - current)
        raise HTTPException(429, "Rate limit exceeded. Please retry later.", headers={"Retry-After": str(retry)})


async def cleanup_expired_counters(*, db: AsyncSession, now: datetime | None = None) -> None:
    """Prune expired windows in a background transaction; the caller commits."""
    from sqlalchemy import delete

    from app.models.rate_limit_counter import RateLimitCounter

    current = int((now or datetime.now(timezone.utc)).timestamp())
    await db.execute(delete(RateLimitCounter).where(RateLimitCounter.expires_at <= current))
