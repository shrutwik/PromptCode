"""Benchmark pack and reproducibility gate helpers.

This module gives us a deterministic, CI-friendly evaluation benchmark that
tracks scoring drift without requiring sandbox execution or external API calls.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from app.services.evaluation.engine import SCORE_WEIGHTS, _apply_overall_caps
from app.services.evaluation.scorer import score_efficiency_tradeoff


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    profile: str
    accuracy: float
    perturbed_pass_rate: float
    adversarial_pass_rate: float
    reliability: float
    prompt_quality: float
    orchestration: float
    calibration: float
    rule_adherence: float
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: float
    total_calls: int
    token_budget: int
    cost_budget_usd: float
    latency_budget_ms: float
    call_budget: int
    expected_overall_min: float
    expected_overall_max: float

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "BenchmarkCase":
        return cls(
            case_id=str(row["case_id"]),
            profile=str(row["profile"]),
            accuracy=float(row["accuracy"]),
            perturbed_pass_rate=float(row["perturbed_pass_rate"]),
            adversarial_pass_rate=float(row["adversarial_pass_rate"]),
            reliability=float(row["reliability"]),
            prompt_quality=float(row["prompt_quality"]),
            orchestration=float(row["orchestration"]),
            calibration=float(row["calibration"]),
            rule_adherence=float(row["rule_adherence"]),
            total_tokens=int(row["total_tokens"]),
            total_cost_usd=float(row["total_cost_usd"]),
            total_latency_ms=float(row["total_latency_ms"]),
            total_calls=int(row["total_calls"]),
            token_budget=int(row["token_budget"]),
            cost_budget_usd=float(row["cost_budget_usd"]),
            latency_budget_ms=float(row["latency_budget_ms"]),
            call_budget=int(row["call_budget"]),
            expected_overall_min=float(row["expected_overall_min"]),
            expected_overall_max=float(row["expected_overall_max"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "profile": self.profile,
            "accuracy": self.accuracy,
            "perturbed_pass_rate": self.perturbed_pass_rate,
            "adversarial_pass_rate": self.adversarial_pass_rate,
            "reliability": self.reliability,
            "prompt_quality": self.prompt_quality,
            "orchestration": self.orchestration,
            "calibration": self.calibration,
            "rule_adherence": self.rule_adherence,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_latency_ms": self.total_latency_ms,
            "total_calls": self.total_calls,
            "token_budget": self.token_budget,
            "cost_budget_usd": self.cost_budget_usd,
            "latency_budget_ms": self.latency_budget_ms,
            "call_budget": self.call_budget,
            "expected_overall_min": self.expected_overall_min,
            "expected_overall_max": self.expected_overall_max,
        }


def load_benchmark_cases(path: Path) -> list[BenchmarkCase]:
    rows = json.loads(path.read_text())
    return [BenchmarkCase.from_dict(row) for row in rows]


def compute_case_scores(case: BenchmarkCase) -> dict[str, float]:
    robustness = round(
        (case.perturbed_pass_rate * 0.5) + (case.adversarial_pass_rate * 0.5),
        4,
    )
    quality_anchor = (case.accuracy * 0.5) + (robustness * 0.3) + (case.reliability * 0.2)
    efficiency = score_efficiency_tradeoff(
        total_tokens=case.total_tokens,
        total_cost_usd=case.total_cost_usd,
        total_latency_ms=case.total_latency_ms,
        total_calls=case.total_calls,
        quality_anchor=quality_anchor,
        budgets={
            "token_budget": case.token_budget,
            "cost_budget_usd": case.cost_budget_usd,
            "latency_budget_ms": case.latency_budget_ms,
            "call_budget": case.call_budget,
        },
    )

    raw_overall = round(
        case.accuracy * SCORE_WEIGHTS["accuracy"]
        + robustness * SCORE_WEIGHTS["robustness"]
        + case.reliability * SCORE_WEIGHTS["reliability"]
        + efficiency * SCORE_WEIGHTS["efficiency"]
        + case.prompt_quality * SCORE_WEIGHTS["prompt_quality"]
        + case.orchestration * SCORE_WEIGHTS["orchestration"]
        + case.calibration * SCORE_WEIGHTS["calibration"],
        4,
    )
    overall, _events = _apply_overall_caps(
        raw_overall=raw_overall,
        accuracy=case.accuracy,
        rule_adherence=case.rule_adherence,
        anti_gaming_triggered=False,
    )
    return {
        "accuracy": case.accuracy,
        "robustness": robustness,
        "reliability": case.reliability,
        "efficiency": efficiency,
        "prompt_quality": case.prompt_quality,
        "orchestration": case.orchestration,
        "calibration": case.calibration,
        "rule_adherence": case.rule_adherence,
        "overall": overall,
    }


def simulate_repeated_overall(case: BenchmarkCase, repeats: int) -> list[float]:
    """Simulate repeated evaluation outputs with tiny deterministic jitter.

    This approximates run-to-run noise while keeping CI deterministic.
    """
    base = compute_case_scores(case)["overall"]
    values: list[float] = []
    for i in range(repeats):
        seed = _seed_from_case(case.case_id, i)
        rng = random.Random(seed)
        # Stable, tiny jitter envelope to emulate stochastic model variance.
        jitter = rng.uniform(-0.01, 0.01)
        values.append(round(max(0.0, min(1.0, base + jitter)), 4))
    return values


def evaluate_reproducibility(
    cases: list[BenchmarkCase],
    *,
    repeats: int = 10,
    stddev_threshold: float = 0.03,
) -> dict[str, Any]:
    per_case: list[dict[str, Any]] = []
    stddev_violations: list[dict[str, Any]] = []
    band_violations: list[dict[str, Any]] = []

    for case in cases:
        seq = simulate_repeated_overall(case, repeats)
        avg = mean(seq)
        var = sum((x - avg) ** 2 for x in seq) / max(1, len(seq))
        stddev = var ** 0.5
        expected_ok = case.expected_overall_min <= avg <= case.expected_overall_max

        row = {
            "case_id": case.case_id,
            "profile": case.profile,
            "mean_overall": round(avg, 4),
            "stddev": round(stddev, 4),
            "expected_band": [case.expected_overall_min, case.expected_overall_max],
            "in_band": expected_ok,
        }
        per_case.append(row)

        if stddev > stddev_threshold:
            stddev_violations.append(row)
        if not expected_ok:
            band_violations.append(row)

    return {
        "case_count": len(cases),
        "repeats": repeats,
        "stddev_threshold": stddev_threshold,
        "stddev_violations": stddev_violations,
        "band_violations": band_violations,
        "pass": not stddev_violations and not band_violations,
        "summary": {
            "mean_stddev": round(mean([r["stddev"] for r in per_case]) if per_case else 0.0, 4),
            "max_stddev": round(max([r["stddev"] for r in per_case]) if per_case else 0.0, 4),
            "band_pass_rate": round(
                (sum(1 for r in per_case if r["in_band"]) / len(per_case)) if per_case else 0.0,
                4,
            ),
        },
    }


def _seed_from_case(case_id: str, i: int) -> int:
    h = hashlib.sha256(f"{case_id}:{i}".encode("utf-8")).hexdigest()
    return int(h[:16], 16)

