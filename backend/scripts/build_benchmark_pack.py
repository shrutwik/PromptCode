"""Generate deterministic benchmark pack for scoring drift gates.

Usage:
    cd backend && python -m scripts.build_benchmark_pack
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.services.evaluation.benchmarking import BenchmarkCase, compute_case_scores


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _sample_case(rng: random.Random, case_id: str, profile: str) -> BenchmarkCase:
    if profile == "strong":
        accuracy = _clamp(rng.normalvariate(0.90, 0.04))
        perturbed = _clamp(rng.normalvariate(0.88, 0.06))
        adversarial = _clamp(rng.normalvariate(0.82, 0.08))
        reliability = _clamp(rng.normalvariate(0.86, 0.05))
        prompt_quality = _clamp(rng.normalvariate(0.84, 0.06))
        orchestration = _clamp(rng.normalvariate(0.82, 0.06))
        rule_adherence = _clamp(rng.normalvariate(0.88, 0.05))
        calibration = _clamp(rng.normalvariate(0.62, 0.12))
        total_tokens = int(rng.uniform(5_000, 16_000))
        total_cost = round(rng.uniform(0.04, 0.22), 6)
        total_latency = rng.uniform(14_000, 42_000)
        total_calls = int(rng.uniform(6, 26))
    elif profile == "gaming":
        accuracy = _clamp(rng.normalvariate(0.54, 0.08))
        perturbed = _clamp(rng.normalvariate(0.42, 0.10))
        adversarial = _clamp(rng.normalvariate(0.34, 0.10))
        reliability = _clamp(rng.normalvariate(0.52, 0.09))
        prompt_quality = _clamp(rng.normalvariate(0.43, 0.10))
        orchestration = _clamp(rng.normalvariate(0.46, 0.11))
        rule_adherence = _clamp(rng.normalvariate(0.48, 0.09))
        calibration = _clamp(rng.normalvariate(0.40, 0.12))
        total_tokens = int(rng.uniform(40, 600))
        total_cost = round(rng.uniform(0.0004, 0.01), 6)
        total_latency = rng.uniform(700, 4_500)
        total_calls = int(rng.uniform(0, 3))
    elif profile == "brittle":
        accuracy = _clamp(rng.normalvariate(0.78, 0.06))
        perturbed = _clamp(rng.normalvariate(0.58, 0.09))
        adversarial = _clamp(rng.normalvariate(0.40, 0.10))
        reliability = _clamp(rng.normalvariate(0.61, 0.08))
        prompt_quality = _clamp(rng.normalvariate(0.69, 0.09))
        orchestration = _clamp(rng.normalvariate(0.62, 0.08))
        rule_adherence = _clamp(rng.normalvariate(0.67, 0.08))
        calibration = _clamp(rng.normalvariate(0.55, 0.12))
        total_tokens = int(rng.uniform(7_000, 24_000))
        total_cost = round(rng.uniform(0.08, 0.32), 6)
        total_latency = rng.uniform(20_000, 58_000)
        total_calls = int(rng.uniform(8, 40))
    else:  # average
        accuracy = _clamp(rng.normalvariate(0.72, 0.09))
        perturbed = _clamp(rng.normalvariate(0.67, 0.09))
        adversarial = _clamp(rng.normalvariate(0.60, 0.10))
        reliability = _clamp(rng.normalvariate(0.69, 0.08))
        prompt_quality = _clamp(rng.normalvariate(0.71, 0.09))
        orchestration = _clamp(rng.normalvariate(0.68, 0.08))
        rule_adherence = _clamp(rng.normalvariate(0.72, 0.08))
        calibration = _clamp(rng.normalvariate(0.56, 0.12))
        total_tokens = int(rng.uniform(6_000, 20_000))
        total_cost = round(rng.uniform(0.05, 0.28), 6)
        total_latency = rng.uniform(16_000, 50_000)
        total_calls = int(rng.uniform(6, 34))

    token_budget = 12_000
    cost_budget_usd = 0.20
    latency_budget_ms = 30_000
    call_budget = 20

    # Temporary placeholder band; updated after computing score.
    case = BenchmarkCase(
        case_id=case_id,
        profile=profile,
        accuracy=round(accuracy, 4),
        perturbed_pass_rate=round(perturbed, 4),
        adversarial_pass_rate=round(adversarial, 4),
        reliability=round(reliability, 4),
        prompt_quality=round(prompt_quality, 4),
        orchestration=round(orchestration, 4),
        calibration=round(calibration, 4),
        rule_adherence=round(rule_adherence, 4),
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        total_latency_ms=round(total_latency, 2),
        total_calls=total_calls,
        token_budget=token_budget,
        cost_budget_usd=cost_budget_usd,
        latency_budget_ms=latency_budget_ms,
        call_budget=call_budget,
        expected_overall_min=0.0,
        expected_overall_max=1.0,
    )

    overall = compute_case_scores(case)["overall"]
    margin = 0.025
    return BenchmarkCase(
        **{
            **case.to_dict(),
            "expected_overall_min": round(max(0.0, overall - margin), 4),
            "expected_overall_max": round(min(1.0, overall + margin), 4),
        }
    )


def build_cases(seed: int = 20260304, total_cases: int = 100) -> list[BenchmarkCase]:
    rng = random.Random(seed)
    profiles = (
        ["strong"] * 30
        + ["average"] * 35
        + ["brittle"] * 20
        + ["gaming"] * 15
    )
    rng.shuffle(profiles)

    cases: list[BenchmarkCase] = []
    for i in range(total_cases):
        profile = profiles[i % len(profiles)]
        case_id = f"bench_{i+1:03d}_{profile}"
        cases.append(_sample_case(rng, case_id, profile))
    return cases


def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    out_dir = backend_root / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = build_cases()
    out_file = out_dir / "benchmark_cases.json"
    out_file.write_text(json.dumps([c.to_dict() for c in cases], indent=2) + "\n")

    print(
        json.dumps(
            {
                "output": str(out_file),
                "case_count": len(cases),
                "profiles": {
                    "strong": sum(1 for c in cases if c.profile == "strong"),
                    "average": sum(1 for c in cases if c.profile == "average"),
                    "brittle": sum(1 for c in cases if c.profile == "brittle"),
                    "gaming": sum(1 for c in cases if c.profile == "gaming"),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

