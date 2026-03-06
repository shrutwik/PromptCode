from __future__ import annotations

import hashlib
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


def _resolve_profile_lock_path() -> Path:
    settings = get_settings()
    configured = str(settings.evaluation_weight_profile_lock_path or "").strip()
    if configured:
        return Path(configured).expanduser()
    default_profile = _resolve_profile_path()
    return default_profile.with_name("ai_weight_profile.lock.json")


def _profile_hash(raw: dict[str, Any]) -> str:
    payload = {
        "version": str(raw.get("version") or ""),
        "ai_mastery_without_baseline": raw.get("ai_mastery_without_baseline"),
        "ai_mastery_with_baseline": raw.get("ai_mastery_with_baseline"),
        "future_readiness": raw.get("future_readiness"),
    }
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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


def validate_weight_profile_freeze(
    *,
    profile_path: Path | None = None,
    lock_path: Path | None = None,
) -> dict[str, Any]:
    profile = profile_path or _resolve_profile_path()
    lock = lock_path or _resolve_profile_lock_path()

    if not profile.exists():
        return {"pass": False, "reason": "profile_missing", "profile_path": str(profile)}
    if not lock.exists():
        return {"pass": False, "reason": "lock_missing", "lock_path": str(lock)}

    try:
        raw_profile = json.loads(profile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to parse profile file %s", profile)
        return {"pass": False, "reason": "profile_parse_error", "profile_path": str(profile)}

    try:
        raw_lock = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to parse lock file %s", lock)
        return {"pass": False, "reason": "lock_parse_error", "lock_path": str(lock)}

    if not bool(raw_lock.get("approved")):
        return {"pass": False, "reason": "lock_not_approved", "lock_path": str(lock)}

    approved_version = str(raw_lock.get("approved_version") or "")
    profile_version = str(raw_profile.get("version") or "")
    if not approved_version or approved_version != profile_version:
        return {
            "pass": False,
            "reason": "version_mismatch",
            "approved_version": approved_version,
            "profile_version": profile_version,
        }

    expected_hash = str(raw_lock.get("profile_sha256") or "")
    actual_hash = _profile_hash(raw_profile)
    if not expected_hash or expected_hash != actual_hash:
        return {
            "pass": False,
            "reason": "profile_hash_mismatch",
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }

    return {
        "pass": True,
        "profile_path": str(profile),
        "lock_path": str(lock),
        "version": profile_version,
        "profile_sha256": actual_hash,
    }


@lru_cache(maxsize=1)
def get_weight_profile() -> dict[str, Any]:
    settings = get_settings()
    path = _resolve_profile_path()
    if not path.exists():
        return dict(DEFAULT_PROFILE)

    if bool(settings.evaluation_weight_profile_enforce_lock):
        freeze = validate_weight_profile_freeze(profile_path=path)
        if not freeze.get("pass", False):
            logger.warning(
                "Weight profile lock validation failed (%s); using defaults",
                freeze.get("reason", "unknown"),
            )
            return dict(DEFAULT_PROFILE)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
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
