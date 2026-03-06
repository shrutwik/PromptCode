from __future__ import annotations

from pathlib import Path

from scripts.run_prompt_judge_dataset_freshness_gate import run_gate


def test_prompt_judge_dataset_freshness_gate_passes_with_reviewed_metadata(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    samples.write_text(
        "\n".join(
            [
                '{"challenge_description":"A","human_overall":0.9,"reviewed_at":"2026-03-05T12:00:00+00:00"}',
                '{"challenge_description":"B","human_overall":0.8,"reviewed_at":"2026-03-04T12:00:00+00:00"}',
                '{"challenge_description":"C","human_overall":0.7,"reviewed_at":"2026-03-03T12:00:00+00:00"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_gate(
        samples_path=samples,
        min_total=3,
        min_recent=2,
        recent_days=14,
        min_unique_challenges=3,
        require_reviewed_at=True,
    )
    assert result["pass"] is True
    assert result["reviewed_at_missing"] == 0
    assert result["reviewed_at_parse_failures"] == 0


def test_prompt_judge_dataset_freshness_gate_fails_when_metadata_required(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    samples.write_text(
        "\n".join(
            [
                '{"challenge_description":"A","human_overall":0.9}',
                '{"challenge_description":"B","human_overall":0.8}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_gate(
        samples_path=samples,
        min_total=2,
        min_recent=1,
        recent_days=14,
        min_unique_challenges=2,
        require_reviewed_at=True,
    )
    assert result["pass"] is False
    assert result["checks"]["reviewed_at_present"] is False
