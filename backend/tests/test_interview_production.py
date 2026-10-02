"""Unit tests for Docker IsolatedRunner + production AI wiring (no live Docker/AI required)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.interview.ai_provider import (
    AIProviderError,
    AIRequest,
    MockAIProvider,
    ProductionAIProvider,
    assemble_user_content,
    get_ai_provider,
    validate_context_budget,
)
from app.services.interview.registry import get_runner_config, is_blocked_path
from app.services.interview.runner import (
    IsolatedRunner,
    LocalDevelopmentRunner,
    get_challenge_runner,
    normalize_runner_config,
    resolve_command,
    resolve_command_id,
    runner_mode,
)


def test_arbitrary_commands_blocked():
    with pytest.raises(ValueError):
        resolve_command("rm -rf /")
    with pytest.raises(ValueError):
        resolve_command_id("curl_evil", "npm test")


def test_resolve_command_id_uses_runner_commands_map():
    cmd = resolve_command_id(
        "run_tests",
        "npm test",
        commands_map={"run_tests": "pytest -q", "run_targeted_tests": "pytest -q", "run_benchmark": "pytest -q"},
    )
    assert cmd == "pytest -q"
    with pytest.raises(ValueError):
        resolve_command_id(
            "run_tests",
            "npm test",
            commands_map={"run_tests": "curl http://evil"},
        )


def test_normalize_runner_config_defaults_and_clamps():
    cfg = normalize_runner_config(
        {
            "stack": "Python / FastAPI",
            "test_command": "pytest -q",
            "runner": {"timeoutSeconds": 999, "memoryMb": 50, "cpuLimit": 9},
        }
    )
    assert cfg["image"] == "promptcode-runner-python:latest"
    assert cfg["timeoutSeconds"] == 120
    assert cfg["memoryMb"] == 256
    assert cfg["cpuLimit"] == 2.0
    assert cfg["network"] == "none"
    assert cfg["commands"]["run_tests"] == "pytest -q"


def test_registry_runner_config_present():
    from app.services.interview.registry import load_registry

    load_registry.cache_clear()
    cfg = get_runner_config("invoice-status-transition")
    assert cfg["image"].startswith("promptcode-runner-")
    assert "run_tests" in cfg["commands"]
    resolve_command(cfg["commands"]["run_tests"])


def test_runner_mode_prefers_promptcode_runner(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_RUNNER", "docker")
    monkeypatch.delenv("INTERVIEW_RUNNER", raising=False)
    assert runner_mode() == "docker"
    assert isinstance(get_challenge_runner(), IsolatedRunner)
    monkeypatch.setenv("PROMPTCODE_RUNNER", "local")
    assert isinstance(get_challenge_runner(), LocalDevelopmentRunner)


def test_isolated_runner_never_silent_host_fallback(tmp_path):
    ws = tmp_path / "session-a"
    ws.mkdir()
    (ws / "README.md").write_text("x", encoding="utf-8")

    with patch(
        "app.services.interview.runner._docker_client",
        side_effect=RuntimeError("no daemon"),
    ), patch(
        "app.services.interview.runner._docker_errors",
        return_value=(Exception, Exception),
    ):
        result = asyncio.run(
            IsolatedRunner().run_tests(ws, "npm test", command_id="run_tests")
        )
    assert result["runner"] == "docker"
    assert result["isolation"] == "docker"
    assert result["ok"] is False
    assert result.get("error_code") == "docker_unavailable"
    assert "fall back" in result["stderr"].lower() or "unavailable" in result["stderr"].lower()


def test_isolated_runner_container_cleanup_and_limits(tmp_path):
    ws = tmp_path / "session-b"
    ws.mkdir()
    (ws / "package.json").write_text("{}", encoding="utf-8")

    container = MagicMock()
    container.attrs = {"State": {"Running": False}}
    container.exec_run.return_value.exit_code = 1
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b"Tests  1 passed (1)\n"

    client = MagicMock()
    client.containers.run.return_value = container

    with patch(
        "app.services.interview.runner._docker_client", return_value=client
    ), patch(
        "app.services.interview.runner._docker_errors",
        return_value=(Exception, Exception),
    ):
        result = asyncio.run(
            IsolatedRunner().run_tests(
                ws,
                "npm test",
                command_id="run_tests",
                runner_config={
                    "image": "promptcode-runner-node:latest",
                    "timeoutSeconds": 45,
                    "memoryMb": 512,
                    "cpuLimit": 1.0,
                    "pidsLimit": 64,
                    "outputLimit": 20000,
                    "challengeSlug": "",
                },
            )
        )

    assert result["ok"] is False
    assert result["error_code"] == "incomplete_test_report"
    assert result["authoritative"] is False
    assert result["runner"] == "docker"
    assert result["timed_out"] is False
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["network_disabled"] is True
    assert kwargs["mem_limit"] == "512m"
    assert kwargs["pids_limit"] == 64
    assert kwargs["cap_drop"] == ["ALL"]
    assert str(ws.resolve()) in kwargs["volumes"]
    assert kwargs["volumes"][str(ws.resolve())] == {"bind": "/source", "mode": "ro"}
    container.remove.assert_called()


def test_session_workspaces_isolated(tmp_path):
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    (a / "secret.txt").write_text("session-a-only", encoding="utf-8")
    (b / "secret.txt").write_text("session-b-only", encoding="utf-8")
    assert (a / "secret.txt").read_text() != (b / "secret.txt").read_text()
    # Hidden evaluator / solution names stay blocked
    assert is_blocked_path("SOLUTION.md")
    assert is_blocked_path("nested/interviewer/notes.md")
    assert is_blocked_path("path/.reference/hidden.py")


def test_mock_ai_still_works(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "mock")
    monkeypatch.delenv("INTERVIEW_AI_PROVIDER", raising=False)
    provider = get_ai_provider()
    assert isinstance(provider, MockAIProvider)
    result = asyncio.run(
        provider.complete(messages=[{"role": "user", "content": "hi"}], system="sys")
    )
    assert result["provider"] == "mock"
    assert "mock interview" in result["content"].lower()


def test_production_ai_requires_credentials(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "production")
    monkeypatch.delenv("PROMPTCODE_AI_API_KEY", raising=False)
    monkeypatch.delenv("INTERVIEW_AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PROMPTCODE_OPENAI_API_KEY", raising=False)
    provider = get_ai_provider()
    assert isinstance(provider, ProductionAIProvider)
    with pytest.raises(AIProviderError) as exc:
        asyncio.run(
            provider.complete(messages=[{"role": "user", "content": "x"}], system="sys")
        )
    assert exc.value.code == "auth"


def test_production_ai_payload_conversion_and_hidden_never_sent(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "production")
    monkeypatch.setenv("PROMPTCODE_AI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("PROMPTCODE_AI_MODEL", "gpt-test")
    monkeypatch.setenv("PROMPTCODE_AI_BASE_URL", "https://example.test/v1")

    captured: dict = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "choices": [{"message": {"content": "ok"}}],
                "model": "gpt-test",
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            }

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResp()

    with patch("httpx.AsyncClient", FakeClient):
        provider = ProductionAIProvider()
        req = AIRequest(
            prompt="fix the bug",
            system="sys",
            attachments=[{"path": "src/a.ts", "content": " consle.log(1)"}],
            selected_text="consle",
        )
        # Ensure assemble never includes SOLUTION
        body = assemble_user_content(req)
        assert "SOLUTION" not in body
        assert "src/a.ts" in body
        result = asyncio.run(provider.complete_request(req))

    assert result.provider == "production"
    assert captured["json"]["model"] == "gpt-test"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert "Authorization" in captured["headers"]
    assert "sk-test" in captured["headers"]["Authorization"]
    # Keys must not appear in assembled user content
    assert "sk-test" not in assemble_user_content(req)


def test_context_budget_rejects_visible():
    errors = validate_context_budget(
        prompt="x" * 20_000,
        attachments=[{"path": "a.ts", "content": "y" * 200_000}],
        selected_text=None,
    )
    assert errors
    assert any("Prompt too large" in e for e in errors)


def test_provider_failure_clean(monkeypatch):
    monkeypatch.setenv("PROMPTCODE_AI_API_KEY", "sk-x")
    monkeypatch.setenv("PROMPTCODE_AI_BASE_URL", "https://example.test/v1")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.TimeoutException("slow")

    with patch("httpx.AsyncClient", FakeClient):
        with pytest.raises(AIProviderError) as exc:
            asyncio.run(
                ProductionAIProvider().complete(
                    messages=[{"role": "user", "content": "hi"}], system="sys"
                )
            )
    assert exc.value.code == "timeout"
    assert exc.value.retryable is True


@pytest.mark.skipif(
    True,  # integration: enable manually when Docker daemon + images available
    reason="Docker integration — run manually with daemon + built images",
)
def test_docker_integration_smoke():
    """Documented integration test (skipped in CI by default)."""
    from app.services.interview.runner import docker_runner_health

    report = docker_runner_health(probe_exec=True)
    assert report["docker"]["ok"] is True
