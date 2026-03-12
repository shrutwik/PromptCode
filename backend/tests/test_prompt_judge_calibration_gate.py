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


def test_prompt_judge_calibration_gate_passes_locked_baseline() -> None:
    samples = Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"
    lock = Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_calibration.lock.json"
    result = run_gate(
        samples_path=samples,
        mode="locked",
        min_samples=20,
        min_pearson=0.75,
        max_mae=0.25,
        require_judge_mode=True,
        lock_path=lock,
    )
    assert result["pass"] is True
    assert result["mode"] == "locked"
    assert result["method"] == "prompt_judge_lock_v1"


def test_prompt_judge_calibration_gate_enforces_strict_mode_requirement() -> None:
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
    assert result["reason"] == "strict_mode_required"


def test_prompt_judge_calibration_gate_fails_when_lock_is_missing(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    samples.write_text(
        "\n".join(
            [
                '{"challenge_description":"A","prompts":[{"user":"x"}],"human_overall":0.9}',
            ]
            * 20
        ),
        encoding="utf-8",
    )

    result = run_gate(
        samples_path=samples,
        mode="locked",
        min_samples=20,
        min_pearson=0.75,
        max_mae=0.25,
        require_judge_mode=False,
        lock_path=tmp_path / "missing.lock.json",
    )
    assert result["pass"] is False
    assert result["reason"] == "lock_missing"


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
