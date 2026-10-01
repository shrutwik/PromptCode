"""Interview authz: unauth + cross-user isolation for session APIs."""

from __future__ import annotations

import asyncio
import uuid

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

    db_file = tmp_path / "interview_authz.db"
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


def _signup(client: TestClient, *, email: str, username: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "username": username,
            "password": _PASSWORD,
            "first_name": "Beta",
            "last_name": "User",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_interview_unauth_and_cross_user_blocked(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            challenges = client.get("/api/interview/challenges")
            assert challenges.status_code == 200
            slug = challenges.json()[0]["slug"]

            assert (
                client.post(
                    "/api/interview/sessions", json={"challenge_slug": slug}
                ).status_code
                == 401
            )
            assert client.get("/api/interview/dashboard").status_code == 401

            a = _signup(client, email="a@example.com", username="betauser_a")
            b = _signup(client, email="b@example.com", username="betauser_b")
            ha = {"Authorization": f"Bearer {a['access_token']}"}
            hb = {"Authorization": f"Bearer {b['access_token']}"}

            start = client.post(
                "/api/interview/sessions",
                headers=ha,
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]

            # User B cannot see A's session (404 — no existence leak)
            for method, path in [
                ("get", f"/api/interview/sessions/{sid}"),
                ("get", f"/api/interview/sessions/{sid}/files"),
                ("get", f"/api/interview/sessions/{sid}/report"),
                ("post", f"/api/interview/sessions/{sid}/tests"),
                ("post", f"/api/interview/sessions/{sid}/ai/chat"),
                ("post", f"/api/interview/sessions/{sid}/submit"),
            ]:
                if method == "get":
                    r = client.get(path, headers=hb)
                else:
                    body = {"command_id": "run_tests"} if "tests" in path else (
                        {"message": "hi"} if "ai" in path else {}
                    )
                    r = client.post(path, headers=hb, json=body)
                assert r.status_code == 404, f"{method} {path}: {r.status_code} {r.text}"

            # Random UUID also 404 for A
            fake = str(uuid.uuid4())
            assert (
                client.get(f"/api/interview/sessions/{fake}", headers=ha).status_code
                == 404
            )

            # Owner can read
            assert client.get(f"/api/interview/sessions/{sid}", headers=ha).status_code == 200
            dash = client.get("/api/interview/dashboard", headers=ha)
            assert dash.status_code == 200
            assert any(s["id"] == sid for s in dash.json()["sessions"])
            dash_b = client.get("/api/interview/dashboard", headers=hb)
            assert dash_b.status_code == 200
            assert all(s["id"] != sid for s in dash_b.json()["sessions"])
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        app.dependency_overrides.clear()
        asyncio.run(test_engine.dispose())


def test_session_ttl_blocks_mutations(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.models.interview_session import InterviewSession

    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    monkeypatch.setenv("PROMPTCODE_SESSION_TTL_HOURS", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            a = _signup(client, email="ttl@example.com", username="betauser_ttl")
            ha = {"Authorization": f"Bearer {a['access_token']}"}
            slug = client.get("/api/interview/challenges").json()[0]["slug"]
            start = client.post(
                "/api/interview/sessions",
                headers=ha,
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200
            sid = start.json()["id"]

            async def _expire():
                async with test_engine.begin() as conn:
                    await conn.execute(
                        InterviewSession.__table__.update()
                        .where(InterviewSession.id == uuid.UUID(sid))
                        .values(
                            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
                        )
                    )

            asyncio.run(_expire())
            r = client.post(
                f"/api/interview/sessions/{sid}/tests",
                headers=ha,
                json={"command_id": "run_tests"},
            )
            assert r.status_code == 410
    finally:
        get_settings.cache_clear()
        app.dependency_overrides.clear()
        asyncio.run(test_engine.dispose())
