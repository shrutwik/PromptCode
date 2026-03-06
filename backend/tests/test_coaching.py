from __future__ import annotations

from types import SimpleNamespace

from app.workers.evaluate import (
    _build_coaching,
    _build_coaching_actions,
    _build_future_feedback,
    _compute_learning_effectiveness,
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


def test_coaching_actions_include_leverage_gain_when_not_beating_baseline():
    actions = _build_coaching_actions(
        result=SimpleNamespace(efficiency=0.8),
        growth={"status": "flat"},
        runs=[],
        diagnostics=[],
        iteration_diff={"prompt_changes": {"added_count": 0}},
        ai_leverage={"leverage_gain": -0.04, "counterfactual_baseline_overall": 0.62},
    )
    assert any("baseline" in a["title"].lower() for a in actions)


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


def test_compute_learning_effectiveness_uses_previous_actions():
    previous = SimpleNamespace(
        report={
            "coaching_actions": [
                {"title": "Improve accuracy", "expected_impact": ["accuracy", "reliability"]},
                {"title": "Improve leverage", "expected_impact": ["leverage_gain", "ai_mastery"]},
            ],
            "ai_leverage": {
                "ai_mastery_score": 0.5,
                "frontier_navigation_score": 0.55,
                "reliance_calibration_score": 0.52,
                "leverage_gain": -0.02,
            },
        },
        score_overall=0.58,
        score_accuracy=0.50,
        score_edge_cases=0.46,
        score_efficiency=0.55,
        score_reliability=0.48,
        score_orchestration=0.60,
        score_rule_adherence=0.61,
    )
    current = SimpleNamespace(
        overall=0.66,
        accuracy=0.61,
        edge_case_handling=0.52,
        efficiency=0.58,
        reliability=0.56,
        orchestration=0.63,
        rule_adherence=0.66,
    )
    current_ai = {
        "ai_mastery_score": 0.62,
        "frontier_navigation_score": 0.64,
        "reliance_calibration_score": 0.60,
        "leverage_gain": 0.06,
    }
    result = _compute_learning_effectiveness(
        previous=previous,
        current=current,
        current_ai_leverage=current_ai,
    )
    assert result["status"] == "ok"
    assert result["assessed_actions"] >= 1
    assert result["coach_hit_rate"] is not None


def test_build_future_feedback_flags_low_readiness_and_prioritizes_verification():
    result = _build_future_feedback(
        result=SimpleNamespace(
            runs=[
                {"run_type": "clean"},
                {"run_type": "perturbed"},
            ],
            llm_calls=8,
            reliability=0.42,
            rule_adherence=0.48,
        ),
        ai_leverage={
            "frontier_navigation_score": 0.45,
            "reliance_calibration_score": 0.40,
            "learning_velocity_score": 0.35,
            "leverage_gain": -0.06,
        },
        credibility={"score": 0.44},
        learning_effectiveness={"coach_hit_rate": 0.2},
        growth={"status": "regressed"},
    )
    assert result["readiness_band"] == "low"
    assert result["delegation_mode"] == "over_delegating"
    assert result["next_7_days"]
    assert any("verification" in str(item.get("goal", "")).lower() for item in result["next_7_days"])
    assert "recover baseline" in " ".join(result["next_eval_protocol"]).lower()


def test_build_future_feedback_reports_high_readiness_for_strong_signals():
    result = _build_future_feedback(
        result=SimpleNamespace(
            runs=[
                {"run_type": "clean"},
                {"run_type": "perturbed"},
                {"run_type": "adversarial"},
                {"run_type": "hidden_clean"},
            ],
            llm_calls=5,
            reliability=0.84,
            rule_adherence=0.86,
        ),
        ai_leverage={
            "frontier_navigation_score": 0.82,
            "reliance_calibration_score": 0.80,
            "learning_velocity_score": 0.74,
            "leverage_gain": 0.12,
        },
        credibility={"score": 0.86},
        learning_effectiveness={"coach_hit_rate": 0.7},
        growth={"status": "improved"},
    )
    assert result["readiness_band"] == "high"
    assert result["behavior_scores"]["evaluation_rigor"] >= 0.85
    assert result["signals"]["run_type_coverage"] == 1.0
