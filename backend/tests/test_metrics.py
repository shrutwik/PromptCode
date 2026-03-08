from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app import main as main_module
from app.core.config import get_settings


def test_metrics_endpoint_returns_prometheus_text(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        # Hit /health so there is at least one recorded request.
        client.get("/health")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_metrics_endpoint_requires_token_in_non_debug_mode(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "false")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "prod-metrics-test-secret")
    monkeypatch.setenv("DOMAIN", "api.example.com")
    monkeypatch.setenv(
        "PROMPTCODE_DATABASE_URL",
        "postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
    )
    monkeypatch.setenv("PROMPTCODE_OPENAI_API_KEY", "sk-live-metrics-test-key")
    monkeypatch.delenv("PROMPTCODE_METRICS_TOKEN", raising=False)
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 401
    assert response.text == "Unauthorized"

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())


def test_metrics_endpoint_accepts_bearer_token_in_non_debug_mode(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "false")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "prod-metrics-test-secret")
    monkeypatch.setenv("DOMAIN", "api.example.com")
    monkeypatch.setenv(
        "PROMPTCODE_DATABASE_URL",
        "postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
    )
    monkeypatch.setenv("PROMPTCODE_OPENAI_API_KEY", "sk-live-metrics-test-key")
    monkeypatch.setenv("PROMPTCODE_METRICS_TOKEN", "metrics-secret")
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with TestClient(app) as client:
        response = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})

    assert response.status_code == 200
    assert "http_requests_total" in response.text

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())
