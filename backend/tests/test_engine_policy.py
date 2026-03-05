from __future__ import annotations

from app.services.evaluation.engine import (
    _apply_overall_caps,
    _build_evaluation_manifest,
    _default_evaluation_seed,
    _detect_metric_gaming,
)


def test_apply_overall_caps_applies_all_caps():
    overall, events = _apply_overall_caps(
        raw_overall=0.91,
        accuracy=0.32,
        rule_adherence=0.42,
        anti_gaming_triggered=True,
    )
    assert overall == 0.45
    assert len(events) == 3
    assert events[0]["reason"] == "accuracy_below_0.40"
    assert events[1]["reason"] == "rule_adherence_below_0.50"
    assert events[2]["reason"] == "anti_gaming_triggered"


def test_evaluation_manifest_is_deterministic():
    run_plan = [
        {"run_type": "clean", "run_index": 0, "meta": {"seed": None, "perturbation": "none"}},
        {"run_type": "perturbed", "run_index": 0, "meta": {"seed": 123, "perturbation": "normal"}},
    ]
    run_records = [
        {
            "run_type": "clean",
            "run_index": 0,
            "status": "pass",
            "accuracy": 0.9,
            "schema_valid": True,
            "tokens_total": 100,
            "cost_usd": 0.01,
            "latency_ms": 500,
            "llm_calls": 1,
            "retries": 0,
            "meta": {"seed": None},
        }
    ]
    scores = {
        "accuracy": 0.9,
        "robustness": 0.8,
        "reliability": 0.85,
        "efficiency": 0.7,
        "prompt_quality": 0.75,
        "orchestration": 0.8,
        "calibration": 0.5,
        "rule_adherence": 0.92,
        "overall": 0.81,
        "raw_overall": 0.81,
    }
    challenge_config = {
        "accuracy_mode": "json",
        "expected_calls": 3,
        "processing_rules": {"a": 1},
        "hidden_tests": {"private_validation": [{"name": "h1"}]},
    }

    m1 = _build_evaluation_manifest(
        entrypoint="main.py",
        challenge_config=challenge_config,
        evaluation_seed=42,
        run_plan=run_plan,
        run_records=run_records,
        scores=scores,
    )
    m2 = _build_evaluation_manifest(
        entrypoint="main.py",
        challenge_config=challenge_config,
        evaluation_seed=42,
        run_plan=run_plan,
        run_records=run_records,
        scores=scores,
    )
    assert m1["replay_hash"] == m2["replay_hash"]
    assert m1["challenge_fingerprint"] == m2["challenge_fingerprint"]


def test_default_evaluation_seed_is_stable_for_same_config():
    cfg = {
        "accuracy_mode": "json",
        "inputs": {"x": [1, 2, 3]},
        "ground_truth": {"ok": True},
        "processing_rules": {"a": 1},
        "hidden_tests": {"tier": [{"inputs": {"x": [4]}}]},
    }
    s1 = _default_evaluation_seed(cfg)
    s2 = _default_evaluation_seed(cfg)
    assert s1 == s2
    assert s1 > 0


def test_detect_metric_gaming_flags_repetitive_low_schema_runs():
    runs = [
        {"output_hash": "x", "schema_valid": False, "output_chars": 40},
        {"output_hash": "x", "schema_valid": False, "output_chars": 38},
        {"output_hash": "x", "schema_valid": False, "output_chars": 42},
        {"output_hash": "x", "schema_valid": False, "output_chars": 41},
        {"output_hash": "x", "schema_valid": True, "output_chars": 39},
    ]
    result = _detect_metric_gaming(
        runs=runs,
        total_tokens=5000,
        total_calls=8,
        accuracy=0.6,
        robustness=0.45,
    )
    assert result["triggered"] is True
