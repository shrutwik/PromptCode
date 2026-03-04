"""Backfill candidate growth/mastery/coaching fields for completed submissions.

Usage:
    cd backend && python -m scripts.backfill_growth_metrics --dry-run
    cd backend && python -m scripts.backfill_growth_metrics
"""

from __future__ import annotations

import argparse
from types import SimpleNamespace

from sqlalchemy import select

from app.db.session import async_session_factory, engine
from app.models.submission import Submission
from app.workers.evaluate import (
    _build_coaching,
    _compute_growth,
    _derive_mastery_state,
)


def _submission_as_result_like(submission: Submission) -> SimpleNamespace:
    return SimpleNamespace(
        overall=submission.score_overall or 0.0,
        accuracy=submission.score_accuracy or 0.0,
        edge_case_handling=submission.score_edge_cases or 0.0,
        efficiency=submission.score_efficiency or 0.0,
        reliability=submission.score_reliability or 0.0,
        orchestration=submission.score_orchestration or 0.0,
    )


async def run_backfill(*, dry_run: bool, limit: int | None) -> None:
    async with async_session_factory() as db:
        query = (
            select(Submission)
            .where(Submission.status == "completed")
            .order_by(
                Submission.user_id.asc(),
                Submission.challenge_id.asc(),
                Submission.completed_at.asc(),
                Submission.created_at.asc(),
            )
        )
        if limit is not None and limit > 0:
            query = query.limit(limit)
        result = await db.execute(query)
        submissions = result.scalars().all()

        updated = 0
        group_history: dict[tuple[str, str], list[Submission]] = {}

        for submission in submissions:
            key = (str(submission.user_id), str(submission.challenge_id))
            history = group_history.get(key, [])
            previous = history[-1] if history else None
            current_like = _submission_as_result_like(submission)
            recent_history = list(reversed(history[-4:]))

            growth = _compute_growth(previous=previous, current=current_like)
            mastery_state = _derive_mastery_state(current=current_like, history=recent_history)
            coaching = _build_coaching(
                result=current_like,
                growth=growth,
                mastery_state=mastery_state,
                previous=previous,
            )

            submission.delta_overall = growth.get("delta_overall")
            submission.delta_accuracy = growth.get("delta_accuracy")
            submission.delta_robustness = growth.get("delta_robustness")
            submission.delta_efficiency = growth.get("delta_efficiency")
            submission.growth_score = growth.get("growth_score")
            submission.mastery_state = mastery_state

            report = dict(submission.report or {})
            report["growth"] = growth
            report["mastery_state"] = mastery_state
            report["coaching"] = coaching
            submission.report = report

            updated += 1
            history.append(submission)
            group_history[key] = history

        if dry_run:
            await db.rollback()
            print(f"[dry-run] would update {updated} completed submissions")
        else:
            await db.commit()
            print(f"updated {updated} completed submissions")

    await engine.dispose()


async def _main_async(args: argparse.Namespace) -> None:
    await run_backfill(dry_run=args.dry_run, limit=args.limit)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print count without committing DB changes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of completed submissions to process.",
    )
    args = parser.parse_args()

    import asyncio

    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
