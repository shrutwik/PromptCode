from __future__ import annotations

from pathlib import Path

from docker.errors import DockerException
from fastapi.testclient import TestClient

from app import sandbox_executor


def test_sandbox_executor_health():
    with TestClient(sandbox_executor.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sandbox_executor_ready_uses_runtime_report(monkeypatch):
    monkeypatch.setattr(
        sandbox_executor,
        "_executor_runtime_report",
        lambda: {"status": "ok", "checks": {"docker": {"ok": True}}, "stats": {}},
    )

    with TestClient(sandbox_executor.app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sandbox_executor_ready_returns_503_on_runtime_failure(monkeypatch):
    monkeypatch.setattr(
        sandbox_executor,
        "_executor_runtime_report",
        lambda: {"status": "error", "checks": {"docker": {"ok": False}}, "stats": {}},
    )

    with TestClient(sandbox_executor.app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_sandbox_executor_requires_token(monkeypatch):
    monkeypatch.setattr(sandbox_executor.settings, "sandbox_executor_token", "secret-token")

    with TestClient(sandbox_executor.app) as client:
        response = client.post(
            "/v1/sandbox/run",
            json={
                "code": "print('ok')",
                "entrypoint": "main.py",
                "challenge_config": {"inputs": {}},
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid sandbox executor token."


def test_sandbox_executor_forwards_run_request(monkeypatch):
    monkeypatch.setattr(sandbox_executor.settings, "sandbox_executor_token", "secret-token")
    monkeypatch.setattr(sandbox_executor, "executor_state", sandbox_executor._ExecutorState())

    class FakeResult:
        success = True
        error = None

        @staticmethod
        def to_dict():
            return {
                "success": True,
                "output": "ok",
                "exit_code": 0,
                "telemetry": [],
                "error": None,
            }

    captured: dict[str, object] = {}

    def fake_run_local(code, entrypoint, challenge_config, *, run_id=None, input_overrides=None):
        captured["code"] = code
        captured["entrypoint"] = entrypoint
        captured["challenge_config"] = challenge_config
        captured["run_id"] = run_id
        captured["input_overrides"] = input_overrides
        return FakeResult()

    monkeypatch.setattr(sandbox_executor, "_run_in_sandbox_local", fake_run_local)

    with TestClient(sandbox_executor.app) as client:
        response = client.post(
            "/v1/sandbox/run",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "code": "print('ok')",
                "entrypoint": "main.py",
                "challenge_config": {"inputs": {"text": "hello"}},
                "run_id": "run-123",
                "input_overrides": {"text": "override"},
            },
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert captured == {
        "code": "print('ok')",
        "entrypoint": "main.py",
        "challenge_config": {"inputs": {"text": "hello"}},
        "run_id": "run-123",
        "input_overrides": {"text": "override"},
    }


def test_sandbox_executor_rejects_when_concurrency_limit_is_saturated(monkeypatch):
    monkeypatch.setattr(sandbox_executor.settings, "sandbox_executor_token", "secret-token")

    class FakeLimiter:
        async def acquire(self):
            return True

        def release(self):
            return None

    async def fake_wait_for(awaitable, timeout):
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError()

    monkeypatch.setattr(sandbox_executor, "_executor_run_limiter", lambda: FakeLimiter())
    monkeypatch.setattr(sandbox_executor, "_sandbox_executor_max_concurrent_runs", lambda: 2)
    monkeypatch.setattr(sandbox_executor, "_sandbox_executor_acquire_timeout_seconds", lambda: 3.0)
    monkeypatch.setattr(sandbox_executor.asyncio, "wait_for", fake_wait_for)

    with TestClient(sandbox_executor.app) as client:
        response = client.post(
            "/v1/sandbox/run",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "code": "print('ok')",
                "entrypoint": "main.py",
                "challenge_config": {"inputs": {}},
            },
        )

    assert response.status_code == 503
    assert "Sandbox executor saturated" in response.json()["detail"]


def test_sandbox_executor_status_reports_run_counters(monkeypatch):
    monkeypatch.setattr(sandbox_executor.settings, "sandbox_executor_token", "secret-token")
    monkeypatch.setattr(sandbox_executor, "executor_state", sandbox_executor._ExecutorState())
    monkeypatch.setattr(
        sandbox_executor,
        "_executor_runtime_report",
        lambda: {
            "status": "ok",
            "checks": {},
            "limits": {"max_concurrent_runs": 6, "acquire_timeout_seconds": 10.0},
            "stats": sandbox_executor.executor_state.snapshot(),
        },
    )

    class FakeResult:
        success = True
        error = None

        @staticmethod
        def to_dict():
            return {
                "success": True,
                "output": "ok",
                "exit_code": 0,
                "telemetry": [],
                "error": None,
            }

    monkeypatch.setattr(sandbox_executor, "_run_in_sandbox_local", lambda *args, **kwargs: FakeResult())

    with TestClient(sandbox_executor.app) as client:
        response = client.post(
            "/v1/sandbox/run",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "code": "print('ok')",
                "entrypoint": "main.py",
                "challenge_config": {"inputs": {}},
            },
        )
        status_response = client.get("/status")

    assert response.status_code == 200
    assert status_response.status_code == 200
    assert status_response.json()["stats"]["active_runs"] == 0
    assert status_response.json()["stats"]["total_runs"] == 1
    assert status_response.json()["stats"]["successful_runs"] == 1
    assert status_response.json()["stats"]["failed_runs"] == 0
    assert status_response.json()["limits"]["max_concurrent_runs"] == 6


def test_executor_runtime_report_checks_docker_image_and_workdir(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox_executor, "executor_state", sandbox_executor._ExecutorState())
    monkeypatch.setattr(sandbox_executor, "_sandbox_temp_root", lambda: Path(tmp_path))
    monkeypatch.setattr(sandbox_executor, "_sandbox_executor_max_concurrent_runs", lambda: 4)
    monkeypatch.setattr(sandbox_executor, "_sandbox_executor_acquire_timeout_seconds", lambda: 9.0)

    class FakeImages:
        def get(self, image_name: str):
            assert image_name == sandbox_executor.settings.sandbox_image
            return object()

    class FakeClient:
        def __init__(self):
            self.images = FakeImages()

        def ping(self):
            return True

        def close(self):
            return None

    monkeypatch.setattr(sandbox_executor.docker, "from_env", lambda: FakeClient())

    report = sandbox_executor._executor_runtime_report()

    assert report["status"] == "ok"
    assert report["checks"]["docker"]["ok"] is True
    assert report["checks"]["sandbox_image"]["ok"] is True
    assert report["checks"]["shared_workdir"]["ok"] is True
    assert report["limits"]["max_concurrent_runs"] == 4
    assert report["limits"]["acquire_timeout_seconds"] == 9.0


def test_executor_runtime_report_fails_when_docker_is_unavailable(monkeypatch):
    monkeypatch.setattr(sandbox_executor, "_sandbox_temp_root", lambda: None)
    monkeypatch.setattr(
        sandbox_executor.docker,
        "from_env",
        lambda: (_ for _ in ()).throw(DockerException("docker unavailable")),
    )

    report = sandbox_executor._executor_runtime_report()

    assert report["status"] == "error"
    assert report["checks"]["docker"]["ok"] is False
