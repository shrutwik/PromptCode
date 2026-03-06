from __future__ import annotations

from pathlib import Path


def test_all_challenges_have_sample_solutions():
    repo_root = Path(__file__).resolve().parents[2]
    challenge_dirs = sorted((repo_root / "challenges").glob("*/challenge.json"))
    assert len(challenge_dirs) == 10

    missing = [
        str(path.parent.name)
        for path in challenge_dirs
        if not (path.parent / "sample_solution.py").exists()
    ]
    assert missing == []


def test_sdk_guide_mentions_every_sample_solution():
    repo_root = Path(__file__).resolve().parents[2]
    guide = (repo_root / "docs" / "SDK_GUIDE.md").read_text(encoding="utf-8")

    for challenge_dir in sorted((repo_root / "challenges").glob("*")):
        if not challenge_dir.is_dir():
            continue
        sample_path = f"challenges/{challenge_dir.name}/sample_solution.py"
        assert sample_path in guide
