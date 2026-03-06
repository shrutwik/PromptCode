"""Evaluation engine: multi-run sandbox scoring with quality, robustness, and efficiency tradeoffs."""

from __future__ import annotations

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


def evaluate_submission(
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

    for spec in run_plan:
        result = run_in_sandbox(code, entrypoint, challenge_config, input_overrides=spec["inputs"])
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
    pq_result = score_prompt_quality(all_telemetry, challenge_description)

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
    ai_mastery_result = score_ai_mastery(
        frontier_navigation_score=float(frontier_result.get("score", 0.0)),
        reliance_calibration_score=float(reliance_result.get("score", 0.0)),
        prompt_quality_score=pq,
    )
    if hardcoded:
        frontier_result["score"] = 0.0
        reliance_result["score"] = 0.0
        ai_mastery_result["score"] = 0.0
    ai_leverage = {
        "frontier_navigation_score": round(float(frontier_result.get("score", 0.0)), 4),
        "reliance_calibration_score": round(float(reliance_result.get("score", 0.0)), 4),
        "learning_velocity_score": None,
        "ai_mastery_score": round(float(ai_mastery_result.get("score", 0.0)), 4),
        "signals": {
            "frontier": frontier_result,
            "reliance": reliance_result,
            "composite": ai_mastery_result,
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
    for event in cap_events:
        audit_trail.append(
            {
                "event": "score_cap_applied",
                "at": _now_iso(),
                "details": event,
            }
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
        "accuracy": _mean_confidence_interval(clean_accuracies),
        "robustness_proxy": _mean_confidence_interval(
            perturbed_accuracies + adversarial_accuracies
        ),
        "run_accuracy": _mean_confidence_interval(all_accuracies),
        "pass_rate": _proportion_confidence_interval(
            sum(1 for r in run_records if r.get("status") == "pass"),
            len(run_records),
        ),
    }
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
