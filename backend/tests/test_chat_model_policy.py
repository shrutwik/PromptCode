from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.chat import _resolve_requested_model
from app.core.model_policy import OPENAI_CHAT_MODELS, resolve_allowed_model


def test_model_policy_keeps_legacy_supported_models():
    assert "gpt-4-turbo" in OPENAI_CHAT_MODELS
    assert "gpt-3.5-turbo" in OPENAI_CHAT_MODELS
    assert resolve_allowed_model("gpt-4-turbo", OPENAI_CHAT_MODELS) == "gpt-4-turbo"
    assert resolve_allowed_model("openai/gpt-3.5-turbo", OPENAI_CHAT_MODELS) == "gpt-3.5-turbo"
    assert resolve_allowed_model("protected.gpt-4o", OPENAI_CHAT_MODELS) == "gpt-4o"


def test_resolve_requested_model_accepts_supported_aliases():
    settings = SimpleNamespace(openai_model="gpt-4o")
    raw_model, canonical_model = _resolve_requested_model("openai:gpt-4-turbo", settings)
    assert raw_model == "openai:gpt-4-turbo"
    assert canonical_model == "gpt-4-turbo"


def test_resolve_requested_model_rejects_unknown_models():
    settings = SimpleNamespace(openai_model="gpt-4o")
    with pytest.raises(HTTPException) as excinfo:
        _resolve_requested_model("claude-3-5-sonnet", settings)
    assert excinfo.value.status_code == 400
