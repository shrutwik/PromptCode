from __future__ import annotations

import asyncio

import pytest

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app import main as main_module
from app.core.config import get_settings
from app.db.base import Base


async def create_schema(engine):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def test_metrics_endpoint_returns_prometheus_text(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_METRICS_TOKEN", "metrics-secret")
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        # Hit /health so there is at least one recorded request.
        client.get("/health")
        response = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_metrics_endpoint_requires_token_in_non_debug_mode(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "false")
    monkeypatch.setenv("PROMPTCODE_RUNNER", "docker")
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN", "test-internal-token")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "prod-metrics-test-secret")
    monkeypatch.setenv("DOMAIN", "api.example.com")
    monkeypatch.setenv(
        "PROMPTCODE_DATABASE_URL",
        "postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
    )
    monkeypatch.setenv("PROMPTCODE_OPENAI_API_KEY", "sk-live-metrics-test-key")
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "openai")
    monkeypatch.setenv("PROMPTCODE_OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PROMPTCODE_EXECUTION_BROKER_URL", "https://runner.example.net")
    monkeypatch.setenv("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN", "prod-executor-secret-abcdef-0123456789")
    monkeypatch.delenv("PROMPTCODE_METRICS_TOKEN", raising=False)
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with pytest.raises(RuntimeError, match="PROMPTCODE_METRICS_TOKEN"):
        with TestClient(app):
            pytest.fail("Missing production metrics secret must prevent startup")

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_metrics_endpoint_accepts_bearer_token_in_non_debug_mode(monkeypatch):
    from pathlib import Path
    exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda path: False if str(path) == '/var/run/docker.sock' else exists(path))
    monkeypatch.delenv('DOCKER_HOST', raising=False)
    monkeypatch.setenv("PROMPTCODE_DEBUG", "false")
    monkeypatch.setenv("PROMPTCODE_RUNNER", "docker")
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN", "test-internal-token")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "prod-metrics-test-secret")
    monkeypatch.setenv("DOMAIN", "api.example.com")
    monkeypatch.setenv(
        "PROMPTCODE_DATABASE_URL",
        "postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
    )
    monkeypatch.setenv("PROMPTCODE_OPENAI_API_KEY", "sk-live-metrics-test-key")
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "openai")
    monkeypatch.setenv("PROMPTCODE_OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PROMPTCODE_EXECUTION_BROKER_URL", "https://runner.example.net")
    monkeypatch.setenv("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN", "prod-executor-secret-abcdef-0123456789")
    monkeypatch.setenv("PROMPTCODE_METRICS_TOKEN", "metrics-secret")
    # Production startup validation requires a >=32-byte signing key. Supply it here
    # rather than depending on the developer's (or CI's) environment, which made this
    # test pass or fail depending on who ran it.
    monkeypatch.setenv("PROMPTCODE_GRADING_SIGNING_KEY", "metrics-test-grading-signing-key-32bytes+")
    # An explicit provider keeps the key from being replaced by legacy DeepSeek routing.
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "openai")
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    asyncio.run(create_schema(async_engine))
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        response = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})

    assert response.status_code == 200
    assert "http_requests_total" in response.text

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())
