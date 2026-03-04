"""Run benchmark reproducibility gate.

Usage:
    cd backend && python -m scripts.run_reproducibility_gate
    cd backend && python -m scripts.run_reproducibility_gate --repeats 12 --stddev-threshold 0.03
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.evaluation.benchmarking import (
    evaluate_reproducibility,
    load_benchmark_cases,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "benchmark_cases.json"),
        help="Path to benchmark case JSON file",
    )
    parser.add_argument("--repeats", type=int, default=10)
    parser.add_argument("--stddev-threshold", type=float, default=0.03)
    parser.add_argument(
        "--max-violations",
        type=int,
        default=10,
        help="Max violations to print for each category",
    )
    args = parser.parse_args()

    cases = load_benchmark_cases(Path(args.cases))
    result = evaluate_reproducibility(
        cases,
        repeats=args.repeats,
        stddev_threshold=args.stddev_threshold,
    )

    trimmed = {
        **result,
        "stddev_violations": result["stddev_violations"][: args.max_violations],
        "band_violations": result["band_violations"][: args.max_violations],
    }
    print(json.dumps(trimmed, indent=2))

    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

