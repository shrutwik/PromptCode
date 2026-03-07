from __future__ import annotations

import asyncio
import json
import logging

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app import main as main_module
from app.core.config import get_settings
from app.core.logging import JsonFormatter


def test_json_formatter_emits_structured_fields():
    formatter = JsonFormatter()
    record = logging.makeLogRecord(
        {
            "name": "promptcode.test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "worker.started",
            "worker_id": "worker-a",
        }
    )

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "worker.started"
    assert payload["logger"] == "promptcode.test"
    assert payload["level"] == "INFO"
    assert payload["worker_id"] == "worker-a"
    assert "timestamp" in payload


def test_access_log_middleware_records_request(caplog, monkeypatch):
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(main_module, "engine", async_engine)
    get_settings.cache_clear()

    app = main_module.create_app()

    with caplog.at_level(logging.INFO, logger="app.access"):
        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    record = next(record for record in caplog.records if record.name == "app.access")
    assert record.getMessage() == "request.complete"
    assert record.method == "GET"
    assert record.path == "/health"
    assert record.status_code == 200

    get_settings.cache_clear()
    asyncio.run(async_engine.dispose())
