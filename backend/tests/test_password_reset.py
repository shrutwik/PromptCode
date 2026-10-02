from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — registers models, including PasswordResetToken
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.password_reset import PasswordResetToken
from app.services.password_reset import FORGOT_PASSWORD_MESSAGE

_VALID_PASSWORD = "Str0ng!P@ssw0rd"
_NEW_PASSWORD = "N3w!Reset#Pass"


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.db import session as session_module

    db_file = tmp_path / "password_reset_test.db"
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
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return app, test_engine


def _cleanup(app, test_engine) -> None:
    get_settings.cache_clear()
    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())


def _capture_tokens(monkeypatch) -> dict[str, str]:
    captured: dict[str, str] = {}

    async def _capture(email: str, raw_token: str) -> None:
        captured["email"] = email
        captured["token"] = raw_token

    monkeypatch.setattr("app.api.routes.auth.notify_password_reset", _capture)
    return captured


def _signup(client: TestClient, *, email: str, username: str) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"email": email, "username": username, "password": _VALID_PASSWORD},
    )
    assert response.status_code == 201, response.text


def test_forgot_password_unknown_email_returns_same_message(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    get_settings().debug = False
    try:
        with TestClient(app) as client:
            unknown = client.post(
                "/api/auth/forgot-password",
                json={"email": "missing@example.com"},
            )
            _signup(client, email="known-reset@example.com", username="knownreset01")
            known = client.post(
                "/api/auth/forgot-password",
                json={"email": "known-reset@example.com"},
            )

        assert unknown.status_code == 200
        assert known.status_code == 200
        assert unknown.json() == {"message": FORGOT_PASSWORD_MESSAGE}
        assert known.json() == {"message": FORGOT_PASSWORD_MESSAGE}
        assert "reset_token" not in unknown.json()
        assert "reset_token" not in known.json()
    finally:
        _cleanup(app, test_engine)


def test_debug_response_never_includes_reset_token(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    captured = _capture_tokens(monkeypatch)
    get_settings().debug = True
    try:
        with TestClient(app) as client:
            _signup(client, email="debug-reset@example.com", username="debugreset01")
            known = client.post(
                "/api/auth/forgot-password",
                json={"email": "debug-reset@example.com"},
            )
            unknown = client.post(
                "/api/auth/forgot-password",
                json={"email": "still-missing@example.com"},
            )

        assert known.status_code == 200
        assert known.json() == {"message": FORGOT_PASSWORD_MESSAGE}
        assert "reset_token" not in known.json()
        assert captured["token"]
        assert unknown.status_code == 200
        assert unknown.json() == {"message": FORGOT_PASSWORD_MESSAGE}
    finally:
        _cleanup(app, test_engine)


def test_reset_password_changes_password_and_rejects_reuse(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    captured = _capture_tokens(monkeypatch)
    get_settings().debug = False
    email = "reuse-reset@example.com"
    try:
        with TestClient(app) as client:
            _signup(client, email=email, username="reusereset01")
            forgot = client.post("/api/auth/forgot-password", json={"email": email})
            assert forgot.status_code == 200
            assert forgot.json() == {"message": FORGOT_PASSWORD_MESSAGE}
            token = captured["token"]

            updated = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": _NEW_PASSWORD},
            )
            assert updated.status_code == 200
            assert updated.json()["message"] == "Password updated."

            old_login = client.post(
                "/api/auth/login",
                json={"email": email, "password": _VALID_PASSWORD},
            )
            assert old_login.status_code == 401

            new_login = client.post(
                "/api/auth/login",
                json={"email": email, "password": _NEW_PASSWORD},
            )
            assert new_login.status_code == 200
            assert new_login.json()["user"]["email"] == email

            reused = client.post(
                "/api/auth/reset-password",
                json={"token": token, "new_password": "An0ther!Passw0rd"},
            )
            assert reused.status_code == 400
    finally:
        _cleanup(app, test_engine)


def test_reset_password_rejects_expired_and_bad_tokens(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    captured = _capture_tokens(monkeypatch)
    get_settings().debug = False
    email = "expired-reset@example.com"
    try:
        with TestClient(app) as client:
            _signup(client, email=email, username="expiredreset1")
            forgot = client.post("/api/auth/forgot-password", json={"email": email})
            assert forgot.status_code == 200
            assert captured["token"]

            async def _expire() -> None:
                from app.db import session as session_module

                async with session_module.async_session_factory() as session:
                    rows = (await session.execute(select(PasswordResetToken))).scalars().all()
                    assert rows
                    for row in rows:
                        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
                    await session.commit()

            asyncio.run(_expire())

            expired = client.post(
                "/api/auth/reset-password",
                json={"token": captured["token"], "new_password": _NEW_PASSWORD},
            )
            bad = client.post(
                "/api/auth/reset-password",
                json={"token": "not-a-real-reset-token", "new_password": _NEW_PASSWORD},
            )
            login = client.post(
                "/api/auth/login",
                json={"email": email, "password": _VALID_PASSWORD},
            )

        assert expired.status_code == 400
        assert bad.status_code == 400
        assert login.status_code == 200
    finally:
        _cleanup(app, test_engine)


def test_stored_reset_token_is_a_hash(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    captured = _capture_tokens(monkeypatch)
    try:
        with TestClient(app) as client:
            _signup(client, email="hash-reset@example.com", username="hashreset001")
            response = client.post(
                "/api/auth/forgot-password",
                json={"email": "hash-reset@example.com"},
            )
            assert response.status_code == 200

            async def _load_hash() -> str:
                from app.db import session as session_module

                async with session_module.async_session_factory() as session:
                    row = (
                        await session.execute(select(PasswordResetToken))
                    ).scalar_one()
                    return row.token_hash

            stored = asyncio.run(_load_hash())
        assert stored == hashlib.sha256(captured["token"].encode()).hexdigest()
        assert stored != captured["token"]
    finally:
        _cleanup(app, test_engine)


def test_notify_password_reset_does_not_log_the_token(caplog, monkeypatch):
    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    get_settings.cache_clear()
    from app.services.password_reset import notify_password_reset

    caplog.set_level(logging.INFO, logger="app.services.password_reset")
    asyncio.run(notify_password_reset("person@example.com", "raw-reset-token-value"))
    assert "raw-reset-token-value" not in caplog.text
    assert "person@example.com" in caplog.text
    get_settings.cache_clear()
