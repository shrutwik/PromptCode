from __future__ import annotations

from types import SimpleNamespace

from app.workers.evaluate import _eligible_for_leaderboard


def _submission(**overrides):
    base = {
        "status": "completed",
        "score_overall": 0.8,
        "score_reliability": 0.7,
        "report": {"tests_total": 8, "disqualified": False},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_eligible_for_leaderboard_happy_path():
    assert _eligible_for_leaderboard(_submission()) is True


def test_eligible_for_leaderboard_rejects_low_reliability():
    assert _eligible_for_leaderboard(_submission(score_reliability=0.4)) is False


def test_eligible_for_leaderboard_rejects_low_test_count():
    assert _eligible_for_leaderboard(_submission(report={"tests_total": 3})) is False


def test_eligible_for_leaderboard_rejects_disqualified():
    assert _eligible_for_leaderboard(
        _submission(report={"tests_total": 8, "disqualified": True})
    ) is False

