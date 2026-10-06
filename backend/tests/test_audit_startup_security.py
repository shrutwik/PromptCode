from types import SimpleNamespace

import pytest

from app.core.startup_security import validate_production_startup


def _settings(**changes):
    values = dict(debug=False, environment="production", allow_unsafe_local_runner=False,
                  runner="docker", interview_internal_token="test-internal-unique-token",
                  metrics_token="test-metrics-unique-token", jwt_secret="test-jwt-unique-random-secret",
                  execution_broker_url="https://execution.example.com",
                  sandbox_executor_token="test-execution-management-secret-32bytes",
                  grading_signing_key="test-grading-signing-key-32bytes-minimum")
    values.update(changes)
    return SimpleNamespace(**values)


def _modal_settings(**changes):
    """A Modal + Supabase deployment: no Docker host, no broker, no inline grading."""
    values = dict(debug=False, environment="production", allow_unsafe_local_runner=False,
                  runner="local", interview_internal_token="test-internal-unique-token",
                  metrics_token="test-metrics-unique-token", jwt_secret="test-jwt-unique-random-secret",
                  execution_backend="modal", storage_backend="supabase",
                  modal_sandbox_image_node="promptcode-node:latest",
                  modal_sandbox_image_python="promptcode-python:latest",
                  supabase_url="https://testproject.supabase.co",
                  supabase_service_role_key="test-supabase-service-role-key-32bytes",
                  submission_inline_queue_processing=False,
                  execution_broker_url="", execution_broker_mode=False, sandbox_executor_url="",
                  grading_signing_key="test-grading-signing-key-32bytes-minimum")
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("changes", [
    {"debug": True}, {"allow_unsafe_local_runner": True}, {"runner": "local"},
    {"interview_internal_token": ""}, {"interview_internal_token": "change-me-internal-token"},
    {"metrics_token": ""}, {"metrics_token": "example-metrics-token"},
    {"jwt_secret": "local-dev-secret-change-in-production"},
    {"execution_broker_url": ""}, {"execution_broker_url": "http://execution.example.com"},
    {"execution_broker_url": "https://127.0.0.1"}, {"sandbox_executor_token": ""},
    {"grading_signing_key": ""}, {"grading_signing_key": "too-short"},
])
def test_production_refuses_unsafe_settings(changes):
    with pytest.raises(RuntimeError, match="Unsafe production configuration"):
        validate_production_startup(_settings(**changes))


def test_production_accepts_safe_settings(monkeypatch):
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    validate_production_startup(_settings())


def test_production_refuses_daemon_socket(monkeypatch):
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: True)
    with pytest.raises(RuntimeError, match="Docker daemon access"):
        validate_production_startup(_settings())


def test_production_refuses_remote_docker_daemon(monkeypatch):
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: False)
    monkeypatch.setenv("DOCKER_HOST", "tcp://execution-host:2375")
    with pytest.raises(RuntimeError, match="Docker daemon access"):
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


def test_queue_worker_refuses_unsafe_configuration_before_processing(monkeypatch):
    from scripts import run_queue_worker
    monkeypatch.setattr(run_queue_worker, "configure_logging", lambda: None)
    monkeypatch.setattr(run_queue_worker, "get_settings", lambda: _settings(debug=True))
    monkeypatch.setattr(run_queue_worker, "worker_loop", lambda: pytest.fail("Unsafe worker started"))
    with pytest.raises(RuntimeError, match="PROMPTCODE_DEBUG"):
        run_queue_worker.main()


# --- Modal + Supabase deployment -------------------------------------------------
# The Modal deployment has no Docker daemon and no execution broker, so the Docker
# checks must not run for it; it has its own requirements instead. Every check that
# today's Docker mode needs stays enforced (see the tests above).


def test_modal_production_config_passes(monkeypatch):
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    validate_production_startup(_modal_settings())


