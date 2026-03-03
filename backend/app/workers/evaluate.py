"""Background worker that runs the full evaluation pipeline for a submission."""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.challenge import Challenge
from app.models.leaderboard import LeaderboardEntry
from app.models.run import Run
from app.models.submission import Submission
from app.services.evaluation.ai_judge import ai_judge_evaluate

logger = logging.getLogger(__name__)


async def run_evaluation_pipeline(submission_id: str) -> None:
    """Entry point called from BackgroundTasks.

    Loads the submission, runs evaluation, persists scores and report.
    """
    async with async_session_factory() as db:
        try:
            await _evaluate(db, submission_id)
        except Exception:
            logger.exception("Evaluation pipeline failed for submission %s", submission_id)
            await _mark_failed(db, submission_id)


async def _evaluate(db: AsyncSession, submission_id: str) -> None:
    sid = _uuid.UUID(submission_id) if isinstance(submission_id, str) else submission_id
    submission = await db.get(Submission, sid)
    if not submission:
        logger.error("Submission %s not found", submission_id)
        return

    challenge = await db.get(Challenge, submission.challenge_id)
    if not challenge:
        logger.error("Challenge %s not found", submission.challenge_id)
        return

    submission.status = "running"
    await db.commit()

    eval_config = {**challenge.config}
    eval_config.setdefault("description", challenge.description)

    result = ai_judge_evaluate(
        code=submission.code,
        entrypoint=submission.entrypoint,
        challenge_config=eval_config,
    )

    report = result.to_report(submission_id)

    submission.status = "completed"
    submission.report = report
    submission.score_accuracy = result.accuracy
    submission.score_prompt_quality = result.prompt_quality
    submission.score_efficiency = result.efficiency
    submission.score_reliability = result.reliability
    submission.score_orchestration = result.orchestration
    submission.score_code_quality = result.code_quality
    submission.score_rule_adherence = result.rule_adherence
    submission.score_edge_cases = result.edge_case_handling
    submission.score_overall = result.overall
    submission.total_cost_usd = result.cost_usd
    submission.total_latency_ms = result.latency_ms
    submission.total_llm_calls = result.llm_calls
    submission.completed_at = datetime.now(timezone.utc)

    # Persist individual run records
    for run_data in result.runs:
        run = Run(
            submission_id=submission.id,
            run_type=run_data.get("run_type", "ai_judge"),
            run_index=run_data.get("run_index", 0),
            status="success" if run_data.get("success") else "error",
            output={"feedback": run_data.get("feedback", ""), "accuracy_reasoning": run_data.get("accuracy_reasoning", "")},
            telemetry=None,
            tokens_total=run_data.get("tokens_total", 0),
            cost_usd=run_data.get("cost_usd", 0.0),
            latency_ms=run_data.get("latency_ms", 0.0),
            llm_calls=run_data.get("llm_calls", 0),
            retries=run_data.get("retries", 0),
            accuracy=run_data.get("accuracy", 0.0),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        db.add(run)

    await _upsert_leaderboard(db, submission)
    await db.commit()

    logger.info(
        "Submission %s evaluated: overall=%.4f prompt_quality=%.4f accuracy=%.4f",
        submission_id,
        result.overall,
        result.prompt_quality,
        result.accuracy,
    )


async def _upsert_leaderboard(db: AsyncSession, submission: Submission) -> None:
    result = await db.execute(
        select(LeaderboardEntry).where(
            LeaderboardEntry.challenge_id == submission.challenge_id,
            LeaderboardEntry.user_id == submission.user_id,
        )
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        entry = LeaderboardEntry(
            challenge_id=submission.challenge_id,
            user_id=submission.user_id,
            submission_id=submission.id,
        )
        db.add(entry)

    if submission.score_overall and (
        entry.score_overall is None or submission.score_overall > entry.score_overall
    ):
        entry.submission_id = submission.id
        entry.score_overall = submission.score_overall
        entry.score_accuracy = submission.score_accuracy or 0.0
        entry.score_prompt_quality = submission.score_prompt_quality or 0.0
        entry.score_efficiency = submission.score_efficiency or 0.0
        entry.score_reliability = submission.score_reliability or 0.0
        entry.score_orchestration = submission.score_orchestration or 0.0
        entry.score_code_quality = submission.score_code_quality or 0.0
        entry.score_rule_adherence = submission.score_rule_adherence or 0.0
        entry.score_edge_cases = submission.score_edge_cases or 0.0
        entry.total_cost_usd = submission.total_cost_usd or 0.0
        entry.total_llm_calls = submission.total_llm_calls or 0


async def _mark_failed(db: AsyncSession, submission_id: str) -> None:
    sid = _uuid.UUID(submission_id) if isinstance(submission_id, str) else submission_id
    submission = await db.get(Submission, sid)
    if submission:
        submission.status = "failed"
        await db.commit()
