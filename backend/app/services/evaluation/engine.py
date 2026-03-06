"""Evaluation engine: multi-run sandbox scoring with quality, robustness, and efficiency tradeoffs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services.evaluation.code_analysis import analyze_code, score_code_quality
from app.services.evaluation.perturbation import perturb_adversarial, perturb_normal
from app.services.evaluation.prompt_quality import score_prompt_quality
from app.services.evaluation.scorer import (
    score_ai_mastery,
    score_accuracy,
    score_calibration,
    score_efficiency_tradeoff,
    score_frontier_navigation,
    score_orchestration,
    score_reliance_calibration,
    score_reliability,
)
from app.services.evaluation.weight_profile import get_weight_profile
from app.services.sandbox.runner import SandboxResult, run_in_sandbox

logger = logging.getLogger(__name__)
settings = get_settings()

SCORE_WEIGHTS = {
    "accuracy": 0.35,
    "robustness": 0.15,
    "reliability": 0.10,
    "efficiency": 0.15,
    "prompt_quality": 0.10,
    "orchestration": 0.10,
    "calibration": 0.05,
}
PERTURBATION_CONFIG_VERSION = "v1"


async def _run_all_specs_in_parallel(
    run_plan: list[dict[str, Any]],
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
) -> list[tuple[dict[str, Any], SandboxResult]]:
    """Execute all specs in parallel using asyncio thread pool.

    Returns list of (spec, result) tuples in order.

    Speedup: 8x (all runs concurrent) vs sequential execution.
    """
    loop = asyncio.get_event_loop()

    async def run_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], SandboxResult]:
        # Use functools.partial to pass kwargs to thread pool
        from functools import partial
        runner = partial(
            run_in_sandbox,
            code,
            entrypoint,
            challenge_config,
            input_overrides=spec["inputs"],
        )
        result = await loop.run_in_executor(None, runner)
        return (spec, result)

    # Create tasks for all runs
    tasks = [run_spec(spec) for spec in run_plan]

    # Run all in parallel - this is the 8x speedup!
    results = await asyncio.gather(*tasks)
    return results


async def _score_prompt_quality_async(
    telemetry_calls: list[dict[str, Any]],
    challenge_description: str,
) -> dict[str, Any]:
    """Run the synchronous prompt-quality judge off the event loop."""
    return await asyncio.to_thread(
        score_prompt_quality,
        telemetry_calls,
        challenge_description,
    )


class EvaluationResult:
    def __init__(
        self,
        *,
        accuracy: float,
        prompt_quality: float,
        rule_adherence: float,
        efficiency: float,
        reliability: float,
        orchestration: float,
        code_quality: float,
        edge_case_handling: float,
        calibration: float,
        overall: float,
        cost_usd: float,
        latency_ms: float,
        llm_calls: int,
        prompt_tokens: int,
        completion_tokens: int,
        retries: int,
        runs: list[dict[str, Any]],
        prompt_quality_details: dict[str, Any],
        code_analysis_details: dict[str, Any],
        calibration_details: dict[str, Any],
        diagnostics: list[dict[str, str]],
        evaluation_config: dict[str, Any],
        ai_leverage: dict[str, Any] | None = None,
        usage_breakdown: dict[str, Any] | None = None,
        credibility: dict[str, Any] | None = None,
        confidence_intervals: dict[str, Any] | None = None,
        audit_trail: list[dict[str, Any]] | None = None,
        evaluation_manifest: dict[str, Any] | None = None,
        hardcoded: bool = False,
    ):
        self.accuracy = accuracy
        self.prompt_quality = prompt_quality
        self.rule_adherence = rule_adherence
        self.efficiency = efficiency
        self.reliability = reliability
        self.orchestration = orchestration
        self.code_quality = code_quality
        self.edge_case_handling = edge_case_handling
        self.calibration = calibration
        self.overall = overall
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.llm_calls = llm_calls
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.retries = retries
        self.runs = runs
        self.prompt_quality_details = prompt_quality_details
        self.code_analysis_details = code_analysis_details
        self.calibration_details = calibration_details
        self.diagnostics = diagnostics
        self.evaluation_config = evaluation_config
        self.ai_leverage = ai_leverage or {}
        self.usage_breakdown = usage_breakdown or {}
        self.credibility = credibility or {}
        self.confidence_intervals = confidence_intervals or {}
        self.audit_trail = audit_trail or []
        self.evaluation_manifest = evaluation_manifest or {}
        self.hardcoded = hardcoded

    def to_report(self, submission_id: str) -> dict[str, Any]:
        tests_passed = sum(1 for r in self.runs if r.get("status") == "pass")
        tests_total = len(self.runs)
        report: dict[str, Any] = {
            "submission_id": submission_id,
            "accuracy": self.accuracy,
            "prompt_quality": self.prompt_quality,
            "rule_adherence": self.rule_adherence,
            "efficiency": self.efficiency,
            "reliability": self.reliability,
            "orchestration": self.orchestration,
            "code_quality": self.code_quality,
            "edge_case_handling": self.edge_case_handling,
            "calibration": self.calibration,
            "overall": self.overall,
            "cost_usd": round(self.cost_usd, 6),
            "latency_ms": round(self.latency_ms, 2),
            "llm_calls": self.llm_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "retries": self.retries,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "runs": self.runs,
            "prompt_quality_details": self.prompt_quality_details,
            "code_analysis_details": self.code_analysis_details,
            "calibration_details": self.calibration_details,
            "diagnostics": self.diagnostics,
            "feedback": self.diagnostics[0]["message"] if self.diagnostics else "",
            "evaluation_config": self.evaluation_config,
            "ai_leverage": self.ai_leverage,
            "usage_breakdown": self.usage_breakdown,
            "credibility": self.credibility,
            "confidence_intervals": self.confidence_intervals,
            "audit_trail": self.audit_trail,
            "evaluation_manifest": self.evaluation_manifest,
            "scorecard": {
                "accuracy": self.accuracy,
                "robustness": self.edge_case_handling,
                "reliability": self.reliability,
                "efficiency": self.efficiency,
                "prompt_design": self.prompt_quality,
                "orchestration": self.orchestration,
                "calibration": self.calibration,
                "ai_mastery": float(self.ai_leverage.get("ai_mastery_score", 0.0)),
            },
        }
        if self.hardcoded:
            report["disqualified"] = True
            report["disqualification_reason"] = (
                "Submission appears to contain hardcoded answers rather than "
                "using AI to solve the problem. All scores have been zeroed."
            )
        return report


async def evaluate_submission(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
) -> EvaluationResult:
    """Run full evaluation across clean, perturbed, and adversarial runs.

    All 8 runs (1 clean + 5 perturbed + 2 adversarial) execute in parallel
    using asyncio thread pool for 8x speedup vs sequential execution.
    """

    ground_truth = challenge_config.get("ground_truth", "")
    if isinstance(ground_truth, (list, dict)):
        ground_truth = json.dumps(ground_truth)
    accuracy_mode = challenge_config.get("accuracy_mode", "json")
    base_inputs = challenge_config.get("inputs", {})
    challenge_description = challenge_config.get("description", "")
    evaluation_seed = int(
        challenge_config.get("evaluation_seed")
        or _default_evaluation_seed(challenge_config)
    )
    seed_rng = random.Random(evaluation_seed)

    run_records: list[dict[str, Any]] = []
    clean_accuracies: list[float] = []
    perturbed_accuracies: list[float] = []
    adversarial_accuracies: list[float] = []
    all_telemetry: list[dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    total_calls = 0
    total_retries = 0
    audit_trail: list[dict[str, Any]] = [
        {
            "event": "evaluation_started",
            "at": _now_iso(),
            "details": {
                "accuracy_mode": accuracy_mode,
                "evaluation_seed": evaluation_seed,
            },
        }
    ]

    clean_runs = int(challenge_config.get("clean_runs", 1))
    run_plan: list[dict[str, Any]] = []
    hidden_cases = _build_hidden_cases(challenge_config, ground_truth, accuracy_mode)

    for i in range(clean_runs):
        run_plan.append(
            {
                "run_type": "clean",
                "run_index": i,
                "inputs": base_inputs,
                "ground_truth": ground_truth,
                "accuracy_mode": accuracy_mode,
                "meta": {
                    "seed": None,
                    "perturbation": "none",
                    "source_set": "visible",
                    "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
                },
            }
        )

    for i, hidden in enumerate(hidden_cases):
        run_plan.append(
            {
                "run_type": "hidden_clean",
                "run_index": i,
                "inputs": hidden["inputs"],
                "ground_truth": hidden["ground_truth"],
                "accuracy_mode": hidden["accuracy_mode"],
                "meta": {
                    "seed": None,
                    "perturbation": "none",
                    "source_set": hidden["name"],
                    "hidden": True,
                    "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
                },
            }
        )

    for i in range(settings.evaluation_normal_runs):
        seed = seed_rng.randint(0, 2**31)
        perturbed = perturb_normal(base_inputs, seed)
        run_plan.append(
            {
                "run_type": "perturbed",
                "run_index": i,
                "inputs": perturbed,
                "ground_truth": ground_truth,
                "accuracy_mode": accuracy_mode,
                "meta": {
                    "seed": seed,
                    "perturbation": "normal",
                    "source_set": "visible",
                    "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
                },
            }
        )

    for i in range(settings.evaluation_adversarial_runs):
        seed = seed_rng.randint(0, 2**31)
        perturbed = perturb_adversarial(base_inputs, seed)
        run_plan.append(
            {
                "run_type": "adversarial",
                "run_index": i,
                "inputs": perturbed,
                "ground_truth": ground_truth,
                "accuracy_mode": accuracy_mode,
                "meta": {
                    "seed": seed,
                    "perturbation": "adversarial",
                    "source_set": "visible",
                    "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
                },
            }
        )

    # PARALLELIZATION: Run all specs concurrently (8x speedup)
    spec_results = await _run_all_specs_in_parallel(run_plan, code, entrypoint, challenge_config)

    # Process results in order (preserves determinism)
    for spec, result in spec_results:
        record = _process_run(
            result,
            spec["ground_truth"],
            spec["accuracy_mode"],
            spec["run_type"],
            spec["run_index"],
            meta=spec["meta"],
        )
        run_records.append(record)
        if spec["run_type"] in ("clean", "hidden_clean"):
            clean_accuracies.append(record["accuracy"])
        elif spec["run_type"] == "perturbed":
            perturbed_accuracies.append(record["accuracy"])
        elif spec["run_type"] == "adversarial":
            adversarial_accuracies.append(record["accuracy"])
        all_telemetry.extend(result.telemetry)
        total_prompt_tokens += record["tokens_prompt"]
        total_completion_tokens += record["tokens_completion"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]
        audit_trail.append(
            {
                "event": "run_completed",
                "at": _now_iso(),
                "details": {
                    "run_type": record["run_type"],
                    "run_index": record["run_index"],
                    "status": record["status"],
                    "accuracy": record["accuracy"],
                    "schema_valid": record["schema_valid"],
                    "seed": (record.get("meta") or {}).get("seed"),
                },
            }
        )

    all_accuracies = clean_accuracies + perturbed_accuracies + adversarial_accuracies

    hardcoded = _detect_hardcoding(
        total_calls=total_calls,
        accuracies=all_accuracies,
        code=code,
        ground_truth=ground_truth,
    )

    code_analysis_result = analyze_code(code, entrypoint)
    code_quality_result = score_code_quality(code_analysis_result)
    pq_result = await _score_prompt_quality_async(all_telemetry, challenge_description)

    acc = round(sum(clean_accuracies) / len(clean_accuracies), 4) if clean_accuracies else 0.0
    robustness = _score_robustness(perturbed_accuracies, adversarial_accuracies)
    rel = score_reliability(all_accuracies)
    pq = round(pq_result.get("overall", 0.0), 4)
    cq = round(code_quality_result.get("score", 0.5), 4)

    orch = score_orchestration(
        total_calls,
        total_retries,
        expected_calls=challenge_config.get("expected_calls", 3),
        code_analysis=code_quality_result,
    )

    rule_adherence = _score_constraint_adherence(run_records)

    quality_anchor = (acc * 0.5) + (robustness * 0.3) + (rel * 0.2)
    run_count = max(1, len(run_records))
    budgets = {
        "token_budget": challenge_config.get("token_budget", 12_000),
        "cost_budget_usd": challenge_config.get("cost_budget_usd", 0.20),
        "latency_budget_ms": challenge_config.get("latency_budget_ms", 30_000),
        "call_budget": challenge_config.get("call_budget", challenge_config.get("expected_calls", 3) * run_count),
    }
    eff = score_efficiency_tradeoff(
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        total_calls=total_calls,
        quality_anchor=quality_anchor,
        budgets=budgets,
    )

    calibration_points = _extract_confidence_points(run_records)
    calibration_result = score_calibration(calibration_points)
    calibration = float(calibration_result.get("score", 0.5))
    calibration_samples = int(calibration_result.get("samples") or 0)
    run_accuracy_ci_half_width = float(
        _mean_confidence_interval(all_accuracies).get("half_width") or 0.0
    )
    calibration_samples = int(calibration_result.get("samples") or 0)

    prompt_judge_fallback = pq_result.get("method") == "heuristic"
    if prompt_judge_fallback:
        # Heuristic prompt judging is less trustworthy than LLM-judge scoring.
        pq = min(pq, 0.65)

    if hardcoded:
        logger.warning("Hardcoded answer detected - zeroing all quality scores")
        acc = pq = rule_adherence = eff = rel = orch = cq = robustness = calibration = 0.0
        audit_trail.append(
            {
                "event": "hardcode_disqualification",
                "at": _now_iso(),
                "details": {"reason": "hardcoded_or_no_llm_usage"},
            }
        )

    metric_gaming = _detect_metric_gaming(
        runs=run_records,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_calls=total_calls,
        accuracy=acc,
        robustness=robustness,
    )
    if metric_gaming["triggered"]:
        eff = min(eff, 0.25)
        orch = min(orch, 0.5)
        audit_trail.append(
            {
                "event": "anti_gaming_penalty",
                "at": _now_iso(),
                "details": {"reason": metric_gaming["reason"]},
            }
        )

    quality_anchor_final = (acc * 0.5) + (robustness * 0.3) + (rel * 0.2)
    frontier_result = score_frontier_navigation(
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        total_calls=total_calls,
        quality_anchor=quality_anchor_final,
        budgets=budgets,
    )
    reliance_result = score_reliance_calibration(
        calibration_score=calibration,
        runs=run_records,
        expected_calls=int(challenge_config.get("expected_calls", 3)),
        code_analysis=code_quality_result,
        anti_gaming_triggered=metric_gaming["triggered"],
    )
    ai_leverage = {
        "frontier_navigation_score": round(float(frontier_result.get("score", 0.0)), 4),
        "reliance_calibration_score": round(float(reliance_result.get("score", 0.0)), 4),
        "learning_velocity_score": None,
        "counterfactual_baseline_overall": None,
        "leverage_gain": None,
        "leverage_gain_score": None,
        "ai_mastery_score": 0.0,
        "signals": {
            "frontier": frontier_result,
            "reliance": reliance_result,
            "counterfactual": {},
        },
        "method": "research_proxy_v1",
    }

    raw_overall = round(
        acc * SCORE_WEIGHTS["accuracy"]
        + robustness * SCORE_WEIGHTS["robustness"]
        + rel * SCORE_WEIGHTS["reliability"]
        + eff * SCORE_WEIGHTS["efficiency"]
        + pq * SCORE_WEIGHTS["prompt_quality"]
        + orch * SCORE_WEIGHTS["orchestration"]
        + calibration * SCORE_WEIGHTS["calibration"],
        4,
    )
    accuracy_ci = _mean_confidence_interval(clean_accuracies)
    robustness_ci = _mean_confidence_interval(perturbed_accuracies + adversarial_accuracies)
    run_accuracy_ci = _mean_confidence_interval(all_accuracies)
    pass_rate_ci = _proportion_confidence_interval(
        sum(1 for r in run_records if r.get("status") == "pass"),
        len(run_records),
    )
    run_accuracy_ci_half_width = float(run_accuracy_ci.get("half_width") or 0.0)

    overall, cap_events = _apply_overall_caps(
        raw_overall=raw_overall,
        accuracy=acc,
        rule_adherence=rule_adherence,
        anti_gaming_triggered=metric_gaming["triggered"],
    )
    overall, confidence_cap_events = _apply_confidence_caps(
        overall=overall,
        prompt_judge_method=str(pq_result.get("method") or "unknown"),
        calibration_samples=calibration_samples,
        run_accuracy_ci_half_width=run_accuracy_ci_half_width,
    )
    cap_events.extend(confidence_cap_events)

    if hardcoded:
        baseline_result = {"status": "skipped", "reason": "submission_disqualified"}
    else:
        baseline_result = await _evaluate_counterfactual_baseline_async(
            run_plan=run_plan,
            challenge_config=challenge_config,
        )
    baseline_overall = baseline_result.get("overall")
    leverage_gain = None if baseline_overall is None else round(overall - float(baseline_overall), 4)
    leverage_gain_score = None if leverage_gain is None else round(_normalize_leverage_gain(leverage_gain), 4)
    weight_profile = get_weight_profile()
    ai_mastery_result = score_ai_mastery(
        frontier_navigation_score=float(ai_leverage["frontier_navigation_score"]),
        reliance_calibration_score=float(ai_leverage["reliance_calibration_score"]),
        prompt_quality_score=pq,
        leverage_gain_score=leverage_gain_score,
        weights_without_baseline=weight_profile.get("ai_mastery_without_baseline"),
        weights_with_baseline=weight_profile.get("ai_mastery_with_baseline"),
    )
    if hardcoded:
        ai_mastery_result["score"] = 0.0
        ai_mastery_result["components"]["frontier_navigation"] = 0.0
        ai_mastery_result["components"]["reliance_calibration"] = 0.0
        if leverage_gain_score is not None:
            ai_mastery_result["components"]["leverage_gain"] = 0.0
    ai_leverage.update({
        "counterfactual_baseline_overall": baseline_overall,
        "leverage_gain": leverage_gain,
        "leverage_gain_score": leverage_gain_score,
        "ai_mastery_score": round(float(ai_mastery_result.get("score", 0.0)), 4),
        "weight_profile_version": str(weight_profile.get("version") or "static_v1"),
    })
    ai_leverage["signals"]["counterfactual"] = baseline_result
    ai_leverage["signals"]["composite"] = ai_mastery_result
    if baseline_result.get("status") == "ok":
        ai_leverage["method"] = "counterfactual_v1"
    else:
        ai_leverage["method"] = "research_proxy_v1"

    for event in cap_events:
        audit_trail.append(
            {
                "event": "score_cap_applied",
                "at": _now_iso(),
                "details": event,
            }
        )

    leverage_gain_for_diagnostics = (
        float(leverage_gain)
        if (leverage_gain is not None and baseline_result.get("status") == "ok")
        else 1.0
    )
    diagnostics = _build_diagnostics(
        accuracy=acc,
        robustness=robustness,
        reliability=rel,
        efficiency=eff,
        prompt_quality=pq,
        orchestration=orch,
        calibration=calibration,
        code_quality=cq,
        rule_adherence=rule_adherence,
        frontier_navigation=float(ai_leverage["frontier_navigation_score"]),
        reliance_calibration=float(ai_leverage["reliance_calibration_score"]),
        leverage_gain=leverage_gain_for_diagnostics,
        metric_gaming=1.0 if metric_gaming["triggered"] else 0.0,
    )
    if prompt_judge_fallback:
        diagnostics.insert(
            0,
            {
                "metric": "prompt_quality",
                "severity": "medium",
                "message": "Prompt judge fell back to heuristics; prompt-quality score confidence is reduced.",
            },
        )
    if metric_gaming["triggered"]:
        diagnostics.insert(
            0,
            {
                "metric": "anti_gaming",
                "severity": "high",
                "message": metric_gaming["reason"],
            },
        )

    confidence_intervals = {
        "accuracy": accuracy_ci,
        "robustness_proxy": robustness_ci,
        "run_accuracy": run_accuracy_ci,
        "pass_rate": pass_rate_ci,
    }
    run_type_coverage = _compute_run_type_coverage(run_records)
    credibility = _compute_credibility(
        prompt_judge_method=str(pq_result.get("method") or "unknown"),
        calibration_samples=calibration_samples,
        run_count=len(run_records),
        hidden_set_count=len(hidden_cases),
        run_type_coverage=run_type_coverage,
        counterfactual_status=str(baseline_result.get("status") or "unknown"),
        anti_gaming_triggered=metric_gaming["triggered"],
        hardcoded=hardcoded,
        run_accuracy_ci_half_width=run_accuracy_ci_half_width,
    )
    if float(credibility.get("score", 0.0)) < 0.55:
        diagnostics.insert(
            0,
            {
                "metric": "credibility",
                "severity": "medium",
                "message": "Score confidence is limited for this run set. Improve calibration signals and avoid heuristic fallback paths.",
            },
        )
    usage_breakdown = _build_usage_breakdown(all_telemetry, run_records)
    audit_trail.append(
        {
            "event": "evaluation_completed",
            "at": _now_iso(),
            "details": {
                "overall": overall,
                "tests_total": len(run_records),
                "tests_passed": sum(1 for r in run_records if r.get("status") == "pass"),
            },
        }
    )
    evaluation_manifest = _build_evaluation_manifest(
        entrypoint=entrypoint,
        challenge_config=challenge_config,
        evaluation_seed=evaluation_seed,
        run_plan=run_plan,
        run_records=run_records,
        scores={
            "accuracy": acc,
            "robustness": robustness,
            "reliability": rel,
            "efficiency": eff,
            "prompt_quality": pq,
            "orchestration": orch,
            "calibration": calibration,
            "rule_adherence": rule_adherence,
            "frontier_navigation": float(ai_leverage["frontier_navigation_score"]),
            "reliance_calibration": float(ai_leverage["reliance_calibration_score"]),
            "leverage_gain": float(leverage_gain or 0.0),
            "ai_mastery": float(ai_leverage["ai_mastery_score"]),
            "overall": overall,
            "raw_overall": raw_overall,
        },
    )

    return EvaluationResult(
        accuracy=acc,
        prompt_quality=pq,
        rule_adherence=rule_adherence,
        efficiency=eff,
        reliability=rel,
        orchestration=orch,
        code_quality=cq,
        edge_case_handling=robustness,
        calibration=calibration,
        overall=overall,
        cost_usd=total_cost,
        latency_ms=total_latency,
        llm_calls=total_calls,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        retries=total_retries,
        runs=run_records,
        prompt_quality_details=pq_result,
        code_analysis_details=code_quality_result,
        calibration_details=calibration_result,
        diagnostics=diagnostics,
        evaluation_config={
            "evaluation_seed": evaluation_seed,
            "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
            "run_count": len(run_plan),
            "hidden_set_count": len(hidden_cases),
            "scoring_weights": SCORE_WEIGHTS,
        },
        ai_leverage=ai_leverage,
        usage_breakdown=usage_breakdown,
        credibility=credibility,
        confidence_intervals=confidence_intervals,
        audit_trail=audit_trail,
        evaluation_manifest=evaluation_manifest,
        hardcoded=hardcoded,
    )


def _score_robustness(perturbed: list[float], adversarial: list[float]) -> float:
    perturbed_pass = sum(1 for s in perturbed if s >= 0.8) / len(perturbed) if perturbed else 0.0
    adversarial_pass = sum(1 for s in adversarial if s >= 0.7) / len(adversarial) if adversarial else 0.0
    return round((perturbed_pass * 0.5) + (adversarial_pass * 0.5), 4)


def _score_constraint_adherence(runs: list[dict[str, Any]]) -> float:
    if not runs:
        return 0.0

    schema_valid = sum(1 for r in runs if r.get("schema_valid")) / len(runs)
    pass_rate = sum(1 for r in runs if r.get("status") == "pass") / len(runs)
    return round((schema_valid * 0.55) + (pass_rate * 0.45), 4)


def _extract_confidence_points(runs: list[dict[str, Any]]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for run in runs:
        conf = run.get("confidence")
        if conf is None:
            continue
        outcome = 1.0 if run.get("status") == "pass" else 0.0
        points.append((float(conf), outcome))
    return points


def _compute_run_type_coverage(runs: list[dict[str, Any]]) -> float:
    if not runs:
        return 0.0
    required = {"clean", "perturbed", "adversarial"}
    observed = {
        str(r.get("run_type", "")).strip().lower()
        for r in runs
        if isinstance(r, dict)
    }
    coverage = len(required.intersection(observed)) / len(required)
    if "hidden_clean" in observed:
        coverage = min(1.0, coverage + 0.1)
    return round(max(0.0, min(1.0, coverage)), 4)


def _build_diagnostics(**scores: float) -> list[dict[str, str]]:
    tips: list[dict[str, str]] = []

    if scores["accuracy"] < 0.85:
        tips.append({
            "metric": "accuracy",
            "severity": "high",
            "message": "Low clean-run correctness. Tighten extraction instructions and enforce exact output schema.",
        })
    if scores["robustness"] < 0.75:
        tips.append({
            "metric": "robustness",
            "severity": "high",
            "message": "Results degrade on perturbed/adversarial inputs. Add explicit normalization and missing-field handling rules.",
        })
    if scores["efficiency"] < 0.70:
        tips.append({
            "metric": "efficiency",
            "severity": "medium",
            "message": "Usage is above cost/latency budget frontier for achieved quality. Reduce redundant calls and compress prompt context.",
        })
    if scores["orchestration"] < 0.75:
        tips.append({
            "metric": "orchestration",
            "severity": "medium",
            "message": "Orchestration quality is weak. Add retry bounds, JSON validation, and explicit fallback behavior.",
        })
    if scores["calibration"] < 0.60:
        tips.append({
            "metric": "calibration",
            "severity": "low",
            "message": "Confidence signals are missing or miscalibrated. Emit confidence per output and calibrate thresholds.",
        })
    if scores.get("frontier_navigation", 1.0) < 0.65:
        tips.append({
            "metric": "frontier_navigation",
            "severity": "high",
            "message": "Quality is not matching resource spend. Improve prompt precision and reduce redundant context/calls.",
        })
    if scores.get("reliance_calibration", 1.0) < 0.65:
        tips.append({
            "metric": "reliance_calibration",
            "severity": "high",
            "message": "AI reliance is weakly calibrated. Add stronger output validation and bounded retry/fallback logic.",
        })
    if scores.get("leverage_gain", 0.05) <= 0.0:
        tips.append({
            "metric": "leverage_gain",
            "severity": "high",
            "message": "Submission is not outperforming counterfactual baseline. Improve your AI strategy before further tuning.",
        })
    if not tips:
        tips.append({
            "metric": "summary",
            "severity": "low",
            "message": "Balanced submission: no critical weaknesses detected in this run set.",
        })

    return tips


def _build_hidden_cases(
    challenge_config: dict[str, Any],
    default_ground_truth: str,
    default_accuracy_mode: str,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    hidden_tests = challenge_config.get("hidden_tests")
    if isinstance(hidden_tests, list):
        _append_hidden_cases(
            cases, hidden_tests, "hidden", default_ground_truth, default_accuracy_mode
        )
    elif isinstance(hidden_tests, dict):
        for tier_name, tier_cases in hidden_tests.items():
            if not isinstance(tier_cases, list):
                continue
            _append_hidden_cases(
                cases,
                tier_cases,
                str(tier_name),
                default_ground_truth,
                default_accuracy_mode,
            )
    return cases


def _append_hidden_cases(
    dest: list[dict[str, Any]],
    hidden_cases: list[dict[str, Any]],
    tier_name: str,
    default_ground_truth: str,
    default_accuracy_mode: str,
) -> None:
    for i, case in enumerate(hidden_cases):
        if not isinstance(case, dict) or "inputs" not in case:
            continue
        gt = case.get("ground_truth", default_ground_truth)
        if isinstance(gt, (list, dict)):
            gt = json.dumps(gt)
        dest.append(
            {
                "name": str(case.get("name", f"{tier_name}_{i+1}")),
                "inputs": case["inputs"],
                "ground_truth": gt,
                "accuracy_mode": str(case.get("accuracy_mode", default_accuracy_mode)),
            }
        )


def _detect_metric_gaming(
    *,
    runs: list[dict[str, Any]],
    total_tokens: int,
    total_calls: int,
    accuracy: float,
    robustness: float,
) -> dict[str, Any]:
    if not runs:
        return {"triggered": False, "reason": ""}

    avg_output_chars = sum(r.get("output_chars", 0) for r in runs) / max(1, len(runs))
    minimal_usage = total_tokens <= max(120, len(runs) * 20) and total_calls <= max(1, len(runs) // 2)
    low_quality = accuracy < 0.65 or robustness < 0.55
    low_effort_output = avg_output_chars < 24
    output_hashes = [r.get("output_hash") for r in runs if r.get("output_hash")]
    unique_ratio = (len(set(output_hashes)) / len(output_hashes)) if output_hashes else 1.0
    suspicious_repeat_pattern = len(output_hashes) >= 4 and unique_ratio < 0.35 and robustness < 0.6
    low_schema_validity = (sum(1 for r in runs if r.get("schema_valid")) / len(runs)) < 0.5

    if minimal_usage and low_quality and low_effort_output:
        return {
            "triggered": True,
            "reason": "Potential metric gaming detected: extremely low usage plus low-quality/low-effort outputs.",
        }
    if suspicious_repeat_pattern and low_schema_validity:
        return {
            "triggered": True,
            "reason": "Potential metric gaming detected: repetitive outputs with weak schema adherence under perturbations.",
        }
    return {"triggered": False, "reason": ""}


def _detect_hardcoding(
    total_calls: int,
    accuracies: list[float],
    code: str,
    ground_truth: str,
) -> bool:
    mean_acc = sum(accuracies) / len(accuracies) if accuracies else 0.0

    if total_calls == 0 and mean_acc > 0.3:
        return True

    if total_calls == 0:
        return True

    code_lower = code.lower()
    try:
        gt = json.loads(ground_truth) if isinstance(ground_truth, str) else ground_truth
    except (json.JSONDecodeError, TypeError):
        gt = None

    if gt:
        embedded_count = _count_gt_fragments_in_code(gt, code_lower)
        if embedded_count >= 3:
            return True

    if total_calls <= 1 and mean_acc > 0.95 and len(accuracies) >= 5:
        all_perfect = all(a > 0.9 for a in accuracies)
        if all_perfect:
            return True

    return False


def _count_gt_fragments_in_code(gt: Any, code_lower: str) -> int:
    count = 0

    if isinstance(gt, dict):
        for v in gt.values():
            count += _count_gt_fragments_in_code(v, code_lower)
    elif isinstance(gt, list):
        for item in gt:
            count += _count_gt_fragments_in_code(item, code_lower)
    elif isinstance(gt, str) and len(gt) > 5:
        if gt.lower() in code_lower:
            count += 1
    elif isinstance(gt, (int, float)):
        if str(gt) in code_lower and gt not in (0, 1, 0.0, 1.0):
            count += 1

    return count


def _process_run(
    result: SandboxResult,
    ground_truth: str,
    accuracy_mode: str,
    run_type: str,
    run_index: int,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    telemetry = result.telemetry
    prompt_tokens = sum(r.get("tokens_prompt", 0) for r in telemetry)
    completion_tokens = sum(r.get("tokens_completion", 0) for r in telemetry)
    tokens = sum(r.get("tokens_total", 0) for r in telemetry)
    cost = sum(r.get("cost_usd", 0.0) for r in telemetry)
    latency = sum(r.get("latency_ms", 0.0) for r in telemetry)
    calls = len(telemetry)
    retries = sum(1 for r in telemetry if r.get("retry_index", 0) > 0)

    acc = 0.0
    schema_valid = False
    confidence = None
    output_chars = 0
    if result.success:
        raw = result.output.strip()
        output_chars = len(raw)
        output_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else None
        acc = score_accuracy(raw, ground_truth, mode=accuracy_mode)
        schema_valid = _is_schema_valid(raw, accuracy_mode, ground_truth)
        confidence = _extract_confidence_value(raw)
    else:
        output_hash = None

    status = "pass" if (result.success and acc >= 0.8 and schema_valid) else "fail"

    return {
        "run_type": run_type,
        "run_index": run_index,
        "success": result.success,
        "status": status,
        "accuracy": round(acc, 4),
        "schema_valid": schema_valid,
        "confidence": confidence,
        "output_chars": output_chars,
        "output_hash": output_hash,
        "tokens_prompt": prompt_tokens,
        "tokens_completion": completion_tokens,
        "tokens_total": tokens,
        "cost_usd": round(cost, 6),
        "latency_ms": round(latency, 2),
        "llm_calls": calls,
        "retries": retries,
        "error": result.error,
        "meta": meta or {},
    }


def _is_schema_valid(output: str, accuracy_mode: str, ground_truth: str) -> bool:
    if accuracy_mode != "json":
        return bool(output.strip())
    try:
        got = json.loads(output)
        expected = json.loads(ground_truth) if isinstance(ground_truth, str) else ground_truth
        return _validate_shape(got, expected)
    except Exception:
        return False


def _extract_confidence_value(output: str) -> float | None:
    try:
        data = json.loads(output)
    except Exception:
        return None

    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (int, float)) and any(t in k.lower() for t in ("confidence", "probability", "prob")):
                return float(v)
    return None


def _validate_shape(got: Any, expected: Any) -> bool:
    if expected is None:
        return got is None
    if isinstance(expected, bool):
        return isinstance(got, bool)
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return isinstance(got, (int, float)) and not isinstance(got, bool)
    if isinstance(expected, str):
        return isinstance(got, str)
    if isinstance(expected, list):
        if not isinstance(got, list):
            return False
        if not expected:
            return True
        sample = expected[0]
        return all(_validate_shape(item, sample) for item in got)
    if isinstance(expected, dict):
        if not isinstance(got, dict):
            return False
        for key, exp_val in expected.items():
            if key not in got:
                return False
            if not _validate_shape(got[key], exp_val):
                return False
        return True
    return True


def _mean_confidence_interval(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "n": 0,
            "mean": 0.0,
            "lower_95": 0.0,
            "upper_95": 0.0,
            "half_width": 0.0,
            "method": "normal_approx",
        }
    n = len(values)
    mean = sum(values) / n
    if n == 1:
        lower = upper = mean
    else:
        variance = sum((v - mean) ** 2 for v in values) / n
        std = variance ** 0.5
        half = 1.96 * (std / (n ** 0.5))
        lower = max(0.0, mean - half)
        upper = min(1.0, mean + half)
    return {
        "n": n,
        "mean": round(mean, 4),
        "lower_95": round(lower, 4),
        "upper_95": round(upper, 4),
        "half_width": round((upper - lower) / 2, 4),
        "method": "normal_approx",
    }


def _proportion_confidence_interval(successes: int, total: int) -> dict[str, Any]:
    if total <= 0:
        return {
            "n": 0,
            "rate": 0.0,
            "lower_95": 0.0,
            "upper_95": 0.0,
            "half_width": 0.0,
            "method": "wilson",
        }

    z = 1.96
    p = successes / total
    denom = 1.0 + (z**2 / total)
    center = (p + (z**2 / (2 * total))) / denom
    margin = (
        z
        * (
            ((p * (1 - p)) / total)
            + ((z**2) / (4 * (total**2)))
        )
        ** 0.5
    ) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return {
        "n": total,
        "rate": round(p, 4),
        "lower_95": round(lower, 4),
        "upper_95": round(upper, 4),
        "half_width": round((upper - lower) / 2, 4),
        "method": "wilson",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_leverage_gain(gain: float) -> float:
    # Maps [-0.10, +0.30] roughly to [0, 1] with clamping.
    return max(0.0, min(1.0, (float(gain) + 0.10) / 0.40))


def _compute_credibility(
    *,
    prompt_judge_method: str,
    calibration_samples: int,
    run_count: int,
    hidden_set_count: int,
    run_type_coverage: float,
    counterfactual_status: str,
    anti_gaming_triggered: bool,
    hardcoded: bool,
    run_accuracy_ci_half_width: float,
) -> dict[str, Any]:
    score = 0.0

    score += 0.22 if prompt_judge_method == "llm_judge" else 0.10
    score += min(0.15, (max(0, calibration_samples) / 12.0) * 0.15)
    score += min(0.15, (max(0, run_count) / 8.0) * 0.15)
    score += 0.10 if hidden_set_count > 0 else 0.03
    score += max(0.0, min(1.0, float(run_type_coverage))) * 0.08
    if counterfactual_status == "ok":
        score += 0.15
    elif counterfactual_status == "disabled":
        score += 0.06
    else:
        score += 0.03
    ci_quality = max(0.0, min(1.0, 1.0 - (max(0.0, run_accuracy_ci_half_width) / 0.20)))
    score += ci_quality * 0.13

    if anti_gaming_triggered:
        score -= 0.25
    if hardcoded:
        score -= 0.50

    bounded = max(0.0, min(1.0, score))
    band = "high" if bounded >= 0.75 else ("medium" if bounded >= 0.55 else "low")
    return {
        "score": round(bounded, 4),
        "band": band,
        "signals": {
            "prompt_judge_method": prompt_judge_method,
            "calibration_samples": calibration_samples,
            "run_count": run_count,
            "hidden_set_count": hidden_set_count,
            "run_type_coverage": round(float(run_type_coverage), 4),
            "counterfactual_status": counterfactual_status,
            "anti_gaming_triggered": anti_gaming_triggered,
            "hardcoded": hardcoded,
            "run_accuracy_ci_half_width": round(run_accuracy_ci_half_width, 4),
        },
        "method": "credibility_v1",
    }


async def _evaluate_counterfactual_baseline_async(
    *,
    run_plan: list[dict[str, Any]],
    challenge_config: dict[str, Any],
) -> dict[str, Any]:
    """Run the blocking counterfactual baseline off the event loop."""
    return await asyncio.to_thread(
        _evaluate_counterfactual_baseline_sync,
        run_plan=run_plan,
        challenge_config=challenge_config,
    )


def _evaluate_counterfactual_baseline_sync(
    *,
    run_plan: list[dict[str, Any]],
    challenge_config: dict[str, Any],
) -> dict[str, Any]:
    if not bool(challenge_config.get("counterfactual_baseline_enabled", True)):
        return {"status": "disabled", "reason": "counterfactual_baseline_disabled"}
    if not run_plan:
        return {"status": "error", "reason": "empty_run_plan"}

    try:
        challenge_description = str(challenge_config.get("description", ""))
        variants = _counterfactual_strategy_variants(challenge_config)
        variant_results: list[dict[str, Any]] = []
        for variant in variants:
            baseline_code = _build_counterfactual_baseline_code(
                challenge_config,
                challenge_description,
                strategy_prompt=variant["prompt"],
            )
            result = _run_counterfactual_candidate(
                baseline_code=baseline_code,
                run_plan=run_plan,
                challenge_config=challenge_config,
                challenge_description=challenge_description,
            )
            result["strategy_id"] = variant["id"]
            variant_results.append(result)

        ok_results = [r for r in variant_results if r.get("status") == "ok"]
        if not ok_results:
            return {
                "status": "error",
                "reason": "all_counterfactual_variants_failed",
                "variants": variant_results,
            }

        sorted_ok = sorted(ok_results, key=lambda r: float(r.get("overall") or 0.0))
        median = sorted_ok[len(sorted_ok) // 2]
        aggregate_overall = round(float(median.get("overall") or 0.0), 4)
        aggregate_raw = round(float(median.get("raw_overall") or 0.0), 4)

        merged = dict(median)
        merged["overall"] = aggregate_overall
        merged["raw_overall"] = aggregate_raw
        merged["aggregate"] = {
            "method": "median_overall",
            "variant_overalls": [
                {
                    "strategy_id": str(r.get("strategy_id") or "unknown"),
                    "overall": round(float(r.get("overall") or 0.0), 4),
                }
                for r in sorted_ok
            ],
            "selected_strategy_id": str(median.get("strategy_id") or "unknown"),
            "variants_ok": len(ok_results),
            "variants_total": len(variant_results),
        }
        merged["method"] = "sandbox_counterfactual_multi_v1"
        return merged
    except Exception as exc:
        logger.exception("Counterfactual baseline evaluation failed")
        return {"status": "error", "reason": str(exc)}


def _run_counterfactual_candidate(
    *,
    baseline_code: str,
    run_plan: list[dict[str, Any]],
    challenge_config: dict[str, Any],
    challenge_description: str,
) -> dict[str, Any]:
    run_records: list[dict[str, Any]] = []
    clean_accuracies: list[float] = []
    perturbed_accuracies: list[float] = []
    adversarial_accuracies: list[float] = []
    all_telemetry: list[dict[str, Any]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    total_calls = 0
    total_retries = 0

    for spec in run_plan:
        result = run_in_sandbox(
            baseline_code,
            "counterfactual_baseline.py",
            challenge_config,
            input_overrides=spec["inputs"],
        )
        record = _process_run(
            result,
            spec["ground_truth"],
            spec["accuracy_mode"],
            spec["run_type"],
            spec["run_index"],
            meta=spec.get("meta"),
        )
        run_records.append(record)
        if spec["run_type"] in ("clean", "hidden_clean"):
            clean_accuracies.append(record["accuracy"])
        elif spec["run_type"] == "perturbed":
            perturbed_accuracies.append(record["accuracy"])
        elif spec["run_type"] == "adversarial":
            adversarial_accuracies.append(record["accuracy"])

        all_telemetry.extend(result.telemetry)
        total_prompt_tokens += record["tokens_prompt"]
        total_completion_tokens += record["tokens_completion"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

    all_accuracies = clean_accuracies + perturbed_accuracies + adversarial_accuracies
    acc = round(sum(clean_accuracies) / len(clean_accuracies), 4) if clean_accuracies else 0.0
    robustness = _score_robustness(perturbed_accuracies, adversarial_accuracies)
    rel = score_reliability(all_accuracies)
    rule_adherence = _score_constraint_adherence(run_records)
    quality_anchor = (acc * 0.5) + (robustness * 0.3) + (rel * 0.2)
    run_count = max(1, len(run_records))
    budgets = {
        "token_budget": challenge_config.get("token_budget", 12_000),
        "cost_budget_usd": challenge_config.get("cost_budget_usd", 0.20),
        "latency_budget_ms": challenge_config.get("latency_budget_ms", 30_000),
        "call_budget": challenge_config.get("call_budget", challenge_config.get("expected_calls", 3) * run_count),
    }
    eff = score_efficiency_tradeoff(
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        total_calls=total_calls,
        quality_anchor=quality_anchor,
        budgets=budgets,
    )
    pq_result = score_prompt_quality(all_telemetry, challenge_description)
    pq = round(float(pq_result.get("overall", 0.0)), 4)
    if pq_result.get("method") == "heuristic":
        pq = min(pq, 0.65)

    orch = score_orchestration(
        total_calls,
        total_retries,
        expected_calls=challenge_config.get("expected_calls", 3),
        code_analysis=None,
    )
    calibration_points = _extract_confidence_points(run_records)
    calibration_result = score_calibration(calibration_points)
    calibration = float(calibration_result.get("score", 0.5))

    metric_gaming = _detect_metric_gaming(
        runs=run_records,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_calls=total_calls,
        accuracy=acc,
        robustness=robustness,
    )
    if metric_gaming["triggered"]:
        eff = min(eff, 0.25)
        orch = min(orch, 0.5)

    raw_overall = round(
        acc * SCORE_WEIGHTS["accuracy"]
        + robustness * SCORE_WEIGHTS["robustness"]
        + rel * SCORE_WEIGHTS["reliability"]
        + eff * SCORE_WEIGHTS["efficiency"]
        + pq * SCORE_WEIGHTS["prompt_quality"]
        + orch * SCORE_WEIGHTS["orchestration"]
        + calibration * SCORE_WEIGHTS["calibration"],
        4,
    )
    overall, cap_events = _apply_overall_caps(
        raw_overall=raw_overall,
        accuracy=acc,
        rule_adherence=rule_adherence,
        anti_gaming_triggered=metric_gaming["triggered"],
    )
    overall, confidence_cap_events = _apply_confidence_caps(
        overall=overall,
        prompt_judge_method=str(pq_result.get("method") or "unknown"),
        calibration_samples=calibration_samples,
        run_accuracy_ci_half_width=run_accuracy_ci_half_width,
    )
    cap_events.extend(confidence_cap_events)
    return {
        "status": "ok",
        "overall": overall,
        "raw_overall": raw_overall,
        "metrics": {
            "accuracy": acc,
            "robustness": robustness,
            "reliability": rel,
            "efficiency": eff,
            "prompt_quality": pq,
            "orchestration": orch,
            "calibration": round(calibration, 4),
            "rule_adherence": rule_adherence,
        },
        "run_count": len(run_records),
        "tests_passed": sum(1 for r in run_records if r.get("status") == "pass"),
        "cap_events": cap_events,
        "anti_gaming_triggered": metric_gaming["triggered"],
        "usage": {
            "llm_calls": total_calls,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "cost_usd": round(total_cost, 6),
            "latency_ms": round(total_latency, 2),
        },
        "method": "sandbox_counterfactual_v1",
    }


def _counterfactual_strategy_variants(challenge_config: dict[str, Any]) -> list[dict[str, str]]:
    default_variants = [
        {
            "id": "strict_schema",
            "prompt": (
                "Follow schema exactly and return ONLY valid JSON with exact keys/types. "
                "Use null for unknowns, never prose, never markdown."
            ),
        },
        {
            "id": "normalize_and_extract",
            "prompt": (
                "Normalize dates/currency/names before extraction, then emit strict JSON only. "
                "Apply processing rules and avoid extra commentary."
            ),
        },
        {
            "id": "evidence_guardrail",
            "prompt": (
                "Verify every field against explicit input evidence before final output. "
                "If uncertain or unsupported, emit null rather than guessing."
            ),
        },
    ]
    requested = int(challenge_config.get("counterfactual_variants", 3) or 3)
    requested = max(1, min(3, requested))
    return default_variants[:requested]


def _build_counterfactual_baseline_code(
    challenge_config: dict[str, Any],
    challenge_description: str,
    *,
    strategy_prompt: str = "",
) -> str:
    template = _counterfactual_template_for_challenge(challenge_config)
    model_name = str(challenge_config.get("counterfactual_model", "gpt-4o-mini"))
    max_tokens = int(challenge_config.get("counterfactual_max_tokens", 1400))
    max_retries = max(1, min(3, int(challenge_config.get("counterfactual_retries", 2) or 2)))
    rules_preview = json.dumps(
        challenge_config.get("processing_rules", {}),
        ensure_ascii=False,
    )
    ground_truth = challenge_config.get("ground_truth", "")
    if isinstance(ground_truth, (dict, list)):
        schema_preview = json.dumps(ground_truth, ensure_ascii=False)
    else:
        schema_preview = str(ground_truth)
    if len(schema_preview) > 2400:
        schema_preview = schema_preview[:2400] + " ..."
    if len(rules_preview) > 1600:
        rules_preview = rules_preview[:1600] + " ..."
    description_preview = challenge_description.strip()
    if len(description_preview) > 1600:
        description_preview = description_preview[:1600] + " ..."

    return f"""import json
