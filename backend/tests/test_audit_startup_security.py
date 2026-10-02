from types import SimpleNamespace

import pytest

from app.core.startup_security import validate_production_startup


def _settings(**changes):
    values = dict(debug=False, environment="production", allow_unsafe_local_runner=False,
                  runner="docker", interview_internal_token="test-internal-unique-token",
                  metrics_token="test-metrics-unique-token", jwt_secret="test-jwt-unique-random-secret")
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("changes", [
    {"debug": True}, {"allow_unsafe_local_runner": True}, {"runner": "local"},
    {"interview_internal_token": ""}, {"interview_internal_token": "change-me-internal-token"},
    {"metrics_token": ""}, {"metrics_token": "example-metrics-token"},
    {"jwt_secret": "local-dev-secret-change-in-production"},
])
def test_production_refuses_unsafe_settings(changes):
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_production_startup(_settings(**changes))


def test_production_accepts_safe_settings():
    validate_production_startup(_settings())


def test_debug_off_cannot_bypass_gate_with_development_marker():
    with pytest.raises(RuntimeError):
        validate_production_startup(_settings(environment="development", metrics_token=""))


def test_local_debug_does_not_need_deployment_secrets():
    validate_production_startup(_settings(debug=True, environment="development", runner="local", metrics_token=""))


def test_lifespan_refuses_boot_before_serving(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "get_settings", lambda: _settings(debug=True))
    with pytest.raises(RuntimeError, match="PROMPTCODE_DEBUG"):
        with TestClient(main.app):
            pytest.fail("Unsafe app reached running state")
