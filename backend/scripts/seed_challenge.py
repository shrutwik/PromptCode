"""Seed all challenges into the database.

Usage:
    cd backend && python -m scripts.seed_challenge
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.db.base import Base
from app.db.session import async_session_factory, engine
from app.models.challenge import Challenge

CHALLENGES_DIR = Path(__file__).resolve().parent.parent.parent / "challenges"


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    challenge_dirs = sorted(
        d for d in CHALLENGES_DIR.iterdir()
        if d.is_dir() and (d / "challenge.json").exists()
    )

    if not challenge_dirs:
        print(f"No challenge.json files found in {CHALLENGES_DIR}")
        return

    print(f"Found {len(challenge_dirs)} challenges to seed.\n")

    async with async_session_factory() as db:
        seeded = 0
        skipped = 0

        for challenge_dir in challenge_dirs:
            data = json.loads((challenge_dir / "challenge.json").read_text())

            existing = await db.execute(
                select(Challenge).where(Challenge.slug == data["slug"])
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP  {data['slug']} (already exists)")
                skipped += 1
                continue

            challenge = Challenge(
                slug=data["slug"],
                title=data["title"],
                description=data["description"],
                difficulty=data.get("difficulty", "medium"),
                category=data.get("category", "extraction"),
                tags=data.get("tags", []),
                company_context=data.get("company_context", ""),
                input_format=data.get("input_format", "text"),
                output_format=data.get("output_format", "json"),
                constraints=data.get("constraints"),
                sample_input=data.get("sample_input"),
                sample_output=data.get("sample_output"),
                config=data["config"],
            )
            db.add(challenge)
            print(f"  SEED  {data['slug']} — {data['title']}")
            seeded += 1

        await db.commit()

    await engine.dispose()
    print(f"\nDone: {seeded} seeded, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
