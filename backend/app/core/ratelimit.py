"""Lightweight in-process sliding-window rate limiter.

Thread-safe for single-process async servers (uvicorn without --workers).
Resets on process restart — acceptable for soft abuse prevention on auth
and submission endpoints.  For multi-process or multi-host deployments,
replace with a Redis-backed implementation.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

_store: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def check_rate_limit(key: str, *, limit: int, window_seconds: int) -> bool:
    """Return True if the request is allowed, False if rate-limited.

    Uses a sliding window counter keyed by *key*.  Expired entries are
    pruned on each call so memory stays bounded to active keys.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        window = _store[key]
        # Purge entries outside the current window.
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= limit:
            return False
        window.append(now)
        # Remove keys with empty windows to prevent unbounded dict growth.
        if not window:
            del _store[key]
        return True
