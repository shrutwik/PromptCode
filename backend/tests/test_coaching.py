from __future__ import annotations

from types import SimpleNamespace

from app.workers.evaluate import _build_coaching


def _result(**overrides):
    base = {
        "accuracy": 0.7,
        "edge_case_handling": 0.6,
        "reliability": 0.72,
        "efficiency": 0.65,
        "orchestration": 0.8,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_coaching_first_attempt():
    coaching = _build_coaching(
        result=_result(),
        growth={"status": "first_attempt"},
        mastery_state="practicing",
        previous=None,
    )
    assert coaching["trend"] == "first_attempt"
    assert coaching["next_focus"] in {"accuracy", "robustness", "reliability", "efficiency", "orchestration"}


def test_build_coaching_regression_summary():
    coaching = _build_coaching(
        result=_result(),
        growth={
            "status": "regressed",
            "delta_overall": -0.05,
            "delta_accuracy": 0.02,
            "delta_robustness": -0.06,
            "delta_efficiency": -0.01,
        },
        mastery_state="proficient",
        previous=SimpleNamespace(id="prev"),
    )
    assert "Regression detected" in coaching["summary"]
    assert "robustness" in coaching["regressed"]
    assert coaching["previous_submission_id"] == "prev"

