"""Unit tests for the in-memory sliding-window rate limiter."""
from __future__ import annotations

import time

import pytest

from app.core.ratelimit import _store, check_rate_limit


@pytest.fixture(autouse=True)
def clear_store():
    """Ensure each test starts with a clean rate-limit store."""
    _store.clear()
    yield
    _store.clear()


# ── Basic allow / deny ────────────────────────────────────────────────────────


def test_allows_requests_within_limit():
    for _ in range(5):
        assert check_rate_limit("ip:1.2.3.4", limit=5, window_seconds=60) is True


def test_blocks_request_over_limit():
    for _ in range(5):
        check_rate_limit("ip:1.2.3.4", limit=5, window_seconds=60)
    assert check_rate_limit("ip:1.2.3.4", limit=5, window_seconds=60) is False


def test_different_keys_are_independent():
    for _ in range(5):
        check_rate_limit("ip:1.1.1.1", limit=5, window_seconds=60)
    # First key is exhausted; second key should still be allowed.
    assert check_rate_limit("ip:2.2.2.2", limit=5, window_seconds=60) is True


def test_limit_of_one():
    assert check_rate_limit("ip:x", limit=1, window_seconds=60) is True
    assert check_rate_limit("ip:x", limit=1, window_seconds=60) is False


# ── Sliding window expiry ─────────────────────────────────────────────────────


def test_expired_entries_do_not_count():
    """Entries older than window_seconds must not contribute to the count."""
    past = time.monotonic() - 61  # older than a 60s window
    _store["ip:old"] = [past, past, past, past, past]
    # All 5 stored entries are expired — should be allowed (window is clear).
    assert check_rate_limit("ip:old", limit=5, window_seconds=60) is True


def test_mixed_old_and_recent_entries():
    """Only entries within the window count toward the limit."""
    past = time.monotonic() - 61
    # 4 expired + 4 recent = 4 active; limit=5, so one more is OK.
    _store["ip:mix"] = [past, past, past, past]
    for _ in range(4):
        check_rate_limit("ip:mix", limit=5, window_seconds=60)
    # 4 active entries now; next should still be allowed.
    assert check_rate_limit("ip:mix", limit=5, window_seconds=60) is True
    # 5 active entries; next must be blocked.
    assert check_rate_limit("ip:mix", limit=5, window_seconds=60) is False


# ── Memory hygiene ────────────────────────────────────────────────────────────


def test_store_bounded_after_expiry():
    """Expired windows should not accumulate in _store indefinitely."""
    past = time.monotonic() - 61
    _store["ip:clean"] = [past]
    # Calling check_rate_limit prunes the expired entry and cleans the key.
    check_rate_limit("ip:clean", limit=5, window_seconds=60)
    assert "ip:clean" not in _store or len(_store["ip:clean"]) == 1
