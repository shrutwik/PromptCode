"""Background worker that runs the full evaluation pipeline for a submission."""

from __future__ import annotations

import difflib
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.challenge import Challenge
from app.models.leaderboard import LeaderboardEntry
from app.models.run import Run
from app.models.submission import Submission
from app.services.evaluation.engine import evaluate_submission
from app.services.evaluation.scorer import score_ai_mastery
from app.services.evaluation.weight_profile import get_weight_profile

logger = logging.getLogger(__name__)
MIN_LEADERBOARD_TESTS = 6
MIN_LEADERBOARD_RELIABILITY = 0.55
MIN_LEADERBOARD_CREDIBILITY = 0.65
REQUIRE_LLM_PROMPT_JUDGE = True
REQUIRE_COUNTERFACTUAL_BASELINE = True
MIN_LEADERBOARD_LEVERAGE_GAIN = 0.0


async def run_evaluation_pipeline(submission_id: str) -> bool:
    """Entry point called from BackgroundTasks.

    Loads the submission, runs evaluation, persists scores and report.
    """
    async with async_session_factory() as db:
        try:
            await _evaluate(db, submission_id)
            return True
        except Exception:
            logger.exception("Evaluation pipeline failed for submission %s", submission_id)
            await _mark_failed(db, submission_id)
            return False


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
    eval_config.setdefault("challenge_slug", challenge.slug)
    eval_config.setdefault("challenge_title", challenge.title)
    eval_config.setdefault("challenge_category", challenge.category)

    result = await evaluate_submission(
        code=submission.code,
        entrypoint=submission.entrypoint,
        challenge_config=eval_config,
    )

    report = result.to_report(submission_id)
    previous = await _get_previous_completed_submission(db, submission)
    recent_history = await _get_recent_completed_submissions(db, submission, limit=4)
    growth = _compute_growth(previous=previous, current=result)
    mastery_state = _derive_mastery_state(current=result, history=recent_history)
    coaching = _build_coaching(
        result=result,
        growth=growth,
        mastery_state=mastery_state,
        previous=previous,
    )
    iteration_diff = _build_iteration_diff(
        previous=previous,
        current=submission,
        growth=growth,
    )
    ai_leverage = _enrich_ai_leverage(
        ai_leverage=report.get("ai_leverage", {}),
        growth=growth,
        iteration_diff=iteration_diff,
        prompt_quality=float(result.prompt_quality),
    )
    learning_effectiveness = _compute_learning_effectiveness(
        previous=previous,
        current=result,
        current_ai_leverage=ai_leverage,
    )
    future_feedback = _build_future_feedback(
        result=result,
        ai_leverage=ai_leverage,
        credibility=report.get("credibility") or {},
        learning_effectiveness=learning_effectiveness,
        growth=growth,
    )
    coaching_actions = _build_coaching_actions(
        result=result,
        growth=growth,
        runs=result.runs,
        diagnostics=result.diagnostics,
        iteration_diff=iteration_diff,
        ai_leverage=ai_leverage,
    )
    report["growth"] = growth
    report["coaching"] = coaching
    report["iteration_diff"] = iteration_diff
    report["coaching_actions"] = coaching_actions
    report["mastery_state"] = mastery_state
    report["ai_leverage"] = ai_leverage
    report["learning_effectiveness"] = learning_effectiveness
    report["future_feedback"] = future_feedback

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
    submission.delta_overall = growth.get("delta_overall")
    submission.delta_accuracy = growth.get("delta_accuracy")
    submission.delta_robustness = growth.get("delta_robustness")
    submission.delta_efficiency = growth.get("delta_efficiency")
    submission.growth_score = growth.get("growth_score")
    submission.mastery_state = mastery_state
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
            status=run_data.get("status", "fail"),
            output={
                "feedback": run_data.get("feedback", ""),
                "error": run_data.get("error"),
            },
            telemetry=run_data.get("meta"),
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
    if not _eligible_for_leaderboard(submission):
        logger.info(
            "Submission %s skipped for leaderboard eligibility gates",
            submission.id,
        )
        return

    if submission.score_overall is None:
        return

    values = {
        "id": _uuid.uuid4(),
        "challenge_id": submission.challenge_id,
        "user_id": submission.user_id,
        "submission_id": submission.id,
        "score_overall": submission.score_overall,
        "score_accuracy": submission.score_accuracy or 0.0,
        "score_prompt_quality": submission.score_prompt_quality or 0.0,
        "score_efficiency": submission.score_efficiency or 0.0,
        "score_reliability": submission.score_reliability or 0.0,
        "score_orchestration": submission.score_orchestration or 0.0,
        "score_code_quality": submission.score_code_quality or 0.0,
        "score_rule_adherence": submission.score_rule_adherence or 0.0,
        "score_edge_cases": submission.score_edge_cases or 0.0,
        "total_cost_usd": submission.total_cost_usd or 0.0,
        "total_llm_calls": submission.total_llm_calls or 0,
        "updated_at": datetime.now(timezone.utc),
    }

    bind = db.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        insert_stmt = pg_insert(LeaderboardEntry).values(**values)
    elif dialect_name == "sqlite":
        insert_stmt = sqlite_insert(LeaderboardEntry).values(**values)
    else:
        result = await db.execute(
            select(LeaderboardEntry).where(
                LeaderboardEntry.challenge_id == submission.challenge_id,
                LeaderboardEntry.user_id == submission.user_id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            entry = LeaderboardEntry(**values)
            db.add(entry)
            return
        if entry.score_overall is None or submission.score_overall > entry.score_overall:
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
            entry.updated_at = values["updated_at"]
        return

    update_values = {
        "submission_id": submission.id,
        "score_overall": submission.score_overall,
        "score_accuracy": submission.score_accuracy or 0.0,
        "score_prompt_quality": submission.score_prompt_quality or 0.0,
        "score_efficiency": submission.score_efficiency or 0.0,
        "score_reliability": submission.score_reliability or 0.0,
        "score_orchestration": submission.score_orchestration or 0.0,
        "score_code_quality": submission.score_code_quality or 0.0,
        "score_rule_adherence": submission.score_rule_adherence or 0.0,
        "score_edge_cases": submission.score_edge_cases or 0.0,
        "total_cost_usd": submission.total_cost_usd or 0.0,
        "total_llm_calls": submission.total_llm_calls or 0,
        "updated_at": values["updated_at"],
    }

    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["challenge_id", "user_id"],
        set_=update_values,
        where=insert_stmt.excluded.score_overall > LeaderboardEntry.score_overall,
    )
    await db.execute(upsert_stmt)


def _eligible_for_leaderboard(submission: Submission) -> bool:
    if submission.status != "completed":
        return False
    if submission.score_overall is None:
        return False
    if (submission.score_reliability or 0.0) < MIN_LEADERBOARD_RELIABILITY:
        return False
    report = submission.report or {}
    if report.get("disqualified"):
        return False
    tests_total = int(report.get("tests_total") or 0)
    if tests_total < MIN_LEADERBOARD_TESTS:
        return False
    credibility = report.get("credibility") or {}
    if float(credibility.get("score") or 0.0) < MIN_LEADERBOARD_CREDIBILITY:
        return False
    prompt_details = report.get("prompt_quality_details") or {}
    if REQUIRE_LLM_PROMPT_JUDGE and str(prompt_details.get("method") or "") != "llm_judge":
        return False
    ai_leverage = report.get("ai_leverage") or {}
    baseline_status = str(((ai_leverage.get("signals") or {}).get("counterfactual") or {}).get("status") or "")
    if REQUIRE_COUNTERFACTUAL_BASELINE and baseline_status != "ok":
        return False
    leverage_gain = ai_leverage.get("leverage_gain")
    if leverage_gain is None:
        return False
    if float(leverage_gain) < MIN_LEADERBOARD_LEVERAGE_GAIN:
        return False
    return True


async def _mark_failed(db: AsyncSession, submission_id: str) -> None:
    sid = _uuid.UUID(submission_id) if isinstance(submission_id, str) else submission_id
    submission = await db.get(Submission, sid)
    if submission:
        submission.status = "failed"
        await db.commit()


async def _get_previous_completed_submission(
    db: AsyncSession,
    submission: Submission,
) -> Submission | None:
    result = await db.execute(
        select(Submission)
        .where(
            Submission.user_id == submission.user_id,
            Submission.challenge_id == submission.challenge_id,
            Submission.status == "completed",
            Submission.id != submission.id,
        )
        .order_by(Submission.completed_at.desc(), Submission.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_recent_completed_submissions(
    db: AsyncSession,
    submission: Submission,
    *,
    limit: int = 4,
) -> list[Submission]:
    result = await db.execute(
        select(Submission)
        .where(
            Submission.user_id == submission.user_id,
            Submission.challenge_id == submission.challenge_id,
            Submission.status == "completed",
            Submission.id != submission.id,
        )
        .order_by(Submission.completed_at.desc(), Submission.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


def _compute_growth(*, previous: Submission | None, current: Any) -> dict[str, Any]:
    if not previous:
        return {
            "previous_submission_id": None,
            "delta_overall": None,
            "delta_accuracy": None,
            "delta_robustness": None,
            "delta_efficiency": None,
            "growth_score": 0.5,
            "status": "first_attempt",
        }

    def _delta(cur: float | None, prev: float | None) -> float | None:
        if cur is None or prev is None:
            return None
        return round(cur - prev, 4)

    d_overall = _delta(current.overall, previous.score_overall)
    d_accuracy = _delta(current.accuracy, previous.score_accuracy)
    d_robustness = _delta(current.edge_case_handling, previous.score_edge_cases)
    d_eff = _delta(current.efficiency, previous.score_efficiency)

    weighted: list[tuple[float, float]] = [
        (d_overall, 0.4),
        (d_accuracy, 0.2),
        (d_robustness, 0.2),
        (d_eff, 0.2),
    ]
    norm_values: list[tuple[float, float]] = []
    for delta, weight in weighted:
        if delta is None:
            continue
        normalized = max(0.0, min(1.0, (delta + 0.15) / 0.30))
        norm_values.append((normalized, weight))

    if norm_values:
        weight_sum = sum(w for _, w in norm_values)
        growth_score = sum(v * w for v, w in norm_values) / weight_sum
    else:
        growth_score = 0.5

    improved = any((d or 0.0) > 0 for d in [d_overall, d_accuracy, d_robustness, d_eff])
    regressed = any((d or 0.0) < -0.02 for d in [d_overall, d_accuracy, d_robustness, d_eff])
    status = "improved" if improved and not regressed else ("mixed" if improved and regressed else ("regressed" if regressed else "flat"))

    return {
        "previous_submission_id": str(previous.id),
        "delta_overall": d_overall,
        "delta_accuracy": d_accuracy,
        "delta_robustness": d_robustness,
        "delta_efficiency": d_eff,
        "growth_score": round(growth_score, 4),
        "status": status,
    }


def _derive_mastery_state(*, current: Any, history: list[Submission]) -> str:
    window = [current] + history[:2]
    overall_vals = [float(x.overall if hasattr(x, "overall") else x.score_overall or 0.0) for x in window]
    rel_vals = [float(x.reliability if hasattr(x, "reliability") else x.score_reliability or 0.0) for x in window]
    robust_vals = [float(x.edge_case_handling if hasattr(x, "edge_case_handling") else x.score_edge_cases or 0.0) for x in window]

    n = len(window)
    avg_overall = sum(overall_vals) / n if n else 0.0
    avg_rel = sum(rel_vals) / n if n else 0.0
    avg_robust = sum(robust_vals) / n if n else 0.0

    if n >= 3 and avg_overall >= 0.82 and avg_rel >= 0.65 and avg_robust >= 0.75:
        return "mastered"
    if avg_overall >= 0.68 and avg_rel >= 0.55:
        return "proficient"
    return "practicing"


def _build_coaching(
    *,
    result: Any,
    growth: dict[str, Any],
    mastery_state: str,
    previous: Submission | None,
) -> dict[str, Any]:
    improved: list[str] = []
    regressed: list[str] = []

    metric_map = [
        ("delta_overall", "overall"),
        ("delta_accuracy", "accuracy"),
        ("delta_robustness", "robustness"),
        ("delta_efficiency", "efficiency"),
    ]
    for key, label in metric_map:
        delta = growth.get(key)
        if delta is None:
            continue
        if delta > 0.01:
            improved.append(label)
        elif delta < -0.01:
            regressed.append(label)

    next_focus = "accuracy"
    explanation = "Tighten extraction/output constraints and validation."
    priorities = [
        ("accuracy", float(result.accuracy), 0.85, "Add stricter extraction instructions and deterministic output formatting."),
        ("robustness", float(result.edge_case_handling), 0.75, "Add explicit edge-case and malformed-input handling in prompts."),
        ("reliability", float(result.reliability), 0.75, "Reduce stochasticity and enforce stable parsing/validation."),
        ("efficiency", float(result.efficiency), 0.70, "Batch calls and trim prompt context to improve cost/latency."),
        ("orchestration", float(result.orchestration), 0.75, "Add retry bounds and stronger JSON validation/fallback paths."),
    ]
    priorities.sort(key=lambda x: x[1] - x[2])
    worst = priorities[0]
    next_focus = worst[0]
    explanation = worst[3]

    if growth.get("status") == "first_attempt":
        summary = "Baseline established. Focus on consistency and robustness before optimizing cost."
    elif regressed:
        summary = f"Regression detected in {', '.join(regressed)}. Recover baseline before further optimization."
    elif improved:
        summary = f"Improved in {', '.join(improved)}. Keep this direction and target the next weakest dimension."
    else:
        summary = "Flat iteration. Make one targeted change and compare against this run."

    trend = growth.get("status", "flat")
    return {
        "trend": trend,
        "summary": summary,
        "improved": improved,
        "regressed": regressed,
        "next_focus": next_focus,
        "next_focus_explanation": explanation,
        "mastery_state": mastery_state,
        "previous_submission_id": str(previous.id) if previous else None,
    }


def _build_iteration_diff(
    *,
    previous: Submission | None,
    current: Submission,
    growth: dict[str, Any],
) -> dict[str, Any]:
    if not previous:
        return {
            "status": "first_attempt",
            "summary": "No previous attempt. This run establishes your baseline.",
            "previous_submission_id": None,
            "code_changes": {
                "added_lines": 0,
                "removed_lines": 0,
                "changed_ratio": 0.0,
            },
            "prompt_changes": {
                "added_count": 0,
                "removed_count": 0,
                "added_examples": [],
                "removed_examples": [],
            },
            "score_deltas": {
                "overall": None,
                "accuracy": None,
                "robustness": None,
                "efficiency": None,
            },
        }

    prev_code = previous.code or ""
    cur_code = current.code or ""

    prev_lines = prev_code.splitlines()
    cur_lines = cur_code.splitlines()
    added_lines = removed_lines = 0
    for line in difflib.ndiff(prev_lines, cur_lines):
        if line.startswith("+ "):
            added_lines += 1
        elif line.startswith("- "):
            removed_lines += 1
    base = max(1, len(prev_lines))
    changed_ratio = round(min(1.0, (added_lines + removed_lines) / base), 4)

    prev_prompts = _extract_prompt_snippets(prev_code)
    cur_prompts = _extract_prompt_snippets(cur_code)
    added_prompts = [p for p in cur_prompts if p not in prev_prompts]
    removed_prompts = [p for p in prev_prompts if p not in cur_prompts]

    d_overall = growth.get("delta_overall")
    if d_overall is None:
        summary = "Changes detected, but score delta is unavailable."
    elif d_overall > 0.01:
        summary = "This iteration improved. Keep the strongest new changes and continue narrowing weak spots."
    elif d_overall < -0.01:
        summary = "This iteration regressed. Revert the highest-risk prompt/code edits and retest."
    else:
        summary = "This iteration was mostly flat. Make one more targeted change and compare again."

    return {
        "status": growth.get("status", "flat"),
        "summary": summary,
        "previous_submission_id": str(previous.id),
        "code_changes": {
            "added_lines": added_lines,
            "removed_lines": removed_lines,
            "changed_ratio": changed_ratio,
        },
        "prompt_changes": {
            "added_count": len(added_prompts),
            "removed_count": len(removed_prompts),
            "added_examples": added_prompts[:3],
            "removed_examples": removed_prompts[:3],
        },
        "score_deltas": {
            "overall": growth.get("delta_overall"),
            "accuracy": growth.get("delta_accuracy"),
            "robustness": growth.get("delta_robustness"),
            "efficiency": growth.get("delta_efficiency"),
        },
    }


def _enrich_ai_leverage(
    *,
    ai_leverage: dict[str, Any],
    growth: dict[str, Any],
    iteration_diff: dict[str, Any],
    prompt_quality: float,
) -> dict[str, Any]:
    base = dict(ai_leverage or {})
    learning = _compute_learning_velocity_score(
        delta_overall=growth.get("delta_overall"),
        delta_accuracy=growth.get("delta_accuracy"),
        delta_robustness=growth.get("delta_robustness"),
        delta_efficiency=growth.get("delta_efficiency"),
        changed_ratio=((iteration_diff.get("code_changes") or {}).get("changed_ratio")),
    )
    frontier = float(base.get("frontier_navigation_score") or 0.0)
    reliance = float(base.get("reliance_calibration_score") or 0.0)
    mastery = score_ai_mastery(
        frontier_navigation_score=frontier,
        reliance_calibration_score=reliance,
        prompt_quality_score=prompt_quality,
        learning_velocity_score=float(learning.get("score", 0.5)),
        leverage_gain_score=(
            None
            if base.get("leverage_gain_score") is None
            else float(base.get("leverage_gain_score") or 0.0)
        ),
    )
    signals = dict(base.get("signals") or {})
    signals["learning_velocity"] = learning
    signals["composite"] = mastery
    base.update({
        "learning_velocity_score": round(float(learning.get("score", 0.5)), 4),
        "ai_mastery_score": round(float(mastery.get("score", 0.0)), 4),
        "signals": signals,
        "method": "research_proxy_v1",
    })
    return base


def _compute_learning_velocity_score(
    *,
    delta_overall: float | None,
    delta_accuracy: float | None,
    delta_robustness: float | None,
    delta_efficiency: float | None,
    changed_ratio: float | None,
) -> dict[str, Any]:
    if delta_overall is None:
        return {
            "score": 0.5,
            "progress": 0.5,
            "skill_gain": 0.5,
            "change_efficiency": 0.5,
            "method": "learning_velocity_v1",
        }

    progress = _clamp01((float(delta_overall) + 0.08) / 0.16)

    dim_norms: list[float] = []
    for delta in (delta_accuracy, delta_robustness, delta_efficiency):
        if delta is None:
            continue
        dim_norms.append(_clamp01((float(delta) + 0.06) / 0.12))
    skill_gain = sum(dim_norms) / len(dim_norms) if dim_norms else progress

    ratio = float(changed_ratio or 0.0)
    improvement_per_change = float(delta_overall) / max(0.05, ratio)
    change_efficiency = _clamp01((improvement_per_change + 0.05) / 0.25)

    score = (progress * 0.45) + (skill_gain * 0.30) + (change_efficiency * 0.25)
    if float(delta_overall) < -0.08:
        score = min(score, 0.2)

    return {
        "score": round(_clamp01(score), 4),
        "progress": round(progress, 4),
        "skill_gain": round(skill_gain, 4),
        "change_efficiency": round(change_efficiency, 4),
        "method": "learning_velocity_v1",
    }


def _compute_learning_effectiveness(
    *,
    previous: Submission | None,
    current: Any,
    current_ai_leverage: dict[str, Any],
) -> dict[str, Any]:
    if not previous or not isinstance(previous.report, dict):
        return {
            "status": "unavailable",
            "reason": "no_previous_submission",
            "coach_hit_rate": None,
            "assessed_actions": 0,
            "successful_actions": 0,
        }

    previous_actions = previous.report.get("coaching_actions") or []
    if not isinstance(previous_actions, list) or not previous_actions:
        return {
            "status": "unavailable",
            "reason": "no_previous_actions",
            "coach_hit_rate": None,
            "assessed_actions": 0,
            "successful_actions": 0,
        }

    delta_map = {
        "overall": _delta(current.overall, previous.score_overall),
        "accuracy": _delta(current.accuracy, previous.score_accuracy),
        "robustness": _delta(current.edge_case_handling, previous.score_edge_cases),
        "efficiency": _delta(current.efficiency, previous.score_efficiency),
        "reliability": _delta(current.reliability, previous.score_reliability),
        "orchestration": _delta(current.orchestration, previous.score_orchestration),
        "rule_adherence": _delta(current.rule_adherence, previous.score_rule_adherence),
        "ai_mastery": _delta(
            float(current_ai_leverage.get("ai_mastery_score") or 0.0),
            float((previous.report.get("ai_leverage") or {}).get("ai_mastery_score") or 0.0),
        ),
        "frontier_navigation": _delta(
            float(current_ai_leverage.get("frontier_navigation_score") or 0.0),
            float((previous.report.get("ai_leverage") or {}).get("frontier_navigation_score") or 0.0),
        ),
        "reliance_calibration": _delta(
            float(current_ai_leverage.get("reliance_calibration_score") or 0.0),
            float((previous.report.get("ai_leverage") or {}).get("reliance_calibration_score") or 0.0),
        ),
        "leverage_gain": _delta(
            float(current_ai_leverage.get("leverage_gain") or 0.0),
            float((previous.report.get("ai_leverage") or {}).get("leverage_gain") or 0.0),
        ),
    }

    assessed = 0
    successful = 0
    samples: list[dict[str, Any]] = []
    for action in previous_actions[:5]:
        impacts = action.get("expected_impact") if isinstance(action, dict) else None
        if not isinstance(impacts, list) or not impacts:
            continue
        deltas = [delta_map.get(str(metric)) for metric in impacts]
        deltas = [d for d in deltas if d is not None]
        if not deltas:
            continue
        assessed += 1
        avg_delta = sum(deltas) / len(deltas)
        is_success = avg_delta > 0.01
        if is_success:
            successful += 1
        samples.append({
            "title": action.get("title", "action"),
            "expected_impact": impacts,
            "avg_delta": round(avg_delta, 4),
            "success": is_success,
        })

    if assessed == 0:
        return {
            "status": "unavailable",
            "reason": "no_assessable_actions",
            "coach_hit_rate": None,
            "assessed_actions": 0,
            "successful_actions": 0,
        }

    hit_rate = successful / assessed
    return {
        "status": "ok",
        "coach_hit_rate": round(hit_rate, 4),
        "assessed_actions": assessed,
        "successful_actions": successful,
        "overall_delta": _delta(current.overall, previous.score_overall),
        "method": "action_outcome_proxy_v1",
        "samples": samples,
    }


def _build_future_feedback(
    *,
    result: Any,
    ai_leverage: dict[str, Any],
    credibility: dict[str, Any],
    learning_effectiveness: dict[str, Any],
    growth: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runs = result.runs if isinstance(result.runs, list) else []
    run_types = {
        str(r.get("run_type", "")).strip().lower()
        for r in runs
        if isinstance(r, dict)
    }
    required_types = {"clean", "perturbed", "adversarial"}
    required_coverage = len(run_types.intersection(required_types)) / len(required_types)
    hidden_bonus = 0.1 if "hidden_clean" in run_types else 0.0
    run_type_coverage = _clamp01(required_coverage + hidden_bonus)

    credibility_score = _clamp01(float(credibility.get("score") or 0.0))
    frontier = _clamp01(float(ai_leverage.get("frontier_navigation_score") or 0.0))
    reliance = _clamp01(float(ai_leverage.get("reliance_calibration_score") or 0.0))
    velocity = _clamp01(float(ai_leverage.get("learning_velocity_score") or 0.5))
    leverage_gain = ai_leverage.get("leverage_gain")
    leverage_gain_norm = 0.5 if leverage_gain is None else _normalize_leverage_gain_for_feedback(leverage_gain)

    coach_hit_rate = learning_effectiveness.get("coach_hit_rate")
    if coach_hit_rate is None:
        coach_hit = 0.5
    else:
        coach_hit = _clamp01(float(coach_hit_rate))

    rule_adherence = _clamp01(float(getattr(result, "rule_adherence", 0.0) or 0.0))
    reliability = _clamp01(float(getattr(result, "reliability", 0.0) or 0.0))

    verification_discipline = _clamp01((reliance * 0.50) + (rule_adherence * 0.25) + (reliability * 0.25))
    efficient_leverage = _clamp01((frontier * 0.65) + (leverage_gain_norm * 0.35))
    adaptation_speed = _clamp01((velocity * 0.65) + (coach_hit * 0.35))
    evaluation_rigor = _clamp01((credibility_score * 0.75) + (run_type_coverage * 0.25))

    behavior_scores = {
        "verification_discipline": round(verification_discipline, 4),
        "efficient_leverage": round(efficient_leverage, 4),
        "adaptation_speed": round(adaptation_speed, 4),
        "evaluation_rigor": round(evaluation_rigor, 4),
    }

    profile = get_weight_profile()
    readiness_weights_raw = profile.get("future_readiness") if isinstance(profile, dict) else None
    readiness_weights = {
        "verification_discipline": 0.35,
        "efficient_leverage": 0.30,
        "adaptation_speed": 0.20,
        "evaluation_rigor": 0.15,
    }
    if isinstance(readiness_weights_raw, dict):
        for key in readiness_weights.keys():
            if key in readiness_weights_raw:
                try:
                    readiness_weights[key] = max(0.0, float(readiness_weights_raw[key]))
                except (TypeError, ValueError):
                    pass
        total = sum(readiness_weights.values())
        if total > 0:
            readiness_weights = {k: (v / total) for k, v in readiness_weights.items()}

    readiness_score = _clamp01(
        (verification_discipline * readiness_weights["verification_discipline"])
        + (efficient_leverage * readiness_weights["efficient_leverage"])
        + (adaptation_speed * readiness_weights["adaptation_speed"])
        + (evaluation_rigor * readiness_weights["evaluation_rigor"])
    )
    readiness_score = round(readiness_score, 4)
    readiness_band = (
        "high"
        if readiness_score >= 0.75
        else ("medium" if readiness_score >= 0.55 else "low")
    )

    calls_per_run = float(getattr(result, "llm_calls", 0) or 0) / max(1, len(runs))
    if calls_per_run > 2.5 and reliance < 0.65:
        delegation_mode = "over_delegating"
    elif calls_per_run < 0.8 and frontier < 0.55:
        delegation_mode = "under_leveraging"
    else:
        delegation_mode = "balanced"

    ranked_dims = sorted(
        behavior_scores.items(),
        key=lambda item: item[1],
    )
    next_7_days: list[dict[str, Any]] = []
    for dimension, score in ranked_dims:
        if score >= 0.70 and len(next_7_days) >= 1:
            continue
        next_7_days.append(
            _future_action_for_dimension(
                dimension=dimension,
                score=score,
                leverage_gain=leverage_gain,
            )
        )
        if len(next_7_days) >= 3:
            break

    if not next_7_days:
        next_7_days = [
            {
                "priority": "medium",
                "goal": "Protect gains while pushing hard-case robustness",
                "actions": [
                    "Keep one-change-per-iteration discipline with explicit regression checks.",
                    "Shift effort from easy-case tuning to perturbed/adversarial hard cases.",
                ],
                "success_metric": "Hold reliability >= 0.75 while improving robustness by >= 0.05.",
            }
        ]

    protocol = [
        "Run one controlled prompt/code change per iteration and compare against previous submission.",
        "Require strict schema validation + bounded retries before accepting model output.",
        "Evaluate across clean, perturbed, adversarial, and hidden cases when available before publish.",
        "Track leverage gain and keep it positive while reducing unnecessary calls/tokens.",
    ]
    if growth and growth.get("status") == "regressed":
        protocol.insert(
            1,
            "First recover baseline: revert highest-risk edits, then introduce only one targeted fix.",
        )

    if readiness_band == "high":
        summary = "AI usage is strong and disciplined. Focus on raising leverage gain without losing reliability."
    elif readiness_band == "medium":
        summary = "Core AI usage habits are present, but weak dimensions are capping consistent score growth."
    else:
        summary = "Current AI usage is too fragile for reliable gains. Prioritize verification and evaluation discipline first."

    return {
        "method": "future_feedback_v1",
        "summary": summary,
        "readiness_score": readiness_score,
        "readiness_band": readiness_band,
        "delegation_mode": delegation_mode,
        "behavior_scores": behavior_scores,
        "next_7_days": next_7_days,
        "next_eval_protocol": protocol,
        "signals": {
            "weight_profile_version": str(profile.get("version") or "static_v1") if isinstance(profile, dict) else "static_v1",
            "readiness_weights": {k: round(v, 4) for k, v in readiness_weights.items()},
            "calls_per_run": round(calls_per_run, 4),
            "run_type_coverage": round(run_type_coverage, 4),
            "credibility_score": round(credibility_score, 4),
            "frontier_navigation_score": round(frontier, 4),
            "reliance_calibration_score": round(reliance, 4),
            "learning_velocity_score": round(velocity, 4),
            "coach_hit_rate": None if coach_hit_rate is None else round(coach_hit, 4),
            "leverage_gain": None if leverage_gain is None else round(float(leverage_gain), 4),
        },
    }


def _future_action_for_dimension(
    *,
    dimension: str,
    score: float,
    leverage_gain: Any,
) -> dict[str, Any]:
    if dimension == "verification_discipline":
        return {
            "priority": "high" if score < 0.60 else "medium",
            "goal": "Increase verification discipline",
            "actions": [
                "Add strict JSON/schema validation before scoring output as success.",
                "Use bounded retries (max 2) with explicit fallback behavior for invalid outputs.",
            ],
            "success_metric": "Raise reliance calibration to >= 0.70 and rule adherence to >= 0.75.",
        }
    if dimension == "efficient_leverage":
        gain_suffix = ""
        if leverage_gain is not None:
            gain_suffix = f" Current leverage gain is {float(leverage_gain):+.2f}."
        return {
            "priority": "high" if score < 0.60 else "medium",
            "goal": "Improve quality-cost frontier use",
            "actions": [
                "Reduce prompt/context redundancy and combine low-value LLM calls.",
                "Tighten output schema constraints so first-pass quality improves without extra retries.",
            ],
            "success_metric": f"Reach frontier navigation >= 0.70 and positive leverage gain.{gain_suffix}".strip(),
        }
    if dimension == "adaptation_speed":
        return {
            "priority": "high" if score < 0.60 else "medium",
            "goal": "Increase learning velocity",
            "actions": [
                "Ship one focused change per iteration and measure only the target metric impact.",
                "Keep a short change log mapping each edit to expected metric movement before re-run.",
            ],
            "success_metric": "Reach learning velocity >= 0.60 and positive delta_overall on next attempt.",
        }
    return {
        "priority": "high" if score < 0.60 else "medium",
        "goal": "Strengthen evaluation rigor",
        "actions": [
            "Test all required run types (clean, perturbed, adversarial) plus hidden cases when available.",
            "Treat low-credibility runs as non-publishable and iterate until confidence improves.",
        ],
        "success_metric": "Reach credibility >= 0.75 and maintain full run-type coverage.",
    }


def _normalize_leverage_gain_for_feedback(gain: Any) -> float:
    value = float(gain or 0.0)
    return _clamp01((value + 0.10) / 0.30)


def _build_coaching_actions(
    *,
    result: Any,
    growth: dict[str, Any],
    runs: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    iteration_diff: dict[str, Any],
    ai_leverage: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    failed = [r for r in runs if r.get("status") != "pass"]
    for run in failed[:3]:
        run_type = str(run.get("run_type", "run"))
        if run_type in ("clean", "hidden_clean"):
            change = "Constrain output to strict JSON schema and add explicit field-level requirements."
            impact = ["accuracy", "rule_adherence"]
        elif run_type == "perturbed":
            change = "Add normalization rules (whitespace/date/currency/name cleanup) before extraction."
            impact = ["robustness", "reliability"]
        elif run_type == "adversarial":
            change = "Add malformed-input fallback behavior and 'unknown' handling for ambiguous records."
            impact = ["robustness", "orchestration"]
        else:
            change = "Tighten validation and retry bounds for unstable outputs."
            impact = ["reliability", "orchestration"]

        actions.append({
            "priority": "high",
            "title": f"Fix {run_type} failure",
            "why": f"Run #{int(run.get('run_index', 0)) + 1} failed with accuracy {float(run.get('accuracy', 0.0)):.2f}.",
            "evidence": {
                "run_type": run_type,
                "run_index": run.get("run_index", 0),
                "status": run.get("status"),
                "accuracy": run.get("accuracy"),
            },
            "suggested_change": change,
            "expected_impact": impact,
        })

    for d in diagnostics[:2]:
        sev = str(d.get("severity", "low")).lower()
        if sev not in ("high", "medium"):
            continue
        metric = str(d.get("metric", "metric"))
        if metric == "efficiency":
            suggestion = "Batch related tasks into fewer LLM calls and shorten repetitive context."
            impact = ["efficiency"]
        elif metric == "orchestration":
            suggestion = "Validate JSON output before use and cap retries with explicit fallback."
            impact = ["orchestration", "reliability"]
        elif metric == "accuracy":
            suggestion = "Specify exact keys/types and force output format to match challenge schema."
            impact = ["accuracy", "rule_adherence"]
        else:
            suggestion = "Address this diagnostic first, then re-run to verify improvement."
            impact = [metric]

        actions.append({
            "priority": "medium" if sev == "medium" else "high",
            "title": f"Address {metric} diagnostic",
            "why": str(d.get("message", "")),
            "evidence": {"metric": metric, "severity": sev},
            "suggested_change": suggestion,
            "expected_impact": impact,
        })

    if growth.get("delta_overall") is not None and float(growth.get("delta_overall") or 0.0) < -0.02:
        actions.append({
            "priority": "high",
            "title": "Recover previous baseline",
            "why": f"Overall score regressed by {float(growth['delta_overall']):.2f} from your last attempt.",
            "evidence": {
                "delta_overall": growth.get("delta_overall"),
                "previous_submission_id": growth.get("previous_submission_id"),
            },
            "suggested_change": "Reintroduce the most stable prompt structure from the previous run, then apply one targeted fix.",
            "expected_impact": ["overall", "reliability"],
        })

    prompt_changes = (iteration_diff.get("prompt_changes") or {})
    if int(prompt_changes.get("added_count") or 0) > 2 and float(result.efficiency) < 0.75:
        actions.append({
            "priority": "medium",
            "title": "Reduce prompt churn",
            "why": "Many prompt edits were introduced, but efficiency is still below target.",
            "evidence": {
                "prompt_added_count": prompt_changes.get("added_count"),
                "efficiency": float(result.efficiency),
            },
            "suggested_change": "Consolidate overlapping instructions into one reusable prompt block.",
            "expected_impact": ["efficiency", "reliability"],
        })

    leverage = ai_leverage or {}
    frontier = float(leverage.get("frontier_navigation_score") or 0.0)
    reliance = float(leverage.get("reliance_calibration_score") or 0.0)
    velocity = leverage.get("learning_velocity_score")
    gain = leverage.get("leverage_gain")

    if frontier and frontier < 0.65:
        actions.append({
            "priority": "high",
            "title": "Move closer to the quality-cost frontier",
            "why": f"Frontier navigation is {frontier:.2f}, which indicates quality is not matching token/cost spend.",
            "evidence": {"frontier_navigation_score": frontier},
            "suggested_change": "Tighten schema constraints in prompts and remove redundant context so each call has a clear, narrow objective.",
            "expected_impact": ["frontier_navigation", "efficiency", "accuracy"],
        })

    if reliance and reliance < 0.65:
        actions.append({
            "priority": "high",
            "title": "Improve AI reliance calibration",
            "why": f"Reliance calibration is {reliance:.2f}; outputs are not being verified strongly enough for current call volume.",
            "evidence": {"reliance_calibration_score": reliance},
            "suggested_change": "Add strict JSON validation + bounded retries + explicit fallback rules before accepting model output.",
            "expected_impact": ["reliance_calibration", "reliability", "orchestration"],
        })

    if gain is not None and float(gain) <= 0.0:
        actions.append({
            "priority": "high",
            "title": "Beat the counterfactual baseline",
            "why": f"Leverage gain is {float(gain):+.2f}; your current approach is not outperforming the baseline strategy yet.",
            "evidence": {
                "leverage_gain": float(gain),
                "counterfactual_baseline_overall": leverage.get("counterfactual_baseline_overall"),
            },
            "suggested_change": "Use a more explicit schema-constrained prompt and tighter normalization instructions, then validate output before acceptance.",
            "expected_impact": ["leverage_gain", "ai_mastery", "overall"],
        })

    if velocity is not None and float(velocity) < 0.5 and growth.get("status") != "first_attempt":
        actions.append({
            "priority": "medium",
            "title": "Increase iteration learning velocity",
            "why": f"Learning velocity is {float(velocity):.2f}; current edits are not converting into reliable score gains.",
            "evidence": {"learning_velocity_score": float(velocity)},
            "suggested_change": "Ship one targeted prompt/code change at a time and measure impact on a single weak metric before stacking edits.",
            "expected_impact": ["learning_velocity", "overall"],
        })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: priority_order.get(a.get("priority", "low"), 3))
    return actions[:5]


def _extract_prompt_snippets(code: str, *, max_snippets: int = 8) -> list[str]:
    if not code.strip():
        return []

    patterns = [
        r'(?:prompt|system|user_message|instructions)\s*[:=]\s*(?:f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\')',
        r'(?:prompt|system|user_message|instructions)\s*[:=]\s*(?:f?"(.*?)"|f?\'(.*?)\')',
        r'(?:llm\.call|chat\.completions\.create)\((.*?)\)',
    ]
    snippets: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for m in re.finditer(pattern, code, re.DOTALL):
            raw = next((g for g in m.groups() if g), "")
            cleaned = re.sub(r"\s+", " ", raw).strip()
            if len(cleaned) < 20:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            snippets.append(cleaned[:180])
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return round(float(current) - float(previous), 4)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
