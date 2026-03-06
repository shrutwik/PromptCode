from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_PROFILE: dict[str, Any] = {
    "version": "static_v1",
    "method": "static_defaults",
    "ai_mastery_without_baseline": {
        "frontier_navigation": 0.35,
        "reliance_calibration": 0.30,
        "prompt_quality": 0.20,
        "learning_velocity": 0.15,
    },
    "ai_mastery_with_baseline": {
        "frontier_navigation": 0.30,
        "reliance_calibration": 0.25,
        "prompt_quality": 0.15,
        "learning_velocity": 0.15,
        "leverage_gain": 0.15,
    },
    "future_readiness": {
        "verification_discipline": 0.35,
        "efficient_leverage": 0.30,
        "adaptation_speed": 0.20,
        "evaluation_rigor": 0.15,
    },
}


def _resolve_profile_path() -> Path:
    settings = get_settings()
    configured = str(settings.evaluation_weight_profile_path or "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[3] / "benchmarks" / "ai_weight_profile.json"


def _normalize_weights(
    raw: Any,
    *,
    required_keys: list[str],
    default: dict[str, float],
) -> dict[str, float]:
    if not isinstance(raw, dict):
        return dict(default)

    values: dict[str, float] = {}
    for key in required_keys:
        try:
            values[key] = max(0.0, float(raw.get(key, default[key])))
        except (TypeError, ValueError):
            values[key] = float(default[key])

    total = sum(values.values())
    if total <= 0.0:
        return dict(default)

    return {
        key: round(values[key] / total, 6)
        for key in required_keys
    }


@lru_cache(maxsize=1)
def get_weight_profile() -> dict[str, Any]:
    path = _resolve_profile_path()
    if not path.exists():
        return dict(DEFAULT_PROFILE)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load weight profile from %s; using defaults", path)
        return dict(DEFAULT_PROFILE)

    normalized = dict(DEFAULT_PROFILE)
    normalized["version"] = str(raw.get("version") or normalized["version"])
    normalized["method"] = str(raw.get("method") or "profile_file")

    normalized["ai_mastery_without_baseline"] = _normalize_weights(
        raw.get("ai_mastery_without_baseline"),
        required_keys=list(DEFAULT_PROFILE["ai_mastery_without_baseline"].keys()),
        default=DEFAULT_PROFILE["ai_mastery_without_baseline"],
    )
    normalized["ai_mastery_with_baseline"] = _normalize_weights(
        raw.get("ai_mastery_with_baseline"),
        required_keys=list(DEFAULT_PROFILE["ai_mastery_with_baseline"].keys()),
        default=DEFAULT_PROFILE["ai_mastery_with_baseline"],
    )
    normalized["future_readiness"] = _normalize_weights(
        raw.get("future_readiness"),
        required_keys=list(DEFAULT_PROFILE["future_readiness"].keys()),
        default=DEFAULT_PROFILE["future_readiness"],
    )
    return normalized
