"""Background worker that runs the full evaluation pipeline for a submission."""

from __future__ import annotations

import difflib
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.challenge import Challenge
from app.models.leaderboard import LeaderboardEntry
from app.models.run import Run
from app.models.submission import Submission
from app.services.evaluation.engine import evaluate_submission
from app.services.evaluation.scorer import score_ai_mastery

logger = logging.getLogger(__name__)
MIN_LEADERBOARD_TESTS = 6
MIN_LEADERBOARD_RELIABILITY = 0.55


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

    result = evaluate_submission(
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

    if submission.score_overall is not None and (
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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