from pathlib import Path
from promptcode import llm

MODEL = {json.dumps(model_name)}
MAX_TOKENS = {max_tokens}
MAX_RETRIES = {max_retries}
DESCRIPTION = {json.dumps(description_preview)}
RULES = {json.dumps(rules_preview)}
SCHEMA = {json.dumps(schema_preview)}
TASK_FOCUS = {json.dumps(template["task_focus"])}
SYSTEM_PROMPT = {json.dumps(template["system_prompt"])}
STRATEGY_PROMPT = {json.dumps(strategy_prompt)}


def _load_input() -> str:
    p = Path("/workspace/input.json")
    if not p.exists():
        return ""
    return p.read_text()


def _to_valid_json(text: str) -> str:
    raw = (text or "").strip()
    try:
        json.loads(raw)
        return raw
    except Exception:
        pass

    repair_prompt = (
        "Fix the following output into valid JSON matching the target schema.\\n\\n"
        + "Schema example:\\n" + SCHEMA + "\\n\\n"
        + "Broken output:\\n" + raw + "\\n\\n"
        + "Return ONLY valid JSON."
    )
    repaired = llm.call(
        model=MODEL,
        prompt=repair_prompt,
        system="You are a strict JSON repair assistant. Return ONLY valid JSON.",
        temperature=0,
        max_tokens=min(800, MAX_TOKENS),
        retries=1,
    )
    repaired = (repaired or "").strip()
    try:
        json.loads(repaired)
        return repaired
    except Exception:
        # Ensure parseable output even when model repair fails.
        return "{{}}"


