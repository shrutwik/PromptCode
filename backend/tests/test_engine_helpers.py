from app.services.evaluation.engine import _build_hidden_cases, _detect_metric_gaming


def test_build_hidden_cases_supports_configured_cases():
    cfg = {
        "hidden_tests": [
            {
                "name": "hidden_a",
                "inputs": {"claims": ["x"]},
                "ground_truth": [{"ok": True}],
                "accuracy_mode": "json",
            }
        ]
    }
    cases = _build_hidden_cases(cfg, "{}", "json")
    assert len(cases) == 1
    assert cases[0]["name"] == "hidden_a"
    assert cases[0]["accuracy_mode"] == "json"
    assert "\"ok\"" in cases[0]["ground_truth"]


def test_metric_gaming_detects_low_effort_low_quality_pattern():
    runs = [{"output_chars": 10}, {"output_chars": 12}, {"output_chars": 8}]
    result = _detect_metric_gaming(
        runs=runs,
        total_tokens=30,
        total_calls=1,
        accuracy=0.2,
        robustness=0.3,
    )
    assert result["triggered"] is True


def test_metric_gaming_not_triggered_for_normal_usage():
    runs = [{"output_chars": 300}, {"output_chars": 240}, {"output_chars": 180}]
    result = _detect_metric_gaming(
        runs=runs,
        total_tokens=3500,
        total_calls=8,
        accuracy=0.9,
        robustness=0.8,
    )
    assert result["triggered"] is False
