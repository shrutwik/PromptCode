"""Evaluation engine: multi-run sandbox scoring with quality, robustness, and efficiency tradeoffs."""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from app.core.config import get_settings
from app.services.evaluation.code_analysis import analyze_code, score_code_quality
from app.services.evaluation.perturbation import perturb_adversarial, perturb_normal
from app.services.evaluation.prompt_quality import score_prompt_quality
from app.services.evaluation.scorer import (
    score_accuracy,
    score_calibration,
    score_efficiency_tradeoff,
    score_orchestration,
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
            "scorecard": {
                "accuracy": self.accuracy,
                "robustness": self.edge_case_handling,
                "reliability": self.reliability,
                "efficiency": self.efficiency,
                "prompt_design": self.prompt_quality,
                "orchestration": self.orchestration,
                "calibration": self.calibration,
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

    clean_runs = int(challenge_config.get("clean_runs", 1))

    for i in range(clean_runs):
        result = run_in_sandbox(code, entrypoint, challenge_config, input_overrides=base_inputs)
        record = _process_run(result, ground_truth, accuracy_mode, "clean", i)
        run_records.append(record)
        clean_accuracies.append(record["accuracy"])
        all_telemetry.extend(result.telemetry)
        total_prompt_tokens += record["tokens_prompt"]
        total_completion_tokens += record["tokens_completion"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

    for i in range(settings.evaluation_normal_runs):
        seed = random.randint(0, 2**31)
        perturbed = perturb_normal(base_inputs, seed)
        result = run_in_sandbox(code, entrypoint, challenge_config, input_overrides=perturbed)
        record = _process_run(result, ground_truth, accuracy_mode, "perturbed", i)
        run_records.append(record)
        perturbed_accuracies.append(record["accuracy"])
        all_telemetry.extend(result.telemetry)
        total_prompt_tokens += record["tokens_prompt"]
        total_completion_tokens += record["tokens_completion"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

    for i in range(settings.evaluation_adversarial_runs):
        seed = random.randint(0, 2**31)
        perturbed = perturb_adversarial(base_inputs, seed)
        result = run_in_sandbox(code, entrypoint, challenge_config, input_overrides=perturbed)
        record = _process_run(result, ground_truth, accuracy_mode, "adversarial", i)
        run_records.append(record)
        adversarial_accuracies.append(record["accuracy"])
        all_telemetry.extend(result.telemetry)
        total_prompt_tokens += record["tokens_prompt"]
        total_completion_tokens += record["tokens_completion"]
        total_cost += record["cost_usd"]
        total_latency += record["latency_ms"]
        total_calls += record["llm_calls"]
        total_retries += record["retries"]

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
    eff = score_efficiency_tradeoff(
        total_tokens=total_prompt_tokens + total_completion_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=total_latency,
        total_calls=total_calls,
        quality_anchor=quality_anchor,
        budgets={
            "token_budget": challenge_config.get("token_budget", 12_000),
            "cost_budget_usd": challenge_config.get("cost_budget_usd", 0.20),
            "latency_budget_ms": challenge_config.get("latency_budget_ms", 30_000),
            "call_budget": challenge_config.get("call_budget", challenge_config.get("expected_calls", 3) * run_count),
        },
    )

    calibration_points = _extract_confidence_points(run_records)
    calibration_result = score_calibration(calibration_points)
    calibration = float(calibration_result.get("score", 0.5))

    if hardcoded:
        logger.warning("Hardcoded answer detected - zeroing all quality scores")
        acc = pq = rule_adherence = eff = rel = orch = cq = robustness = calibration = 0.0

    overall = round(
        acc * SCORE_WEIGHTS["accuracy"]
        + robustness * SCORE_WEIGHTS["robustness"]
        + rel * SCORE_WEIGHTS["reliability"]
        + eff * SCORE_WEIGHTS["efficiency"]
        + pq * SCORE_WEIGHTS["prompt_quality"]
        + orch * SCORE_WEIGHTS["orchestration"]
        + calibration * SCORE_WEIGHTS["calibration"],
        4,
    )

    if acc < 0.40:
        overall = min(overall, 0.55)
    if rule_adherence < 0.50:
        overall = min(overall, 0.50)

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
    if not tips:
        tips.append({
            "metric": "summary",
            "severity": "low",
            "message": "Balanced submission: no critical weaknesses detected in this run set.",
        })

    return tips


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
    if result.success:
        raw = result.output.strip()
        acc = score_accuracy(raw, ground_truth, mode=accuracy_mode)
        schema_valid = _is_schema_valid(raw, accuracy_mode)
        confidence = _extract_confidence_value(raw)

    status = "pass" if (result.success and acc >= 0.8 and schema_valid) else "fail"

    return {
        "run_type": run_type,
        "run_index": run_index,
        "success": result.success,
        "status": status,
        "accuracy": round(acc, 4),
        "schema_valid": schema_valid,
        "confidence": confidence,
        "tokens_prompt": prompt_tokens,
        "tokens_completion": completion_tokens,
        "tokens_total": tokens,
        "cost_usd": round(cost, 6),
        "latency_ms": round(latency, 2),
        "llm_calls": calls,
        "retries": retries,
        "error": result.error,
    }


def _is_schema_valid(output: str, accuracy_mode: str) -> bool:
    if accuracy_mode != "json":
        return bool(output.strip())
    try:
        json.loads(output)
        return True
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
