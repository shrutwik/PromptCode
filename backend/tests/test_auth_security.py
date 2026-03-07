from __future__ import annotations

import asyncio
import uuid

import app.models  # noqa: F401 — registers all models with Base.metadata
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token, decode_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.schemas.user import UserCreate

_SECRET = "test-only-secret-not-used-in-prod"
_VALID_PASSWORD = "Str0ng!P@ssw0rd"
_VALID_USERNAME = "testuser01"


# ── JWT (authlib) ─────────────────────────────────────────────────────────────


def test_jwt_round_trip():
    uid = uuid.uuid4()
    token = create_access_token(uid, _SECRET)
    assert isinstance(token, str)
    assert decode_access_token(token, _SECRET) == uid


def test_jwt_wrong_secret_returns_none():
    uid = uuid.uuid4()
    token = create_access_token(uid, _SECRET)
    assert decode_access_token(token, "wrong-secret") is None


def test_jwt_bad_token_returns_none():
    assert decode_access_token("not.a.valid.token", _SECRET) is None


def test_jwt_tampered_token_returns_none():
    uid = uuid.uuid4()
    token = create_access_token(uid, _SECRET)
    parts = token.split(".")
    parts[1] = parts[1][::-1]  # corrupt payload
    assert decode_access_token(".".join(parts), _SECRET) is None


# ── UserCreate password validation ───────────────────────────────────────────


def test_password_too_short_rejected():
    with pytest.raises(ValidationError, match="12 characters"):
        UserCreate(email="a@b.com", username=_VALID_USERNAME, password="Sh0rt!")


def test_password_no_uppercase_rejected():
    with pytest.raises(ValidationError, match="uppercase"):
        UserCreate(email="a@b.com", username=_VALID_USERNAME, password="allowercase1!")


def test_password_no_lowercase_rejected():
    with pytest.raises(ValidationError, match="lowercase"):
        UserCreate(email="a@b.com", username=_VALID_USERNAME, password="ALLUPPERCASE1!")


def test_password_no_digit_rejected():
    with pytest.raises(ValidationError, match="number"):
        UserCreate(email="a@b.com", username=_VALID_USERNAME, password="NoDigitsHere!")


def test_password_no_symbol_rejected():
    with pytest.raises(ValidationError, match="symbol"):
        UserCreate(email="a@b.com", username=_VALID_USERNAME, password="NoSymbolsHere1")


def test_valid_password_accepted():
    u = UserCreate(email="a@b.com", username=_VALID_USERNAME, password=_VALID_PASSWORD)
    assert u.password == _VALID_PASSWORD


# ── UserCreate username validation ───────────────────────────────────────────


def test_username_too_short_rejected():
    with pytest.raises(ValidationError, match="3-64"):
        UserCreate(email="a@b.com", username="ab", password=_VALID_PASSWORD)


def test_username_invalid_chars_rejected():
    with pytest.raises(ValidationError, match="3-64"):
        UserCreate(email="a@b.com", username="bad user!", password=_VALID_PASSWORD)


def test_username_starts_with_underscore_rejected():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", username="_badstart1", password=_VALID_PASSWORD)


def test_valid_username_with_hyphen_and_underscore():
    u = UserCreate(email="a@b.com", username="valid-user_99", password=_VALID_PASSWORD)
    assert u.username == "valid-user_99"


# ── Auth rate limiting ────────────────────────────────────────────────────────


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    db_file = tmp_path / "auth_test.db"
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


def test_auth_rate_limit_blocks_on_eleventh_attempt(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # First 10 attempts: wrong creds → 401
        for i in range(10):
            r = client.post(
                "/api/auth/login",
                json={"email": f"x{i}@example.com", "password": "Wr0ng!Passw0rd"},
            )
            assert r.status_code == 401, f"attempt {i + 1}: expected 401, got {r.status_code}"

        # 11th attempt: rate limited → 429
        r = client.post(
            "/api/auth/login",
            json={"email": "x@example.com", "password": "Wr0ng!Passw0rd"},
        )
        assert r.status_code == 429
        assert "Retry-After" in r.headers

    from app.core.config import get_settings
    get_settings.cache_clear()
    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())


def test_signup_rate_limit_blocks_on_eleventh_attempt(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)

    with TestClient(app) as client:
        # 10 signup attempts with duplicate email → 409 (rate limit passes, conflict raised)
        for i in range(10):
            client.post(
                "/api/auth/signup",
                json={
                    "email": f"rl{i}@example.com",
                    "username": f"rluser{i:02d}",
                    "password": _VALID_PASSWORD,
                },
            )

        # 11th → 429
        r = client.post(
            "/api/auth/signup",
            json={
                "email": "rl99@example.com",
                "username": "rluser99",
                "password": _VALID_PASSWORD,
            },
        )
        assert r.status_code == 429

    from app.core.config import get_settings
    get_settings.cache_clear()
    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())
