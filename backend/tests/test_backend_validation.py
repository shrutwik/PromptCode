from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api.routes import auth as auth_routes
from app.api.routes.chat import ChatMessage, _validate_messages
from app.api.routes.submissions import _is_safe_python_entrypoint
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


def test_auth_rate_limit_uses_forwarded_ip_and_sets_retry_after():
    auth_routes._AUTH_RATE_BUCKETS.clear()
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
            "client": ("127.0.0.1", 1234),
        }
    )

    async def exercise_limit():
        for _ in range(auth_routes._AUTH_RATE_LIMIT):
            await auth_routes._check_auth_rate_limit(request)

        with pytest.raises(HTTPException) as excinfo:
            await auth_routes._check_auth_rate_limit(request)

        assert getattr(excinfo.value, "status_code", None) == 429
        assert excinfo.value.headers == {
            "Retry-After": str(auth_routes._AUTH_RATE_WINDOW)
        }

    asyncio.run(exercise_limit())
    assert auth_routes._auth_client_key(request) == "203.0.113.10"


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
