"""Run consolidated release-quality gates for evaluator logic.

Usage:
    cd backend && python -m scripts.run_release_quality_gates
    cd backend && python -m scripts.run_release_quality_gates --strict
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.evaluation.benchmarking import evaluate_reproducibility, load_benchmark_cases
from app.services.evaluation.weight_profile import validate_weight_profile_freeze
from scripts.run_challenge_publish_gate import run_gate as run_challenge_publish_gate
from scripts.run_evaluator_regression_gate import run_gate as run_evaluator_regression_gate
from scripts.run_prompt_judge_calibration_gate import run_gate as run_prompt_judge_calibration_gate
from scripts.run_prompt_judge_dataset_freshness_gate import (
    run_gate as run_prompt_judge_dataset_freshness_gate,
)


def _weight_profile_gate_result() -> dict[str, Any]:
    result = validate_weight_profile_freeze()
    # Static defaults are acceptable when no dynamic profile file exists.
    if not result.get("pass", False) and result.get("reason") == "profile_missing":
        return {
            "pass": True,
            "reason": "static_defaults",
            "method": "weight_profile_lock_v1",
        }
    result["method"] = "weight_profile_lock_v1"
    return result


def run_all_gates(
    *,
    strict: bool,
    challenges_dir: Path,
    benchmark_cases: Path,
    prompt_samples: Path,
) -> dict[str, Any]:
    benchmark_pack = load_benchmark_cases(benchmark_cases)
    reproducibility = evaluate_reproducibility(
        benchmark_pack,
        repeats=10,
        stddev_threshold=0.03,
    )
    regression = run_evaluator_regression_gate(cases_path=benchmark_cases)
    challenge_publish = run_challenge_publish_gate(
        challenges_dir=challenges_dir,
        expected_challenges=10,
        min_hidden_cases=2,
        min_input_examples=1,
    )
    dataset_freshness = run_prompt_judge_dataset_freshness_gate(
        samples_path=prompt_samples,
        min_total=24,
        min_recent=6,
        recent_days=14,
        min_unique_challenges=5,
        require_reviewed_at=strict,
    )
    prompt_judge_calibration = run_prompt_judge_calibration_gate(
        samples_path=prompt_samples,
        mode="judge" if strict else "heuristic",
        min_samples=20,
        min_pearson=0.75,
        max_mae=0.25,
        require_judge_mode=strict,
    )
    weight_profile_lock = _weight_profile_gate_result()

    gates = {
        "challenge_publish": challenge_publish,
        "reproducibility": reproducibility,
        "regression_pack": regression,
        "prompt_judge_dataset_freshness": dataset_freshness,
        "prompt_judge_calibration": prompt_judge_calibration,
        "weight_profile_lock": weight_profile_lock,
    }
    passed = all(bool((result or {}).get("pass", False)) for result in gates.values())
    return {
        "pass": passed,
        "strict": strict,
        "gates": gates,
        "summary": {
            "passed_gates": sum(1 for result in gates.values() if result.get("pass")),
            "total_gates": len(gates),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run consolidated release-quality gates")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable release-strict checks (judge-mode calibration + reviewed_at metadata required).",
    )
    parser.add_argument(
        "--challenges-dir",
        default=str(Path(__file__).resolve().parents[2] / "challenges"),
    )
    parser.add_argument(
        "--benchmark-cases",
        default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "benchmark_cases.json"),
    )
    parser.add_argument(
        "--prompt-samples",
        default=str(Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"),
    )
    args = parser.parse_args()

    result = run_all_gates(
        strict=bool(args.strict),
        challenges_dir=Path(args.challenges_dir),
        benchmark_cases=Path(args.benchmark_cases),
        prompt_samples=Path(args.prompt_samples),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