def test_modal_config_still_forbids_docker_daemon_access(monkeypatch):
    """The no-Docker-daemon invariant is deployment-independent.

    A correct Modal container has no socket and no DOCKER_HOST, so this passes
    trivially there; a Modal-configured app mistakenly placed on a Docker host is
    still rejected rather than silently gaining daemon access.
    """
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: True)
    monkeypatch.setenv("DOCKER_HOST", "tcp://execution-host:2375")
    with pytest.raises(RuntimeError, match="Docker daemon access"):
        validate_production_startup(_modal_settings())


@pytest.mark.parametrize("changes, expected", [
    ({"modal_sandbox_image_node": ""}, "PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE"),
    ({"modal_sandbox_image_python": ""}, "PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON"),
    ({"storage_backend": "filesystem"}, "PROMPTCODE_STORAGE_BACKEND"),
    ({"supabase_url": "http://testproject.supabase.co"}, "PROMPTCODE_SUPABASE_URL"),
    ({"supabase_url": ""}, "PROMPTCODE_SUPABASE_URL"),
    ({"supabase_service_role_key": ""}, "PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY"),
    ({"supabase_service_role_key": "change-me-supabase-service-role-key"}, "PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY"),
    ({"allow_unsafe_local_runner": True}, "unsafe local runner"),
    ({"execution_broker_mode": True}, "Docker execution broker"),
])
def test_modal_production_refuses_unsafe_settings(changes, expected):
    with pytest.raises(RuntimeError, match="Unsafe production configuration") as excinfo:
        validate_production_startup(_modal_settings(**changes))

    assert expected in str(excinfo.value)


def test_modal_config_does_not_require_docker_broker_or_runner(monkeypatch):
    """No execution broker URL, token or Docker runner may be demanded in this mode."""
    # The machine-independent part of this assertion: not the developer's own
    # Docker install. The no-daemon invariant is covered separately below.
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    validate_production_startup(_modal_settings(
        runner="local", execution_broker_url="", sandbox_executor_token="",
    ))


def test_modal_config_allows_broker_and_executor_urls(monkeypatch):
    """Broker/executor URLs must not be rejected: the trusted-evaluation path may be
    wired through them, and forbidding them would block that wiring."""
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: False)
    monkeypatch.delenv("DOCKER_HOST", raising=False)
    validate_production_startup(_modal_settings(
        execution_broker_url="https://execution.example.com",
        sandbox_executor_url="http://sandbox-executor:8877",
        sandbox_executor_token="test-execution-management-secret-32bytes",
        runner="docker",
    ))


@pytest.mark.parametrize("settings_factory", [_settings, _modal_settings])
def test_placeholder_grading_signing_key_fails_in_every_mode(settings_factory):
    # 38 bytes: only the placeholder rule can reject this, not the length rule.
    placeholder = "replace-this-with-a-long-random-secret"
    assert len(placeholder.encode()) >= 32

    with pytest.raises(RuntimeError, match="grading signing key"):
        validate_production_startup(settings_factory(grading_signing_key=placeholder))


@pytest.mark.parametrize("settings_factory", [_settings, _modal_settings])
def test_short_grading_signing_key_fails_in_every_mode(settings_factory):
    with pytest.raises(RuntimeError, match="grading signing key"):
        validate_production_startup(settings_factory(grading_signing_key="too-short"))


def test_explicit_docker_backend_still_enforces_today_rules(monkeypatch):
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: True)
    with pytest.raises(RuntimeError, match="Docker daemon access"):
        validate_production_startup(_settings(execution_backend="docker"))

    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: False)
    with pytest.raises(RuntimeError, match="separate HTTPS execution broker"):
        validate_production_startup(_settings(execution_backend="docker", execution_broker_url=""))

    with pytest.raises(RuntimeError, match="management token"):
        validate_production_startup(_settings(execution_backend="docker", sandbox_executor_token=""))


def test_unknown_execution_backend_falls_back_to_docker_checks(monkeypatch):
    """An unrecognised backend must not silently skip the stricter checks."""
    monkeypatch.setattr("app.core.startup_security.Path.exists", lambda _path: True)
    with pytest.raises(RuntimeError, match="Docker daemon access"):
        validate_production_startup(_modal_settings(execution_backend="kubernetes"))
