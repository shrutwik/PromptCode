"""Protected session files stay read-only and say so."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

_PASSWORD = "Str0ng!P@ssw0rd"


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    get_settings.cache_clear()

    db_file = tmp_path / "readonly.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _create_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return app, test_engine


def test_protected_files_are_listed_read_only_and_reject_writes(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            signup = client.post(
                "/api/auth/signup",
                json={
                    "email": "readonly@example.com",
                    "username": "readonlyuser",
                    "password": _PASSWORD,
                    "first_name": "Read",
                    "last_name": "Only",
                },
            )
            assert signup.status_code == 201, signup.text
            headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
            start = client.post(
                "/api/interview/sessions",
                headers=headers,
                json={"challenge_slug": "order-hold-reason"},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]
            listed = client.get(f"/api/interview/sessions/{sid}/files", headers=headers)
            assert listed.status_code == 200, listed.text
            by_path = {item["path"]: item for item in listed.json()}
            assert by_path["app/service.py"]["writable"] is True
            assert by_path["tests/test_orders.py"]["writable"] is False
            assert by_path["pytest.ini"]["writable"] is False
            assert by_path["requirements.txt"]["writable"] is False

            denied = client.put(
                f"/api/interview/sessions/{sid}/files/tests/test_orders.py",
                headers=headers,
                json={"content": "def test_hacked():\n    assert False\n", "source": "candidate"},
            )
            assert denied.status_code == 403, denied.text
            assert denied.json()["detail"] == "This file is read-only."

            original = client.get(
                f"/api/interview/sessions/{sid}/files/tests/test_orders.py",
                headers=headers,
            )
            assert original.status_code == 200
            assert "test_hacked" not in original.json()["content"]

            applied = client.post(
                f"/api/interview/sessions/{sid}/ai/apply",
                headers=headers,
                json={
                    "path": "pytest.ini",
                    "content": "[pytest]\naddopts = -q\n",
                    "disposition": "accepted",
                    "base_revision": 0,
                },
            )
            assert applied.status_code == 403, applied.text
            assert applied.json()["detail"] == "This file is read-only."
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        app.dependency_overrides.clear()
        asyncio.run(test_engine.dispose())
