"""Frontend overload handling: a saturated system must not look broken.

The audit found no 429/503 or `Retry-After` handling anywhere in `frontend/`, so
the bounded execution queue's queueing behaviour surfaced as a raw error. These
are static contract checks: the repository has no JS test runner, so they assert
the behaviour is present and wired rather than executing a browser.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def test_api_parses_retry_after_and_marks_retryable_errors():
    api = _read("interview-api.js")
    assert "Retry-After" in api
    assert "_retryAfterMs" in api
    assert re.search(r"RETRYABLE_STATUSES\s*:\s*\[\s*429\s*,\s*503\s*\]", api)
    # The error object must carry the machine-readable signal, not just a message.
    assert "err.retryAfterMs" in api
    assert "err.retryable" in api


def test_capacity_waiting_is_bounded():
    api = _read("interview-api.js")
    assert "MAX_CAPACITY_WAIT_MS" in api
    # A single Retry-After cannot pin a caller forever.
    assert "Math.min" in api
    assert "maxAttempts" in api
    assert "maxWaitMs" in api


def test_test_runner_waits_out_overload_instead_of_failing():
    api = _read("interview-api.js")
    runner = api[api.index("runTestsQueued") :]
    assert "isRetryable(err)" in runner
    assert "onWait" in runner
    assert "err.queued = true" in runner


def test_session_ui_shows_a_queued_state_and_keeps_the_run():
    session = _read("js/pages/interview-session.js")
    assert "runTestsQueued" in session
    assert "QUEUED" in session
    assert "onWait" in session
    # The existing design system already had a warning tone for busy states.
    assert 'setSessionStatus("busy", "Queued")' in session
    # Reaching the wait limit must not discard the candidate's saved work.
    assert "Your code is saved" in session


def test_queued_state_has_a_visible_style():
    css = _read("interview.css")
    assert re.search(r"\.term-meta\s+\.queued\s*\{", css)
