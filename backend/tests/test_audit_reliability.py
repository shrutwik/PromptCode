"""Failure behavior for the database, AI provider, and Docker runner."""

from __future__ import annotations

import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import main as main_module
from app.core.config import get_settings
from app.services.interview.ai_provider import AIProviderError, ProductionAIProvider
from app.services.interview.runner import IsolatedRunner


class _HangingConnection:
    async def __aenter__(self):
        await asyncio.sleep(30)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, *_args, **_kwargs):
        return None


class _HangingEngine:
    def connect(self):
        return _HangingConnection()

    async def dispose(self):
        return None


def test_ready_times_out_when_database_hangs(monkeypatch):
    monkeypatch.setattr(main_module, "engine", _HangingEngine())
    get_settings.cache_clear()
    app = main_module.create_app()
    with TestClient(app) as client:
        started = time.monotonic()
        ready = client.get("/ready")
        health_ready = client.get("/health/ready")
        elapsed = time.monotonic() - started
    assert ready.status_code == 503
    assert ready.json()["detail"] == "database unavailable"
    assert health_ready.status_code == 503
    assert elapsed < 12
    get_settings.cache_clear()


def test_postgres_connect_timeout_is_bounded():
    engine = create_async_engine(
        "postgresql+asyncpg://promptcode:promptcode@127.0.0.1:1/promptcode",
        connect_args={"timeout": 1, "statement_cache_size": 0},
    )

    async def _ping() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    started = time.monotonic()
    with pytest.raises(Exception):
        asyncio.run(_ping())
    assert time.monotonic() - started < 3
    asyncio.run(engine.dispose())


def test_ai_provider_times_out_on_slow_response(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            time.sleep(2)
            self.send_response(200)
            self.end_headers()

        def log_message(self, _format, *_args):
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("PROMPTCODE_AI_API_KEY", "sk-audit-test")
    monkeypatch.setenv("PROMPTCODE_AI_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("PROMPTCODE_AI_TIMEOUT_SECONDS", "0.4")
    try:
        started = time.monotonic()
        with pytest.raises(AIProviderError) as exc:
            asyncio.run(
                ProductionAIProvider().complete(
                    messages=[{"role": "user", "content": "hi"}],
                    system="sys",
                )
            )
        elapsed = time.monotonic() - started
    finally:
        server.shutdown()
        server.server_close()
    assert exc.value.code == "timeout"
    assert exc.value.retryable is True
    assert elapsed < 1.5


def test_docker_daemon_down_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://127.0.0.1:1")
    workspace = tmp_path / "session"
    workspace.mkdir()
    started = time.monotonic()
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q"))
    elapsed = time.monotonic() - started
    assert result["ok"] is False
    assert result["runner"] == "docker"
    assert result["error_code"] == "docker_unavailable"
    assert elapsed < 5


def test_timed_out_container_is_killed_and_removed(tmp_path):
    workspace = tmp_path / "session"
    workspace.mkdir()
    container = MagicMock()
    container.attrs = {"State": {"Running": False}}
    container.wait.side_effect = TimeoutError("still running")
    client = MagicMock()
    client.containers.run.return_value = container

    with patch(
        "app.services.interview.runner._docker_client", return_value=client
    ), patch(
        "app.services.interview.runner._docker_errors",
        return_value=(Exception, type("ImageNotFound", (Exception,), {})),
    ):
        result = asyncio.run(
            IsolatedRunner().run_tests(
                workspace,
                "pytest -q",
                runner_config={"image": "promptcode-runner-python:latest", "timeoutSeconds": 5},
            )
        )

    assert result["timed_out"] is True
    assert result["ok"] is False
    container.kill.assert_called()
    container.remove.assert_called()
    assert "docker.sock" not in str(client.containers.run.call_args)


def test_container_removed_by_name_when_remove_fails(tmp_path):
    workspace = tmp_path / "session"
    workspace.mkdir()
    container = MagicMock()
    container.attrs = {"State": {"Running": False}}
    container.wait.side_effect = TimeoutError("still running")
    container.remove.side_effect = RuntimeError("device busy")
    named = MagicMock()
    client = MagicMock()
    client.containers.run.return_value = container
    client.containers.get.return_value = named

    with patch(
        "app.services.interview.runner._docker_client", return_value=client
    ), patch(
        "app.services.interview.runner._docker_errors",
        return_value=(Exception, type("ImageNotFound", (Exception,), {})),
    ):
        result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q"))

    assert result["timed_out"] is True
    named.remove.assert_called()
    assert Path(workspace).is_dir()
