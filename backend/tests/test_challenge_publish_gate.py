from __future__ import annotations

from pathlib import Path

from scripts.run_challenge_publish_gate import run_gate


def test_challenge_publish_gate_passes_repository_challenges() -> None:
    challenges_dir = Path(__file__).resolve().parents[2] / "challenges"
    result = run_gate(
        challenges_dir=challenges_dir,
        expected_challenges=10,
        min_hidden_cases=2,
        min_input_examples=1,
    )
    assert result["pass"] is True
