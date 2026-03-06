from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.evaluation.scorer import score_ai_mastery
from app.services.evaluation.weight_profile import get_weight_profile


def test_ai_mastery_respects_custom_weights_with_baseline():
    result = score_ai_mastery(
        frontier_navigation_score=0.8,
        reliance_calibration_score=0.2,
        prompt_quality_score=0.2,
        learning_velocity_score=0.2,
        leverage_gain_score=0.2,
        weights_with_baseline={
            "frontier_navigation": 1.0,
            "reliance_calibration": 0.0,
            "prompt_quality": 0.0,
            "learning_velocity": 0.0,
            "leverage_gain": 0.0,
        },
    )
    assert abs(result["score"] - 0.8) < 1e-6
    assert result["weights"]["with_baseline"]["frontier_navigation"] == 1.0


def test_ai_mastery_respects_custom_weights_without_baseline():
    result = score_ai_mastery(
        frontier_navigation_score=0.1,
        reliance_calibration_score=0.9,
        prompt_quality_score=0.1,
        learning_velocity_score=0.1,
        weights_without_baseline={
            "frontier_navigation": 0.0,
            "reliance_calibration": 1.0,
            "prompt_quality": 0.0,
            "learning_velocity": 0.0,
        },
    )
    assert abs(result["score"] - 0.9) < 1e-6
    assert result["weights"]["without_baseline"]["reliance_calibration"] == 1.0


def test_weight_profile_defaults_when_file_missing(monkeypatch):
    get_settings.cache_clear()
    get_weight_profile.cache_clear()
    missing_path = str(Path(__file__).resolve().parent / "does_not_exist_profile.json")
    monkeypatch.setenv("PROMPTCODE_EVALUATION_WEIGHT_PROFILE_PATH", missing_path)

    profile = get_weight_profile()
    assert profile["version"] == "static_v1"
    assert "ai_mastery_with_baseline" in profile
    assert "future_readiness" in profile

    get_settings.cache_clear()
    get_weight_profile.cache_clear()
