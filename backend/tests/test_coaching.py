from __future__ import annotations

from types import SimpleNamespace

from app.workers.evaluate import (
    _build_coaching,
    _build_coaching_actions,
    _compute_learning_velocity_score,
    _enrich_ai_leverage,
    _build_iteration_diff,
)


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


def test_iteration_diff_includes_code_and_prompt_changes():
    previous = SimpleNamespace(
        id="prev-id",
        code='prompt = "Extract fields and return json"\nprint(prompt)\n',
    )
    current = SimpleNamespace(
        id="cur-id",
        code='prompt = "Extract fields strictly and return valid JSON only"\nprint(prompt)\nprint("done")\n',
    )
    growth = {
        "status": "improved",
        "delta_overall": 0.04,
        "delta_accuracy": 0.03,
        "delta_robustness": 0.02,
        "delta_efficiency": -0.01,
    }
    diff = _build_iteration_diff(previous=previous, current=current, growth=growth)
    assert diff["status"] == "improved"
    assert diff["code_changes"]["added_lines"] >= 1
    assert diff["prompt_changes"]["added_count"] >= 0
    assert diff["score_deltas"]["overall"] == 0.04


def test_coaching_actions_link_failed_runs():
    actions = _build_coaching_actions(
        result=SimpleNamespace(efficiency=0.6),
        growth={"delta_overall": -0.03, "previous_submission_id": "prev"},
        runs=[
            {"run_type": "adversarial", "run_index": 1, "status": "fail", "accuracy": 0.42},
            {"run_type": "clean", "run_index": 0, "status": "pass", "accuracy": 0.9},
        ],
        diagnostics=[
            {"metric": "efficiency", "severity": "medium", "message": "Too many tokens used."}
        ],
        iteration_diff={"prompt_changes": {"added_count": 3}},
    )
    assert actions
    assert actions[0]["title"].lower().startswith("fix adversarial")


def test_learning_velocity_defaults_to_neutral_without_previous():
    score = _compute_learning_velocity_score(
        delta_overall=None,
        delta_accuracy=None,
        delta_robustness=None,
        delta_efficiency=None,
        changed_ratio=None,
    )
    assert score["score"] == 0.5


def test_enrich_ai_leverage_updates_mastery_with_learning_velocity():
    ai = _enrich_ai_leverage(
        ai_leverage={
            "frontier_navigation_score": 0.7,
            "reliance_calibration_score": 0.8,
            "ai_mastery_score": 0.0,
            "signals": {},
        },
        growth={
            "delta_overall": 0.04,
            "delta_accuracy": 0.02,
            "delta_robustness": 0.03,
            "delta_efficiency": 0.01,
        },
        iteration_diff={"code_changes": {"changed_ratio": 0.25}},
        prompt_quality=0.75,
    )
    assert ai["learning_velocity_score"] > 0.5
    assert ai["ai_mastery_score"] > 0.6
    assert ai["signals"]["learning_velocity"]["method"] == "learning_velocity_v1"
