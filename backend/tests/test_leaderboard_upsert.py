from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.models.challenge import Challenge
from app.models.leaderboard import LeaderboardEntry
from app.models.submission import Submission
from app.models.user import User
from app.workers.evaluate import _upsert_leaderboard


def test_leaderboard_keeps_single_row_per_user_and_challenge():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as db:
            user = User(
                email="leaderboard@example.com",
                username="leaderboard",
                password_hash="hashed",
            )
            challenge = Challenge(
                slug="leaderboard-challenge",
                title="Leaderboard Challenge",
                description="Test",
                category="test",
                config={},
            )
            db.add_all([user, challenge])
            await db.flush()

            report = {
                "tests_total": 8,
                "disqualified": False,
                "credibility": {"score": 0.9},
                "prompt_quality_details": {"method": "llm_judge"},
                "ai_leverage": {
                    "leverage_gain": 0.04,
                    "signals": {"counterfactual": {"status": "ok"}},
                },
            }

            low = Submission(
                challenge_id=challenge.id,
                user_id=user.id,
                status="completed",
                code="print('low')",
                entrypoint="main.py",
                report=report,
                score_overall=0.61,
                score_accuracy=0.6,
                score_prompt_quality=0.6,
                score_efficiency=0.6,
                score_reliability=0.8,
                score_orchestration=0.6,
                score_code_quality=0.6,
                score_rule_adherence=0.7,
                score_edge_cases=0.6,
                total_cost_usd=0.02,
                total_llm_calls=4,
            )
            high = Submission(
                challenge_id=challenge.id,
                user_id=user.id,
                status="completed",
                code="print('high')",
                entrypoint="main.py",
                report=report,
                score_overall=0.79,
                score_accuracy=0.8,
                score_prompt_quality=0.8,
                score_efficiency=0.7,
                score_reliability=0.85,
                score_orchestration=0.75,
                score_code_quality=0.7,
                score_rule_adherence=0.8,
                score_edge_cases=0.76,
                total_cost_usd=0.03,
                total_llm_calls=5,
            )
            db.add_all([low, high])
            await db.flush()

            await _upsert_leaderboard(db, low)
            await _upsert_leaderboard(db, high)
            await db.commit()

            rows = (
                await db.execute(
                    select(LeaderboardEntry).where(
                        LeaderboardEntry.challenge_id == challenge.id,
                        LeaderboardEntry.user_id == user.id,
                    )
                )
            ).scalars().all()

            assert len(rows) == 1
            assert rows[0].submission_id == high.id
            assert rows[0].score_overall == 0.79

        await engine.dispose()

    asyncio.run(_run())