raw_input = _load_input()
prompt = (
    "Solve the task using the input payload and return only valid JSON.\\n\\n"
    + "Strategy:\\n" + STRATEGY_PROMPT + "\\n\\n"
    + "Task focus:\\n" + TASK_FOCUS + "\\n\\n"
    + "Task:\\n" + DESCRIPTION + "\\n\\n"
    + "Normalization rules:\\n" + RULES + "\\n\\n"
    + "Expected output schema example:\\n" + SCHEMA + "\\n\\n"
    + "Input payload:\\n" + raw_input + "\\n\\n"
    + "Return ONLY JSON with no markdown."
)

response = llm.call(
    model=MODEL,
    prompt=prompt,
    system=SYSTEM_PROMPT,
    temperature=0,
    max_tokens=MAX_TOKENS,
    retries=MAX_RETRIES,
)
print(_to_valid_json(response))
"""


def _counterfactual_template_for_challenge(challenge_config: dict[str, Any]) -> dict[str, str]:
    slug = str(challenge_config.get("challenge_slug") or "").strip().lower()
    category = str(challenge_config.get("challenge_category") or "").strip().lower()

    by_slug: dict[str, dict[str, str]] = {
        "extract-structured-claims": {
            "task_focus": "Extract normalized insurance claim fields exactly and skip invalid/test records.",
            "system_prompt": "You are a strict insurance-claims extraction assistant. Output valid JSON only.",
        },
        "review-sentiment-synthesis": {
            "task_focus": "Synthesize review themes, sentiment, and prioritized product actions in structured JSON.",
            "system_prompt": "You are a customer-feedback analysis assistant. Output valid JSON only.",
        },
        "natural-language-to-sql": {
            "task_focus": "Map natural-language questions to correct SQL outputs using provided schema constraints.",
            "system_prompt": "You are a careful analytics assistant. Produce schema-constrained JSON only.",
        },
        "bug-report-dedup-triage": {
            "task_focus": "Cluster duplicate bugs and produce triage priority, owner routing, and root-cause hypotheses.",
            "system_prompt": "You are a software bug-triage assistant. Output valid JSON only.",
        },
        "email-thread-action-items": {
            "task_focus": "Extract actionable tasks, owners, deadlines, and risks from email threads.",
            "system_prompt": "You are an operations action-item extraction assistant. Output valid JSON only.",
        },
        "support-ticket-routing": {
            "task_focus": "Route support tickets to the right team with priority and concise reason.",
            "system_prompt": "You are a support triage assistant. Output valid JSON only.",
        },
        "resume-parsing-pipeline": {
            "task_focus": "Parse resumes into normalized structured candidate profiles with robust field handling.",
            "system_prompt": "You are a resume parsing assistant. Output valid JSON only.",
        },
        "contract-clause-extraction": {
            "task_focus": "Extract clause spans, classify clause types, and assign risk levels from legal contracts.",
            "system_prompt": "You are a legal clause extraction assistant. Output valid JSON only.",
        },
        "legacy-api-xml-to-json": {
            "task_focus": "Transform legacy XML responses into target JSON schema with strict normalization.",
            "system_prompt": "You are an enterprise data migration assistant. Output valid JSON only.",
        },
        "financial-anomaly-detection": {
            "task_focus": "Identify suspicious transactions and return categorized anomaly signals with evidence.",
            "system_prompt": "You are a financial anomaly detection assistant. Output valid JSON only.",
        },
    }
    if slug in by_slug:
        return by_slug[slug]

    by_category: dict[str, dict[str, str]] = {
        "extraction": {
            "task_focus": "Extract and normalize structured fields from noisy inputs.",
            "system_prompt": "You are a structured data extraction assistant. Output valid JSON only.",
        },
        "analysis": {
            "task_focus": "Analyze inputs and return concise structured findings.",
            "system_prompt": "You are an analysis assistant. Output valid JSON only.",
        },
    }
    if category in by_category:
        return by_category[category]
    return {
        "task_focus": "Follow task description exactly and return strict JSON output.",
        "system_prompt": "You are a strict structured output assistant. Output valid JSON only.",
    }


def _default_evaluation_seed(challenge_config: dict[str, Any]) -> int:
    payload = {
        "accuracy_mode": challenge_config.get("accuracy_mode", "json"),
        "inputs": challenge_config.get("inputs", {}),
        "ground_truth": challenge_config.get("ground_truth", ""),
        "processing_rules": challenge_config.get("processing_rules", {}),
        "hidden_tests": challenge_config.get("hidden_tests", {}),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    # Keep within signed 31-bit positive range for compatibility.
    return (int(digest[:12], 16) % (2**31 - 1)) + 1


def _apply_overall_caps(
    *,
    raw_overall: float,
    accuracy: float,
    rule_adherence: float,
    anti_gaming_triggered: bool,
) -> tuple[float, list[dict[str, Any]]]:
    overall = raw_overall
    events: list[dict[str, Any]] = []
    if accuracy < 0.40:
        overall = min(overall, 0.55)
        events.append({"cap": 0.55, "reason": "accuracy_below_0.40"})
    if rule_adherence < 0.50:
        overall = min(overall, 0.50)
        events.append({"cap": 0.50, "reason": "rule_adherence_below_0.50"})
    if anti_gaming_triggered:
        overall = min(overall, 0.45)
        events.append({"cap": 0.45, "reason": "anti_gaming_triggered"})
    return round(overall, 4), events


def _apply_confidence_caps(
    *,
    overall: float,
    prompt_judge_method: str,
    calibration_samples: int,
    run_accuracy_ci_half_width: float,
) -> tuple[float, list[dict[str, Any]]]:
    capped = float(overall)
    events: list[dict[str, Any]] = []

    if prompt_judge_method != "llm_judge":
        capped = min(capped, 0.78)
        events.append({"cap": 0.78, "reason": "prompt_judge_not_llm"})

    if run_accuracy_ci_half_width >= 0.20:
        capped = min(capped, 0.70)
        events.append({"cap": 0.70, "reason": "run_accuracy_ci_half_width_ge_0.20"})
    elif run_accuracy_ci_half_width >= 0.15:
        capped = min(capped, 0.76)
        events.append({"cap": 0.76, "reason": "run_accuracy_ci_half_width_ge_0.15"})

    if calibration_samples <= 1:
        capped = min(capped, 0.80)
        events.append({"cap": 0.80, "reason": "calibration_samples_le_1"})
    elif calibration_samples <= 3:
        capped = min(capped, 0.84)
        events.append({"cap": 0.84, "reason": "calibration_samples_le_3"})

    return round(capped, 4), events


def _build_evaluation_manifest(
    *,
    entrypoint: str,
    challenge_config: dict[str, Any],
    evaluation_seed: int,
    run_plan: list[dict[str, Any]],
    run_records: list[dict[str, Any]],
    scores: dict[str, float],
) -> dict[str, Any]:
    challenge_fingerprint_payload = {
        "accuracy_mode": challenge_config.get("accuracy_mode", "json"),
        "expected_calls": challenge_config.get("expected_calls", 3),
        "processing_rules": challenge_config.get("processing_rules", {}),
        "budgets": {
            "token_budget": challenge_config.get("token_budget", 12_000),
            "cost_budget_usd": challenge_config.get("cost_budget_usd", 0.20),
            "latency_budget_ms": challenge_config.get("latency_budget_ms", 30_000),
            "call_budget": challenge_config.get("call_budget"),
        },
        "hidden_tests": challenge_config.get("hidden_tests", {}),
    }
    challenge_fingerprint = _hash_payload(challenge_fingerprint_payload)
    run_plan_fingerprint = _hash_payload(
        [
            {
                "run_type": spec.get("run_type"),
                "run_index": spec.get("run_index"),
                "meta": spec.get("meta", {}),
            }
            for spec in run_plan
        ]
    )
    run_records_fingerprint = _hash_payload(
        [
            {
                "run_type": r.get("run_type"),
                "run_index": r.get("run_index"),
                "status": r.get("status"),
                "accuracy": r.get("accuracy"),
                "schema_valid": r.get("schema_valid"),
                "tokens_total": r.get("tokens_total"),
                "cost_usd": r.get("cost_usd"),
                "latency_ms": r.get("latency_ms"),
                "llm_calls": r.get("llm_calls"),
                "retries": r.get("retries"),
                "meta": r.get("meta", {}),
            }
            for r in run_records
        ]
    )
    replay_hash = _hash_payload(
        {
            "entrypoint": entrypoint,
            "evaluation_seed": evaluation_seed,
            "challenge_fingerprint": challenge_fingerprint,
            "run_plan_fingerprint": run_plan_fingerprint,
            "run_records_fingerprint": run_records_fingerprint,
            "scores": scores,
            "scoring_weights": SCORE_WEIGHTS,
            "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
        }
    )

    return {
        "version": 1,
        "entrypoint": entrypoint,
        "evaluation_seed": evaluation_seed,
        "challenge_fingerprint": challenge_fingerprint,
        "run_plan_fingerprint": run_plan_fingerprint,
        "run_records_fingerprint": run_records_fingerprint,
        "replay_hash": replay_hash,
        "scoring_weights": SCORE_WEIGHTS,
        "perturbation_config_version": PERTURBATION_CONFIG_VERSION,
    }


def _hash_payload(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_usage_breakdown(
    telemetry_calls: list[dict[str, Any]],
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    model_stats: dict[str, dict[str, float | int]] = {}
    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    total_cost = 0.0
    total_latency = 0.0
    total_calls = 0
    total_retries = 0

    for call in telemetry_calls:
        model = str(call.get("model") or "unknown")
        prompt_tokens = int(call.get("tokens_prompt") or 0)
        completion_tokens = int(call.get("tokens_completion") or 0)
        tokens_total = int(call.get("tokens_total") or (prompt_tokens + completion_tokens))
        cost_usd = float(call.get("cost_usd") or 0.0)
        latency_ms = float(call.get("latency_ms") or 0.0)
        retry_index = int(call.get("retry_index") or 0)

        total_prompt += prompt_tokens
        total_completion += completion_tokens
        total_tokens += tokens_total
        total_cost += cost_usd
        total_latency += latency_ms
        total_calls += 1
        if retry_index > 0:
            total_retries += 1

        if model not in model_stats:
            model_stats[model] = {
                "model": model,
                "calls": 0,
                "retries": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": 0.0,
            }
        entry = model_stats[model]
        entry["calls"] = int(entry["calls"]) + 1
        if retry_index > 0:
            entry["retries"] = int(entry["retries"]) + 1
        entry["prompt_tokens"] = int(entry["prompt_tokens"]) + prompt_tokens
        entry["completion_tokens"] = int(entry["completion_tokens"]) + completion_tokens
        entry["total_tokens"] = int(entry["total_tokens"]) + tokens_total
        entry["cost_usd"] = float(entry["cost_usd"]) + cost_usd
        entry["latency_ms"] = float(entry["latency_ms"]) + latency_ms

    models = sorted(
        (
            {
                "model": m["model"],
                "calls": int(m["calls"]),
                "retries": int(m["retries"]),
                "prompt_tokens": int(m["prompt_tokens"]),
                "completion_tokens": int(m["completion_tokens"]),
                "total_tokens": int(m["total_tokens"]),
                "cost_usd": round(float(m["cost_usd"]), 6),
                "latency_ms": round(float(m["latency_ms"]), 2),
                "avg_tokens_per_call": round(
                    int(m["total_tokens"]) / max(1, int(m["calls"])),
                    2,
                ),
                "avg_latency_ms": round(
                    float(m["latency_ms"]) / max(1, int(m["calls"])),
                    2,
                ),
            }
            for m in model_stats.values()
        ),
        key=lambda row: float(row["cost_usd"]),
        reverse=True,
    )

    run_type_stats: dict[str, dict[str, float | int]] = {}
    for run in runs:
        run_type = str(run.get("run_type") or "unknown")
        if run_type not in run_type_stats:
            run_type_stats[run_type] = {
                "run_type": run_type,
                "runs": 0,
                "passes": 0,
                "llm_calls": 0,
                "tokens_total": 0,
                "cost_usd": 0.0,
                "latency_ms": 0.0,
            }
        bucket = run_type_stats[run_type]
        bucket["runs"] = int(bucket["runs"]) + 1
        if run.get("status") == "pass":
            bucket["passes"] = int(bucket["passes"]) + 1
        bucket["llm_calls"] = int(bucket["llm_calls"]) + int(run.get("llm_calls") or 0)
        bucket["tokens_total"] = int(bucket["tokens_total"]) + int(run.get("tokens_total") or 0)
        bucket["cost_usd"] = float(bucket["cost_usd"]) + float(run.get("cost_usd") or 0.0)
        bucket["latency_ms"] = float(bucket["latency_ms"]) + float(run.get("latency_ms") or 0.0)

    run_types = sorted(
        (
            {
                "run_type": r["run_type"],
                "runs": int(r["runs"]),
                "passes": int(r["passes"]),
                "pass_rate": round(int(r["passes"]) / max(1, int(r["runs"])), 4),
                "llm_calls": int(r["llm_calls"]),
                "tokens_total": int(r["tokens_total"]),
                "cost_usd": round(float(r["cost_usd"]), 6),
                "latency_ms": round(float(r["latency_ms"]), 2),
            }
            for r in run_type_stats.values()
        ),
        key=lambda row: str(row["run_type"]),
    )

    return {
        "totals": {
            "calls": total_calls,
            "retries": total_retries,
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_tokens": total_tokens,
            "cost_usd": round(total_cost, 6),
            "latency_ms": round(total_latency, 2),
            "avg_tokens_per_call": round(total_tokens / max(1, total_calls), 2),
            "avg_latency_ms": round(total_latency / max(1, total_calls), 2),
            "avg_cost_per_call": round(total_cost / max(1, total_calls), 6),
        },
        "models": models,
        "run_types": run_types,
        "method": "telemetry_aggregation_v1",
    }
