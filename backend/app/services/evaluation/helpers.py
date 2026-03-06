"""Pure helper functions used by the evaluation engine."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.evaluation.scorer import score_accuracy
from app.services.sandbox.runner import SandboxResult


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
    except (json.JSONDecodeError, TypeError, ValueError):
        return False


def _extract_confidence_value(output: str) -> float | None:
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError, ValueError):
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
