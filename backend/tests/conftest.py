from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import auth as auth_routes

    monkeypatch.setattr(
        auth_routes,
        "_auth_rate_limiter",
        auth_routes._InMemoryRateLimiter(
            window_seconds=auth_routes._AUTH_RATE_WINDOW,
            max_attempts=auth_routes._AUTH_RATE_LIMIT,
        ),
    )
