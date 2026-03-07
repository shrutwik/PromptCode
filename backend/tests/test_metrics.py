from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app import main as main_module
from app.core.config import get_settings


def test_metrics_endpoint_returns_prometheus_text(monkeypatch):
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
