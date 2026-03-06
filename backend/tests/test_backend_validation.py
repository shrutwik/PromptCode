from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes.chat import ChatMessage, _validate_messages
from app.api.routes.submissions import _is_safe_python_entrypoint
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
