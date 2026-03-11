"""Evaluation engine: multi-run sandbox scoring with quality, robustness, and efficiency tradeoffs."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from functools import partial
from typing import Any

from app.core.config import get_settings
from app.services.evaluation.code_analysis import analyze_code, score_code_quality
from app.services.evaluation.constants import PERTURBATION_CONFIG_VERSION, SCORE_WEIGHTS
from app.services.evaluation.counterfactual import (
    _evaluate_counterfactual_baseline_sync,
)
from app.services.evaluation.helpers import (
    _build_diagnostics,
    _build_hidden_cases,
    _compute_run_type_coverage,
    _detect_hardcoding,
    _detect_metric_gaming,
    _extract_confidence_points,
    _process_run,
    _score_constraint_adherence,
    _score_robustness,
)
from app.services.evaluation.prompt_quality import score_prompt_quality
from app.services.evaluation.reporting import (
    _apply_confidence_caps,
    _apply_overall_caps,
    _build_evaluation_manifest,
    _build_usage_breakdown,
    _compute_credibility,
    _default_evaluation_seed,
    _mean_confidence_interval,
    _normalize_leverage_gain,
    _now_iso,
    _proportion_confidence_interval,
)
from app.services.evaluation.result import EvaluationResult
from app.services.evaluation.scorer import (
    score_ai_mastery,
    score_calibration,
    score_efficiency_tradeoff,
    score_frontier_navigation,
    score_orchestration,
    score_reliability,
    score_reliance_calibration,
)
from app.services.evaluation.weight_profile import get_weight_profile
from app.services.sandbox.runner import SandboxResult, run_in_sandbox

logger = logging.getLogger(__name__)
settings = get_settings()


def _evaluation_max_parallel_specs() -> int:
    configured = int(settings.evaluation_max_parallel_specs or 0)
    return max(1, configured)


async def _run_all_specs_in_parallel(
    run_plan: list[dict[str, Any]],
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
) -> list[tuple[dict[str, Any], SandboxResult]]:
    """Execute all specs in parallel using the thread pool."""
    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(max(1, min(len(run_plan) or 1, _evaluation_max_parallel_specs())))

    async def run_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], SandboxResult]:
        async with semaphore:
            runner = partial(
                run_in_sandbox,
                code,
                entrypoint,
                challenge_config,
                input_overrides=spec["inputs"],
            )
            result = await loop.run_in_executor(None, runner)
        return spec, result

    return await asyncio.gather(*(run_spec(spec) for spec in run_plan))


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


async def evaluate_submission(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
) -> EvaluationResult:
    """Run full evaluation across clean, perturbed, and adversarial runs."""

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
        from app.services.evaluation.perturbation import perturb_normal

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
        from app.services.evaluation.perturbation import perturb_adversarial

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

    spec_results = await _run_all_specs_in_parallel(run_plan, code, entrypoint, challenge_config)

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
    accuracy_ci = _mean_confidence_interval(clean_accuracies)
    robustness_ci = _mean_confidence_interval(perturbed_accuracies + adversarial_accuracies)
    run_accuracy_ci = _mean_confidence_interval(all_accuracies)
    pass_rate_ci = _proportion_confidence_interval(
        sum(1 for r in run_records if r.get("status") == "pass"),
        len(run_records),
    )
    run_accuracy_ci_half_width = float(run_accuracy_ci.get("half_width") or 0.0)

    prompt_judge_fallback = pq_result.get("method") == "heuristic"
    if prompt_judge_fallback:
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
    ai_leverage["method"] = "counterfactual_v1" if baseline_result.get("status") == "ok" else "research_proxy_v1"

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
