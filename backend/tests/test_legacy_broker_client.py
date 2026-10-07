"""Remote legacy work never transfers credentials or repeats paid calls."""
import json
import uuid
from types import SimpleNamespace

import httpx

from app.services.sandbox import legacy_broker_client as broker
from app.services.sandbox import runner
from app.services.sandbox.relay import RelayError


def settings():
    return SimpleNamespace(execution_broker_url="https://broker.example.com",
                           sandbox_executor_token="private-management-secret",
                           sandbox_timeout_seconds=2, openai_api_key="provider-secret",
                           openai_base_url="https://api.deepseek.com", openai_model="deepseek-flash")


def setup(monkeypatch, handler, relay_error=None):
    app_settings = settings()
    monkeypatch.setattr(runner, "settings", app_settings)
    calls = []
    class LocalRelay:
        def __init__(self, **kwargs):
            assert kwargs["api_key"] == "provider-secret"
            assert kwargs["billing_identity"] == ["user-id", "session-id"]
        def handle_request(self, payload):
            calls.append(payload)
            if relay_error:
                raise relay_error
            return {"content": "budgeted result"}
    monkeypatch.setattr(broker, "SandboxLLMRelay", LocalRelay)
    original = httpx.Client
    monkeypatch.setattr(broker.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return app_settings, calls


def execute(app_settings):
    return broker.run_legacy_broker("print('candidate')", "solution.py",
        {"_ai_billing_identity": ["user-id", "session-id"], "constraints": {"max_llm_calls": 1}},
        settings=app_settings)


def test_lost_reply_ack_does_not_repeat_paid_call(monkeypatch):
    job_id, call_id = str(uuid.uuid4()), str(uuid.uuid4())
    polls, reply_attempts = 0, 0
    def handle(request):
        nonlocal polls, reply_attempts
        assert request.headers["Authorization"] == "Bearer private-management-secret"
        assert b"provider-secret" not in request.content
        assert b"_ai_billing_identity" not in request.content
        if request.url.path == "/v1/legacy/jobs":
            policy = json.loads(request.content)["challenge_config"]["constraints"]["allowed_models"]
            assert "deepseek-flash" in policy and "gpt-4o-mini" in policy
            return httpx.Response(200, json={"id": job_id})
        if request.method == "GET":
            polls += 1
            if polls <= 2:
                return httpx.Response(200, json={"status": "running", "call": {"id": call_id,
                    "payload": {"prompt": "task question", "model": "deepseek-flash", "max_tokens": 100}}})
            return httpx.Response(200, json={"status": "complete", "result": {
                "success": True, "output": "done", "exit_code": 0, "telemetry": []}})
        reply_attempts += 1
        if reply_attempts == 1:
            raise httpx.ReadTimeout("lost acknowledgment", request=request)
        return httpx.Response(200, json={"ok": True})
    app_settings, calls = setup(monkeypatch, handle)
    result = execute(app_settings)
    assert result.success
    assert len(calls) == 1
    assert reply_attempts == 2
    assert len(result.telemetry) == 1
    assert result.telemetry[0]["prompt"] == "task question"
    assert result.telemetry[0]["response"] == "budgeted result"


def test_budget_refusal_is_returned_to_candidate_without_provider_retry(monkeypatch):
    job_id, call_id = str(uuid.uuid4()), str(uuid.uuid4())
    replied = False
    def handle(request):
        nonlocal replied
        if request.url.path == "/v1/legacy/jobs":
            return httpx.Response(200, json={"id": job_id})
        if request.method == "POST":
            assert b'429' in request.content and b'budget exhausted' in request.content
            replied = True
            return httpx.Response(200, json={"ok": True})
        if not replied:
            return httpx.Response(200, json={"status": "running", "call": {"id": call_id, "payload": {}}})
        return httpx.Response(200, json={"status": "complete", "result": {
            "success": False, "output": "", "exit_code": 1, "telemetry": [], "error": "candidate error"}})
    app_settings, calls = setup(monkeypatch, handle, RelayError(429, "budget exhausted"))
    assert not execute(app_settings).success
    assert len(calls) == 1


def test_broker_cannot_force_unbounded_distinct_llm_calls(monkeypatch):
    job_id = str(uuid.uuid4())
    canceled = []
    def handle(request):
        if request.url.path == "/v1/legacy/jobs":
            return httpx.Response(200, json={"id": job_id})
        if request.method == "DELETE":
            canceled.append(True)
            return httpx.Response(200, json={"ok": True})
        if request.method == "POST":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"status": "running", "call": {"id": str(uuid.uuid4()), "payload": {}}})
    app_settings, calls = setup(monkeypatch, handle)
    assert not execute(app_settings).success
    assert len(calls) == 1 and canceled


def test_remote_failure_does_not_expose_management_token(monkeypatch):
    app_settings, _ = setup(monkeypatch, lambda _request: httpx.Response(500, text="private-management-secret"))
    result = execute(app_settings)
    assert not result.success
    assert "private-management-secret" not in result.error


def test_broker_branch_precedes_legacy_executor(monkeypatch):
    monkeypatch.setattr(runner, "settings", settings())
    expected = object()
    monkeypatch.setattr(broker, "run_legacy_broker", lambda *args, **kwargs: expected)
    assert runner.run_in_sandbox("code", "solution.py", {}) is expected
