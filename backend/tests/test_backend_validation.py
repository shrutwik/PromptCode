from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.requests import Request

import app.models  # noqa: F401 - ensure ORM models are registered
from app.api.routes import auth as auth_routes
from app.api.routes.chat import ChatMessage, _validate_messages
from app.api.routes.submissions import _is_safe_python_entrypoint
from app.core.config import get_settings
from app.db.base import Base
from app.schemas.user import UserCreate
from app.services.sandbox.runner import _is_safe_entrypoint


def test_entrypoint_validation_accepts_simple_python_file():
    assert _is_safe_python_entrypoint("main.py") is True
    assert _is_safe_entrypoint("main.py") is True


def test_entrypoint_validation_rejects_path_tricks_and_non_python():
    bad = [
        "../main.py",
        "/tmp/main.py",
        "folder/main.py",
        "main.py;rm -rf /",
        "main.sh",
        "",
    ]
    for value in bad:
        assert _is_safe_python_entrypoint(value) is False
        assert _is_safe_entrypoint(value) is False


def test_validate_messages_rejects_invalid_payloads():
    with pytest.raises(HTTPException) as excinfo:
        _validate_messages([])
    assert getattr(excinfo.value, "status_code", None) == 400

    with pytest.raises(HTTPException) as excinfo:
        _validate_messages([ChatMessage(role="hacker", content="hello")])
    assert getattr(excinfo.value, "status_code", None) == 400

    with pytest.raises(HTTPException) as excinfo:
        _validate_messages([ChatMessage(role="user", content="   ")])
    assert getattr(excinfo.value, "status_code", None) == 400


def _build_rate_limit_db(tmp_path) -> tuple[async_sessionmaker[AsyncSession], object]:
    db_file = tmp_path / "rate_limit.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    return session_factory, engine


def test_auth_rate_limit_is_shared_across_sessions(tmp_path, monkeypatch):
    get_settings.cache_clear()
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
            "client": ("127.0.0.1", 1234),
        }
    )
    session_factory, engine = _build_rate_limit_db(tmp_path)

    async def exercise_limit():
        started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        for _ in range(auth_routes._AUTH_RATE_LIMIT):
            async with session_factory() as db:
                await auth_routes._check_auth_rate_limit(request, db=db, now=started_at)

        with pytest.raises(HTTPException) as excinfo:
            async with session_factory() as db:
                await auth_routes._check_auth_rate_limit(request, db=db, now=started_at)

        assert getattr(excinfo.value, "status_code", None) == 429
        assert excinfo.value.headers == {"Retry-After": str(auth_routes._AUTH_RATE_WINDOW)}

    asyncio.run(exercise_limit())
    asyncio.run(engine.dispose())
    assert auth_routes._auth_client_key(request) == "203.0.113.10"
    get_settings.cache_clear()


def test_auth_rate_limit_allows_requests_after_window(tmp_path):
    request = Request(
        {
            "type": "http",
            "headers": [],
            "client": ("198.51.100.25", 1234),
        }
    )
    session_factory, engine = _build_rate_limit_db(tmp_path)

    async def exercise_window() -> None:
        started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        for attempt in range(auth_routes._AUTH_RATE_LIMIT):
            async with session_factory() as db:
                await auth_routes._check_auth_rate_limit(
                    request,
                    db=db,
                    now=started_at + timedelta(seconds=attempt),
                )

        with pytest.raises(HTTPException):
            async with session_factory() as db:
                await auth_routes._check_auth_rate_limit(
                    request,
                    db=db,
                    now=started_at + timedelta(seconds=auth_routes._AUTH_RATE_LIMIT),
                )

        async with session_factory() as db:
            await auth_routes._check_auth_rate_limit(
                request,
                db=db,
                now=started_at
                + timedelta(seconds=auth_routes._AUTH_RATE_WINDOW + auth_routes._AUTH_RATE_LIMIT),
            )

    asyncio.run(exercise_window())
    asyncio.run(engine.dispose())


def test_auth_client_key_ignores_forwarded_headers_from_untrusted_peer(monkeypatch):
    monkeypatch.delenv("PROMPTCODE_AUTH_TRUSTED_PROXY_CIDRS", raising=False)
    get_settings.cache_clear()

    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.10"), (b"x-real-ip", b"203.0.113.10")],
            "client": ("198.51.100.25", 1234),
        }
    )

    assert auth_routes._auth_client_key(request) == "198.51.100.25"
    get_settings.cache_clear()


def test_auth_client_key_trusts_configured_docker_proxy_cidr(monkeypatch):
    monkeypatch.setenv(
        "PROMPTCODE_AUTH_TRUSTED_PROXY_CIDRS",
        '["127.0.0.1/32","::1/128","172.16.0.0/12"]',
    )
    get_settings.cache_clear()

    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.10, 172.20.0.10")],
            "client": ("172.20.0.8", 1234),
        }
    )

    assert auth_routes._auth_client_key(request) == "203.0.113.10"
    get_settings.cache_clear()


def test_user_create_rejects_weak_passwords():
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(
            email="user@example.com",
            username="builder01",
            password="password1234",
        )

    assert "Password must include an uppercase letter." in str(excinfo.value)


def test_user_create_rejects_invalid_username():
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(
            email="user@example.com",
            username="bad name!",
            password="Password123!",
        )

    assert "Username must be 3-64 characters" in str(excinfo.value)
