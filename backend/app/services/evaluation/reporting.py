"""Reporting, confidence, and manifest helpers for evaluation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.services.evaluation.constants import PERTURBATION_CONFIG_VERSION, SCORE_WEIGHTS


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
