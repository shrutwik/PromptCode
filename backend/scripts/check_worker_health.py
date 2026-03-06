"""Check whether this worker is publishing a fresh heartbeat."""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine


def _worker_id() -> str:
    settings = get_settings()
    configured = str(settings.worker_id or "").strip()
    return configured or socket.gethostname()


async def _is_worker_healthy() -> bool:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=max(1, settings.worker_heartbeat_timeout_seconds)
    )
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT worker_id
                FROM worker_heartbeats
                WHERE worker_id = :worker_id
                  AND last_seen_at >= :cutoff
                LIMIT 1
                """
            ),
            {"worker_id": _worker_id(), "cutoff": cutoff},
        )
        return result.first() is not None


def main() -> None:
    try:
        healthy = asyncio.run(_is_worker_healthy())
    except Exception:
        healthy = False
    if not healthy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
