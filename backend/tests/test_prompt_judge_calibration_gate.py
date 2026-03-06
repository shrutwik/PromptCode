from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_prompt_judge_calibration_gate as gate_module
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


def test_prompt_judge_calibration_gate_enforces_judge_mode_requirement() -> None:
    samples = Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"
    result = run_gate(
        samples_path=samples,
        mode="heuristic",
        min_samples=20,
        min_pearson=0.75,
        max_mae=0.25,
        require_judge_mode=True,
    )
    assert result["pass"] is False
    assert result["reason"] == "judge_mode_required"


def test_prompt_judge_calibration_gate_returns_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    samples = Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"

    def _boom(*args, **kwargs):
        raise RuntimeError("judge unavailable")

    monkeypatch.setattr(gate_module, "evaluate_sample", _boom)
    result = run_gate(
        samples_path=samples,
        mode="judge",
        min_samples=20,
        min_pearson=0.75,
        max_mae=0.25,
        require_judge_mode=False,
    )
    assert result["pass"] is False
    assert result["reason"] == "evaluation_error"
