"""Practice runs show real counts, per-test rows, and fail-closed notices."""

from __future__ import annotations

import pytest

from app.services.interview.execution_feedback import (
    candidate_case_rows,
    complete_report,
    practice_notice,
)
from app.services.interview.registry import get_runner_config
from app.services.interview.runner import _clip, _parse_test_counts


def test_pytest_summary_counts_failed_before_passed():
    output = "1 failed, 3 passed, 2 warnings in 0.35s\n"
    assert _parse_test_counts(output) == {
        "passed": 3,
        "failed": 1,
        "skipped": 0,
        "total": 4,
    }


def test_clip_appends_truncation_notice():
    text, truncated = _clip("abcdefghij", 8)
    assert truncated is True
    assert "Output truncated" in text
    assert len(text) <= 8 or text.endswith("limit.]")


def test_candidate_cases_keep_failure_output_and_duration():
    rows = candidate_case_rows([
        {"id": "tests/test_a.py::test_a", "phase": "setup", "outcome": "passed", "duration_ms": 2, "output": ""},
        {"id": "tests/test_a.py::test_a", "phase": "call", "outcome": "failed", "duration_ms": 9, "output": "KeyError: hold_reason"},
        {"id": "tests/test_a.py::test_a", "phase": "teardown", "outcome": "passed", "duration_ms": 1, "output": ""},
    ])
    assert rows == [{
        "id": "tests/test_a.py::test_a",
        "outcome": "failed",
        "duration_ms": 12,
        "output": "KeyError: hold_reason",
    }]


def test_missing_expected_ids_fail_closed_with_an_explanation():
    report = {
        "version": 1,
        "complete": True,
        "exit_code": 0,
        "records": [
            {"id": "tests/test_a.py::test_a", "phase": "setup", "outcome": "passed"},
            {"id": "tests/test_a.py::test_a", "phase": "call", "outcome": "passed"},
            {"id": "tests/test_a.py::test_a", "phase": "teardown", "outcome": "passed"},
        ],
    }
    expected = ["tests/test_a.py::test_a", "tests/test_a.py::test_missing"]
    assert complete_report(report, expected) is False
    notice = practice_notice(
        report=report,
        expected_ids=expected,
        exit_code=0,
        timed_out=False,
        truncated=False,
        report_ok=False,
        is_python=True,
    )
    assert "Missing expected test IDs" in notice
    assert "test_missing" in notice
    assert "fails closed" in notice


def test_python_registry_declares_collected_test_ids():
    expected = {
        "order-hold-reason": [
            "tests/test_orders.py::test_get_legacy_order_shape",
            "tests/test_orders.py::test_hold_sets_status",
            "tests/test_orders.py::test_release_clears_hold",
            "tests/test_orders.py::test_hold_reason_round_trip_and_legacy_null",
        ],
    }
    for slug, ids in expected.items():
        config = get_runner_config(slug)
        assert config["expectedTestIds"] == ids
