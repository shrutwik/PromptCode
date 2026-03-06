from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.sandbox.relay import RelayError, SandboxLLMBudget, SandboxLLMRelay
from app.services.sandbox.runner import (
    _build_container_environment,
    _build_sandbox_llm_budget,
    _sandbox_temp_root,
)


def _fake_sender(payload):
    return (
        {
            "id": "cmpl_test",
            "model": payload["model"],
            "choices": [{"message": {"content": "relay-ok"}}],
            "usage": {
                "prompt_tokens": 24,
                "completion_tokens": 12,
                "total_tokens": 36,
            },
        },
        12.5,
    )


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_build_sandbox_budget_prefers_challenge_constraints():
    budget = _build_sandbox_llm_budget(
        {
            "expected_calls": 3,
            "token_budget": 9000,
            "cost_budget_usd": 0.15,
            "constraints": {
                "allowed_models": ["gpt-4o-mini"],
                "max_llm_calls": 7,
            },
        }
    )

    assert budget.allowed_models == ("gpt-4o-mini",)
    assert budget.max_calls == 7
    assert budget.max_total_tokens == 9000
    assert budget.max_total_cost_usd == 0.15


def test_container_environment_uses_proxy_instead_of_openai_key():
    budget = SandboxLLMBudget(
        allowed_models=("gpt-4o-mini",),
        max_calls=4,
        max_prompt_chars=10_000,
        max_completion_tokens=1024,
        max_total_tokens=5000,
        max_total_cost_usd=0.10,
    )
    relay = SimpleNamespace(
        proxy_url="http://host.docker.internal:41237/v1/llm/call",
        token="relay-token",
    )
    env = _build_container_environment(relay=relay, budget=budget)

    assert "OPENAI_API_KEY" not in env
    assert env["PROMPTCODE_LLM_PROXY_URL"] == "http://host.docker.internal:41237/v1/llm/call"
    assert env["PROMPTCODE_LLM_PROXY_TOKEN"] == "relay-token"
    assert env["PROMPTCODE_ALLOWED_MODELS"] == "gpt-4o-mini"


def test_sandbox_llm_relay_enforces_model_and_call_limits():
    budget = SandboxLLMBudget(
        allowed_models=("gpt-4o-mini",),
        max_calls=1,
        max_prompt_chars=10_000,
        max_completion_tokens=1024,
        max_total_tokens=5000,
        max_total_cost_usd=0.10,
    )
    relay = SandboxLLMRelay(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        host_alias="host.docker.internal",
        budget=budget,
        request_sender=_fake_sender,
    )
    response = relay.handle_request(
        {
            "model": "gpt-4o-mini",
            "prompt": "Hello from the relay",
            "max_tokens": 200,
        }
    )
    assert response["content"] == "relay-ok"
    assert response["usage"]["total_tokens"] == 36

    with pytest.raises(RelayError) as disallowed:
        relay.handle_request(
            {
                "model": "gpt-4o",
                "prompt": "Disallowed model",
                "max_tokens": 50,
            }
        )
    assert disallowed.value.status_code == 400

    with pytest.raises(RelayError) as over_budget:
        relay.handle_request(
            {
                "model": "gpt-4o-mini",
                "prompt": "Second call should exceed budget",
                "max_tokens": 50,
            }
        )
    assert over_budget.value.status_code == 429


def test_sdk_uses_sandbox_proxy_without_openai_key(monkeypatch, tmp_path):
    sdk_root = Path(__file__).resolve().parents[2] / "sdk"
    monkeypatch.syspath_prepend(str(sdk_root))
    monkeypatch.setenv("PROMPTCODE_TELEMETRY_DIR", str(tmp_path))
    monkeypatch.setenv("PROMPTCODE_ALLOWED_MODELS", "gpt-4o-mini")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    budget = SandboxLLMBudget(
        allowed_models=("gpt-4o-mini",),
        max_calls=2,
        max_prompt_chars=10_000,
        max_completion_tokens=1024,
        max_total_tokens=5000,
        max_total_cost_usd=0.10,
    )
    relay = SandboxLLMRelay(
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        host_alias="host.docker.internal",
        budget=budget,
        request_sender=_fake_sender,
    )
    monkeypatch.setenv("PROMPTCODE_LLM_PROXY_URL", "http://sandbox-relay.test/v1/llm/call")
    monkeypatch.setenv("PROMPTCODE_LLM_PROXY_TOKEN", relay.token)
    captured_request: dict[str, object] = {}

    def _fake_urlopen(request, timeout=0):
        captured_request["url"] = request.full_url
        captured_request["auth"] = request.get_header("Authorization")
        captured_request["body"] = json.loads(request.data.decode("utf-8"))
        response = relay.handle_request(captured_request["body"])
        return _FakeHTTPResponse(response)

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        client_module = importlib.import_module("promptcode.client")
        client_module = importlib.reload(client_module)

        result = client_module.llm.call(
            model="gpt-4o-mini",
            prompt="Return a short answer",
            max_tokens=100,
        )

    assert result == "relay-ok"
    assert captured_request["url"] == "http://sandbox-relay.test/v1/llm/call"
    assert captured_request["auth"] == f"Bearer {relay.token}"
    telemetry_lines = (tmp_path / "calls.jsonl").read_text().strip().splitlines()
    assert len(telemetry_lines) == 1
    record = json.loads(telemetry_lines[0])
    assert record["model"] == "gpt-4o-mini"
    assert record["response"] == "relay-ok"


def test_sandbox_temp_root_uses_configured_shared_directory(monkeypatch, tmp_path):
    shared_root = tmp_path / "sandbox-shared"
    monkeypatch.setenv("PROMPTCODE_SANDBOX_HOST_WORKDIR", str(shared_root))

    resolved = _sandbox_temp_root()

    assert resolved == shared_root
    assert shared_root.exists()
