from __future__ import annotations

import asyncio

import app.models  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app import main as main_module
from app.core.config import get_settings


class _NoOpConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def run_sync(self, fn):
        return None


class _FailingConnection:
    async def __aenter__(self):
        raise RuntimeError("database unavailable")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FailingEngine:
    def begin(self):
        return _NoOpConnection()

    def connect(self):
        return _FailingConnection()

    async def dispose(self):
        return None


class _BeginForbiddenEngine:
    def __init__(self, delegate):
        self._delegate = delegate

    def begin(self):
        raise AssertionError("startup should not call engine.begin()")

    def connect(self):
        return self._delegate.connect()

    async def dispose(self):
        await self._delegate.dispose()


def test_health_and_ready_are_ok_with_live_database(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_health_sets_security_headers(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    if not get_settings().debug:
        assert response.headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )
    else:
        assert "Strict-Transport-Security" not in response.headers

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_unhandled_exception_returns_json_500(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    expected_detail = "boom" if get_settings().debug else "Internal server error"
    assert response.json() == {"detail": expected_detail}

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_ready_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(main_module, "engine", _FailingEngine())
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 503
    assert ready.json() == {"status": "error", "detail": "database unavailable"}
    get_settings.cache_clear()


def test_startup_does_not_attempt_schema_creation(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", _BeginForbiddenEngine(async_engine))
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert ready.status_code == 200

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_ready_returns_503_when_sandbox_executor_is_unavailable(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def fake_sandbox_executor_ready(_settings) -> bool:
        return False

    monkeypatch.setenv("PROMPTCODE_SANDBOX_EXECUTOR_URL", "http://sandbox-executor:8090")
    monkeypatch.setenv("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN", "secret-token")
    monkeypatch.setattr(main_module, "engine", async_engine)
    monkeypatch.setattr(main_module, "_sandbox_executor_ready", fake_sandbox_executor_ready)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        ready = client.get("/ready")

    assert ready.status_code == 503
    assert ready.json() == {"status": "error", "detail": "sandbox executor unavailable"}

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_ready_does_not_require_worker_heartbeat_when_inline_processing_disabled(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    monkeypatch.setenv("PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING", "false")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        ready = client.get("/ready")

    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_ready_stays_ok_when_inline_processing_disabled_and_schema_is_present(monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    monkeypatch.setenv("PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING", "false")
    monkeypatch.setenv("PROMPTCODE_WORKER_HEARTBEAT_TIMEOUT_SECONDS", "30")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        ready = client.get("/ready")

    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())
