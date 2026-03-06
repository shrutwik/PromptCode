"""Run deterministic evaluator regression gate over benchmark pack.

Usage:
    cd backend && python -m scripts.run_evaluator_regression_gate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.evaluation.benchmarking import compute_case_scores, load_benchmark_cases


def run_gate(*, cases_path: Path, max_violations: int = 20) -> dict[str, Any]:
    cases = load_benchmark_cases(cases_path)
    violations: list[dict[str, Any]] = []
    per_case: list[dict[str, Any]] = []

    for case in cases:
        scores = compute_case_scores(case)
        overall = float(scores.get("overall", 0.0))
        in_band = case.expected_overall_min <= overall <= case.expected_overall_max
        row = {
            "case_id": case.case_id,
            "profile": case.profile,
            "overall": round(overall, 4),
            "expected_band": [case.expected_overall_min, case.expected_overall_max],
            "in_band": in_band,
        }
        per_case.append(row)
        if not in_band:
            violations.append(row)

    return {
        "pass": len(violations) == 0,
        "case_count": len(cases),
        "violations_count": len(violations),
        "violations": violations[:max_violations],
        "summary": {
            "pass_rate": round(
                (sum(1 for row in per_case if row["in_band"]) / len(per_case)) if per_case else 0.0,
                4,
            ),
        },
        "method": "benchmark_regression_v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run evaluator regression gate")
    parser.add_argument(
        "--cases",
        default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "benchmark_cases.json"),
        help="Path to benchmark case JSON file",
    )
    parser.add_argument(
        "--max-violations",
        type=int,
        default=20,
        help="Maximum failing cases printed in report",
    )
    args = parser.parse_args()

    result = run_gate(cases_path=Path(args.cases), max_violations=args.max_violations)
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
