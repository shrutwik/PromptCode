from __future__ import annotations

from types import SimpleNamespace

from app.workers.evaluate import _eligible_for_leaderboard


def _submission(report: dict, **overrides):
    base = {
        "status": "completed",
        "score_overall": 0.81,
        "score_reliability": 0.72,
        "report": report,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_leaderboard_requires_llm_judge_counterfactual_and_credibility():
    sub = _submission(
        {
            "tests_total": 8,
            "disqualified": False,
            "credibility": {"score": 0.77},
            "prompt_quality_details": {"method": "llm_judge"},
            "ai_leverage": {
                "leverage_gain": 0.04,
                "signals": {"counterfactual": {"status": "ok"}},
            },
        }
    )
    assert _eligible_for_leaderboard(sub) is True


def test_leaderboard_rejects_heuristic_prompt_judge():
    sub = _submission(
        {
            "tests_total": 8,
            "disqualified": False,
            "credibility": {"score": 0.77},
            "prompt_quality_details": {"method": "heuristic"},
            "ai_leverage": {
                "leverage_gain": 0.04,
                "signals": {"counterfactual": {"status": "ok"}},
            },
        }
    )
    assert _eligible_for_leaderboard(sub) is False


def test_leaderboard_rejects_nonpositive_leverage_gain():
    sub = _submission(
        {
            "tests_total": 8,
            "disqualified": False,
            "credibility": {"score": 0.77},
            "prompt_quality_details": {"method": "llm_judge"},
            "ai_leverage": {
                "leverage_gain": -0.01,
                "signals": {"counterfactual": {"status": "ok"}},
            },
        }
    )
    assert _eligible_for_leaderboard(sub) is False
