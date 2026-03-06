from __future__ import annotations

from pathlib import Path

from scripts.run_release_quality_gates import run_all_gates


def test_release_quality_gates_pass_in_non_strict_mode() -> None:
    root = Path(__file__).resolve().parents[2]
    result = run_all_gates(
        strict=False,
        challenges_dir=root / "challenges",
        benchmark_cases=root / "backend" / "benchmarks" / "benchmark_cases.json",
        prompt_samples=root / "docs" / "prompt_judge_samples.jsonl",
    )
    assert result["pass"] is True
    assert result["summary"]["total_gates"] == 6
