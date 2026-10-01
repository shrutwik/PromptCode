#!/usr/bin/env python3
"""List / disable / enable beta users (CLI)."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db.session import async_session_factory  # noqa: E402
from app.models.user import User  # noqa: E402


async def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    d = sub.add_parser("disable")
    d.add_argument("user_id")
    e = sub.add_parser("enable")
    e.add_argument("user_id")
    args = p.parse_args()

    async with async_session_factory() as db:
        if args.cmd == "list":
            users = (await db.execute(select(User).order_by(User.created_at.desc()).limit(100))).scalars().all()
            for u in users:
                print(
                    f"{u.id}\t{u.email}\t{u.username}\t{u.beta_status}\t"
                    f"{u.beta_cohort}\t{u.signup_source}\t{u.created_at}"
                )
            return 0
        uid = uuid.UUID(args.user_id)
        user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user is None:
            print("not found", file=sys.stderr)
            return 1
        user.beta_status = "disabled" if args.cmd == "disable" else "active"
        await db.commit()
        print(f"{user.id}\t{user.beta_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
