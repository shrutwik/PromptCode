from __future__ import annotations

from app.services.evaluation.scorer import (
    score_ai_mastery,
    score_frontier_navigation,
    score_reliance_calibration,
)


def test_frontier_navigation_rewards_quality_for_similar_usage():
    budgets = {
        "token_budget": 10_000,
        "cost_budget_usd": 0.2,
        "latency_budget_ms": 20_000,
        "call_budget": 12,
    }
    low_quality = score_frontier_navigation(
        total_tokens=2500,
        total_cost_usd=0.05,
        total_latency_ms=5000,
        total_calls=5,
        quality_anchor=0.35,
        budgets=budgets,
    )
    high_quality = score_frontier_navigation(
        total_tokens=2500,
        total_cost_usd=0.05,
        total_latency_ms=5000,
        total_calls=5,
        quality_anchor=0.82,
        budgets=budgets,
    )
    assert high_quality["score"] > low_quality["score"]


def test_reliance_calibration_penalizes_overreliance_without_validation():
    weak = score_reliance_calibration(
        calibration_score=0.4,
        runs=[
            {"schema_valid": False, "status": "fail", "llm_calls": 6},
            {"schema_valid": False, "status": "fail", "llm_calls": 5},
            {"schema_valid": True, "status": "fail", "llm_calls": 7},
        ],
        expected_calls=2,
        code_analysis={"analysis": {"has_json_validation": False, "has_try_except": False, "has_llm_error_handling": False}},
        anti_gaming_triggered=True,
    )
    strong = score_reliance_calibration(
        calibration_score=0.8,
        runs=[
            {"schema_valid": True, "status": "pass", "llm_calls": 2},
            {"schema_valid": True, "status": "pass", "llm_calls": 2},
            {"schema_valid": True, "status": "pass", "llm_calls": 1},
        ],
        expected_calls=2,
        code_analysis={"analysis": {"has_json_validation": True, "has_try_except": True, "has_llm_error_handling": True}},
        anti_gaming_triggered=False,
    )
    assert strong["score"] > weak["score"]
    assert weak["over_reliance_penalty"] > 0


def test_ai_mastery_uses_all_components():
    result = score_ai_mastery(
        frontier_navigation_score=0.7,
        reliance_calibration_score=0.8,
        prompt_quality_score=0.75,
        learning_velocity_score=0.9,
    )
    assert 0.0 <= result["score"] <= 1.0
    assert result["components"]["learning_velocity"] == 0.9
