#!/usr/bin/env python3
"""Create private-beta invite codes (CLI — no admin UI)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import async_session_factory  # noqa: E402
from app.services.interview.beta_access import create_invite  # noqa: E402


async def main() -> int:
    p = argparse.ArgumentParser(description="Create PromptCode beta invite code")
    p.add_argument("--cohort", default="beta")
    p.add_argument("--max-uses", type=int, default=1)
    p.add_argument("--note", default="")
    p.add_argument("--code", default=None, help="Optional fixed code")
    p.add_argument("--created-by", default="cli")
    args = p.parse_args()

    async with async_session_factory() as db:
        invite = await create_invite(
            db,
            cohort=args.cohort,
            max_uses=args.max_uses,
            note=args.note or None,
            created_by=args.created_by,
            code=args.code,
        )
    print(f"code={invite.code} cohort={invite.cohort} max_uses={invite.max_uses} id={invite.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
