from __future__ import annotations

from pathlib import Path

from scripts.run_evaluator_regression_gate import run_gate


def test_evaluator_regression_gate_passes_benchmark_pack() -> None:
    cases = Path(__file__).resolve().parents[1] / "benchmarks" / "benchmark_cases.json"
    result = run_gate(cases_path=cases)
    assert result["pass"] is True
    assert result["case_count"] == 100
    assert result["violations_count"] == 0
