from __future__ import annotations

from pathlib import Path

from scripts.run_prompt_judge_calibration_gate import run_gate


def test_prompt_judge_calibration_gate_passes_heuristic_baseline() -> None:
    samples = Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"
    result = run_gate(
        samples_path=samples,
        mode="heuristic",
        min_samples=20,
        min_pearson=0.75,
        max_mae=0.25,
        require_judge_mode=False,
    )
    assert result["pass"] is True
    assert result["sample_count"] >= 20
    assert result["pearson_r"] >= 0.75
