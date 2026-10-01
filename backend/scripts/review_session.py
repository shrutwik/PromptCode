#!/usr/bin/env python3
"""CLI session review for calibration (uses DB directly)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import async_session_factory  # noqa: E402
from app.services.interview.calibration import session_review_payload  # noqa: E402


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("session_id")
    args = p.parse_args()
    sid = uuid.UUID(args.session_id)
    async with async_session_factory() as db:
        payload = await session_review_payload(db, sid)
    if payload is None:
        print("not found", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
