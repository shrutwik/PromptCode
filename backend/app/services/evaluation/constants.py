"""Shared evaluation constants."""

from __future__ import annotations

SCORE_WEIGHTS = {
    "accuracy": 0.35,
    "robustness": 0.15,
    "reliability": 0.10,
    "efficiency": 0.15,
    "prompt_quality": 0.10,
    "orchestration": 0.10,
    "calibration": 0.05,
}

PERTURBATION_CONFIG_VERSION = "v1"
