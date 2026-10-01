#!/usr/bin/env python3
"""Expire due interview sessions and clean orphan/expired workspaces + Docker leftovers.

Usage (from repo root or backend/):
  python backend/scripts/cleanup_interview_sessions.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


async def main() -> int:
    from app.db.session import async_session_factory
    from app.services.interview.cleanup import cleanup_interview_resources

    async with async_session_factory() as db:
        report = await cleanup_interview_resources(db)
    print(
        "cleanup ok "
        f"expired={report.expired_sessions} "
        f"workspaces={report.workspaces_removed} "
        f"starters={report.starters_removed} "
        f"orphans={report.orphan_dirs_removed} "
        f"containers={report.containers_removed}"
    )
    if report.errors:
        for err in report.errors:
            print("error:", err)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
