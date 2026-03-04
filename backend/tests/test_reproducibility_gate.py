from __future__ import annotations

from pathlib import Path

from app.services.evaluation.benchmarking import (
    evaluate_reproducibility,
    load_benchmark_cases,
)


def _cases_path() -> Path:
    return Path(__file__).resolve().parents[1] / "benchmarks" / "benchmark_cases.json"


def test_benchmark_pack_has_expected_size() -> None:
    cases = load_benchmark_cases(_cases_path())
    assert len(cases) == 100


def test_reproducibility_gate_passes_default_threshold() -> None:
    cases = load_benchmark_cases(_cases_path())
    result = evaluate_reproducibility(cases, repeats=10, stddev_threshold=0.03)
    assert result["pass"] is True
    assert not result["stddev_violations"]
    assert not result["band_violations"]
    assert result["summary"]["max_stddev"] <= 0.03

