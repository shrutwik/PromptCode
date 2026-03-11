"""Prompt Efficiency Report generator.

Converts raw evaluation results into the structured report format
that gets stored on the submission and returned via API.
"""

from __future__ import annotations

from typing import Any

from app.services.evaluation.engine import SCORE_WEIGHTS, EvaluationResult


def generate_report(
    submission_id: str,
    result: EvaluationResult,
) -> dict[str, Any]:
    """Build the JSON report that users see."""
    return {
        "submission_id": submission_id,
        "accuracy": result.accuracy,
        "prompt_quality": result.prompt_quality,
        "efficiency": result.efficiency,
        "reliability": result.reliability,
        "orchestration": result.orchestration,
        "code_quality": result.code_quality,
        "overall": result.overall,
        "cost_usd": round(result.cost_usd, 6),
        "latency_ms": round(result.latency_ms, 2),
        "llm_calls": result.llm_calls,
        "breakdown": {
            "score_weights": SCORE_WEIGHTS,
            "prompt_quality_details": result.prompt_quality_details,
            "code_analysis_details": result.code_analysis_details,
            "runs_summary": _summarize_runs(result.runs),
        },
        "runs": result.runs,
    }


def _summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    normal = [r for r in runs if r["run_type"] == "normal"]
    adversarial = [r for r in runs if r["run_type"] == "adversarial"]

    return {
        "total_runs": len(runs),
        "normal_runs": len(normal),
        "adversarial_runs": len(adversarial),
        "normal_success_rate": _success_rate(normal),
        "adversarial_success_rate": _success_rate(adversarial),
        "normal_avg_accuracy": _avg(normal, "accuracy"),
        "adversarial_avg_accuracy": _avg(adversarial, "accuracy"),
        "avg_tokens_per_run": _avg(runs, "tokens_total"),
        "avg_cost_per_run": _avg(runs, "cost_usd"),
    }


def _success_rate(runs: list[dict[str, Any]]) -> float:
    if not runs:
        return 0.0
    return round(sum(1 for r in runs if r["success"]) / len(runs), 4)


def _avg(runs: list[dict[str, Any]], key: str) -> float:
    if not runs:
        return 0.0
    return round(sum(r.get(key, 0.0) for r in runs) / len(runs), 4)
