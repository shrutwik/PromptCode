from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.services.evaluation.scorer import score_ai_mastery
from app.services.evaluation.weight_profile import (
    get_weight_profile,
    validate_weight_profile_freeze,
)


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


def test_validate_weight_profile_freeze_passes_when_lock_matches(tmp_path: Path):
    profile = tmp_path / "profile.json"
    lock = tmp_path / "profile.lock.json"
    profile.write_text(
        """
{
  "version": "2026-03-06",
  "ai_mastery_without_baseline": {"frontier_navigation": 0.35, "reliance_calibration": 0.30, "prompt_quality": 0.20, "learning_velocity": 0.15},
  "ai_mastery_with_baseline": {"frontier_navigation": 0.30, "reliance_calibration": 0.25, "prompt_quality": 0.15, "learning_velocity": 0.15, "leverage_gain": 0.15},
  "future_readiness": {"verification_discipline": 0.35, "efficient_leverage": 0.30, "adaptation_speed": 0.20, "evaluation_rigor": 0.15}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    from app.services.evaluation.weight_profile import _profile_hash

    profile_payload = json.loads(profile.read_text(encoding="utf-8"))
    lock.write_text(
        f"""
{{
  "approved": true,
  "approved_version": "2026-03-06",
  "profile_sha256": "{_profile_hash(profile_payload)}"
}}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = validate_weight_profile_freeze(profile_path=profile, lock_path=lock)
    assert result["pass"] is True


def test_get_weight_profile_defaults_when_lock_invalid(monkeypatch, tmp_path: Path):
    profile = tmp_path / "profile.json"
    lock = tmp_path / "profile.lock.json"
    profile.write_text(
        """
{
  "version": "2026-03-06",
  "method": "outcome_correlation_v1",
  "ai_mastery_without_baseline": {"frontier_navigation": 0.10, "reliance_calibration": 0.50, "prompt_quality": 0.20, "learning_velocity": 0.20},
  "ai_mastery_with_baseline": {"frontier_navigation": 0.10, "reliance_calibration": 0.30, "prompt_quality": 0.20, "learning_velocity": 0.20, "leverage_gain": 0.20},
  "future_readiness": {"verification_discipline": 0.10, "efficient_leverage": 0.50, "adaptation_speed": 0.20, "evaluation_rigor": 0.20}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    lock.write_text(
        """
{
  "approved": true,
  "approved_version": "2026-03-06",
  "profile_sha256": "deadbeef"
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    get_settings.cache_clear()
    get_weight_profile.cache_clear()
    monkeypatch.setenv("PROMPTCODE_EVALUATION_WEIGHT_PROFILE_PATH", str(profile))
    monkeypatch.setenv("PROMPTCODE_EVALUATION_WEIGHT_PROFILE_LOCK_PATH", str(lock))
    monkeypatch.setenv("PROMPTCODE_EVALUATION_WEIGHT_PROFILE_ENFORCE_LOCK", "true")

    loaded = get_weight_profile()
    assert loaded["version"] == "static_v1"

    get_settings.cache_clear()
    get_weight_profile.cache_clear()
