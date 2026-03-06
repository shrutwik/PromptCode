from __future__ import annotations

from app.services.evaluation.engine import (
    _apply_overall_caps,
    _build_counterfactual_baseline_code,
    _build_evaluation_manifest,
    _build_usage_breakdown,
    _counterfactual_template_for_challenge,
    _compute_credibility,
    _default_evaluation_seed,
    _detect_metric_gaming,
    _normalize_leverage_gain,
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


def test_normalize_leverage_gain_bounds():
    assert _normalize_leverage_gain(-0.5) == 0.0
    assert _normalize_leverage_gain(0.5) == 1.0
    mid = _normalize_leverage_gain(0.1)
    assert 0.0 <= mid <= 1.0


def test_build_counterfactual_baseline_code_contains_sdk_call():
    code = _build_counterfactual_baseline_code(
        {
            "counterfactual_model": "gpt-4o-mini",
            "processing_rules": {"a": 1},
            "ground_truth": {"x": "y"},
        },
        "Extract fields",
    )
    assert "from promptcode import llm" in code
    assert "llm.call(" in code
    assert "Return ONLY JSON" in code


def test_build_usage_breakdown_aggregates_models_and_run_types():
    breakdown = _build_usage_breakdown(
        telemetry_calls=[
            {
                "model": "gpt-4o",
                "tokens_prompt": 100,
                "tokens_completion": 40,
                "tokens_total": 140,
                "cost_usd": 0.01,
                "latency_ms": 300,
                "retry_index": 0,
            },
            {
                "model": "gpt-4o-mini",
                "tokens_prompt": 50,
                "tokens_completion": 20,
                "tokens_total": 70,
                "cost_usd": 0.002,
                "latency_ms": 120,
                "retry_index": 1,
            },
        ],
        runs=[
            {"run_type": "clean", "status": "pass", "llm_calls": 1, "tokens_total": 140, "cost_usd": 0.01, "latency_ms": 300},
            {"run_type": "perturbed", "status": "fail", "llm_calls": 1, "tokens_total": 70, "cost_usd": 0.002, "latency_ms": 120},
        ],
    )
    assert breakdown["totals"]["calls"] == 2
    assert breakdown["totals"]["retries"] == 1
    assert breakdown["totals"]["total_tokens"] == 210
    assert len(breakdown["models"]) == 2
    assert any(r["run_type"] == "clean" for r in breakdown["run_types"])


def test_compute_credibility_high_when_signals_are_strong():
    result = _compute_credibility(
        prompt_judge_method="llm_judge",
        calibration_samples=12,
        run_count=8,
        hidden_set_count=2,
        counterfactual_status="ok",
        anti_gaming_triggered=False,
        hardcoded=False,
        run_accuracy_ci_half_width=0.03,
    )
    assert result["band"] == "high"
    assert result["score"] >= 0.75


def test_counterfactual_template_is_challenge_specific():
    template = _counterfactual_template_for_challenge(
        {"challenge_slug": "resume-parsing-pipeline", "challenge_category": "extraction"}
    )
    assert "resume" in template["system_prompt"].lower()
