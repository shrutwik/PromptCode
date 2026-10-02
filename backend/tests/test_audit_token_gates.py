import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app import main
from app.core.config import get_settings
from app.db.session import get_db


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_ENVIRONMENT", "development")
    monkeypatch.setenv("PROMPTCODE_METRICS_TOKEN", "audit-metrics-secret")
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN", "audit-internal-secret")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main, "engine", engine)
    get_settings.cache_clear()
    app = main.create_app()
    async def no_database_access():
        yield object()  # Unauthorized requests must never query it.
    app.dependency_overrides[get_db] = no_database_access
    with TestClient(app) as value:
        yield value
    get_settings.cache_clear()
    asyncio.run(engine.dispose())


def test_metrics_requires_exact_token_even_in_debug(client):
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "audit-metrics-secret"}):
        assert client.get("/metrics", headers=headers).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer audit-metrics-secret"}).status_code == 200


@pytest.mark.parametrize("token", ["", "change-me-metrics-token", "example-metrics-token"])
def test_metrics_missing_or_example_config_stays_closed(client, monkeypatch, token):
    monkeypatch.setattr(get_settings(), "metrics_token", token)
    assert client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_every_internal_route_rejects_missing_and_wrong_tokens(client):
    routes = {path: operations for path, operations in client.app.openapi()["paths"].items() if path.startswith("/api/interview/internal/")}
    assert sum(len(set(operations) & {"get", "post", "put", "delete", "patch"}) for operations in routes.values()) >= 14
    for route, operations in routes.items():
        path = route.replace("{session_id}", "00000000-0000-0000-0000-000000000001").replace("{user_id}", "00000000-0000-0000-0000-000000000002")
        for method in set(operations) & {"get", "post", "put", "delete", "patch"}:
            for headers in ({}, {"X-PromptCode-Internal-Token": "wrong"}):
                response = client.request(method, path, headers=headers, json={})
                assert response.status_code == 404, (method, path, response.text)


@pytest.mark.parametrize("token", ["", "change-me-internal-token", "example-internal-token"])
def test_internal_example_config_stays_closed(client, monkeypatch, token):
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN", token)
    assert client.get("/api/interview/internal/disk", headers={"X-PromptCode-Internal-Token": token}).status_code == 404
