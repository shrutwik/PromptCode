"""Keep legacy paid LLM calls on the application host during remote execution."""
from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
from app.core.execution_transport import broker_tls_context, broker_json

from app.services.sandbox.relay import RelayError, SandboxLLMRelay
from app.core.model_policy import OPENAI_CHAT_MODELS


def run_legacy_broker(code: str, entrypoint: str, challenge_config: dict[str, Any], *,
                      settings, run_id: str | None = None,
                      input_overrides: dict[str, Any] | None = None):
    from app.services.sandbox.runner import SandboxResult, _build_sandbox_llm_budget, _is_safe_entrypoint
    telemetry = []

    def failed(message):
        return SandboxResult(success=False, output="", exit_code=-1, telemetry=list(telemetry), error=message)

    if not _is_safe_entrypoint(entrypoint):
        return failed("Unsafe entrypoint path")
    budget = _build_sandbox_llm_budget(challenge_config)
    # This object never listens on a network port: only its local budgeted handler is used.
    relay = SandboxLLMRelay(api_key=settings.openai_api_key, base_url=settings.openai_base_url,
                            host_alias="localhost", budget=budget, default_model=settings.openai_model,
                            billing_identity=challenge_config.get("_ai_billing_identity"))
    broker_config = {k: v for k, v in challenge_config.items() if k != "_ai_billing_identity"}
    constraints = dict(broker_config.get("constraints") or {})
    allowed_models = list(budget.allowed_models)
    if settings.openai_base_url.rstrip("/") == "https://api.deepseek.com":
        # Legacy SDK callers may use an OpenAI alias; the app relay still maps
        # every permitted alias to the pinned DeepSeek model before any payment.
        allowed_models += list(OPENAI_CHAT_MODELS)
    constraints["allowed_models"] = allowed_models
    broker_config["constraints"] = constraints
    payload = {"code": code, "entrypoint": entrypoint,
               "challenge_config": broker_config,
               "run_id": run_id or uuid.uuid4().hex[:12], "input_overrides": input_overrides or {}}
    base = settings.execution_broker_url.rstrip("/")
    headers = {"Authorization": "Bearer " + settings.sandbox_executor_token}
    deadline = time.monotonic() + max(1, settings.sandbox_timeout_seconds) + 30
    job_id = None
    replies: dict[str, dict] = {}
    complete = False
    with httpx.Client(timeout=10, headers=headers, trust_env=False, verify=broker_tls_context(settings)) as client:
        try:
            state = broker_json(client, "POST", base + "/v1/legacy/jobs", json=payload, max_bytes=4096)
            job_id = str(uuid.UUID(state["id"]))
            endpoint = base + "/v1/legacy/jobs/" + job_id
            while time.monotonic() < deadline:
                state = broker_json(client, "GET", endpoint, max_bytes=2 * 1024 * 1024)
                if state.get("status") == "complete":
                    result = SandboxResult.from_dict(state["result"])
                    # The execution host cannot forge paid-call accounting.
                    result.telemetry = telemetry
                    complete = True
                    return result
                if state.get("status") != "running":
                    return failed("Execution broker returned an invalid job state.")
                call = state.get("call")
                if call is None:
                    time.sleep(.1)
                    continue
                call_id = str(uuid.UUID(call["id"]))
                if call_id not in replies:
                    if len(replies) >= budget.max_calls:
                        return failed("Execution broker exceeded the bounded LLM request allowance.")
                    try:
                        paid_result = relay.handle_request(call["payload"])
                        usage = paid_result.get("usage") or {}
                        request_payload = call["payload"]
                        telemetry.append({"call_id": call_id, "model": paid_result.get("model", settings.openai_model),
                            "prompt": str(request_payload.get("prompt", "")), "system": str(request_payload.get("system", "")),
                            "response": str(paid_result.get("content", "")), "temperature": request_payload.get("temperature", 0),
                            "tokens_prompt": int(usage.get("prompt_tokens", 0)),
                            "tokens_completion": int(usage.get("completion_tokens", 0)),
                            "tokens_total": int(usage.get("total_tokens", 0)),
                            "latency_ms": paid_result.get("latency_ms", 0),
                            "cost_usd": paid_result.get("cost_usd", 0), "retry_index": 0})
                        reply = {"id": call_id, "result": paid_result, "error": None}
                    except RelayError as exc:
                        reply = {"id": call_id, "result": None,
                                 "error": {"status_code": int(exc.status_code), "detail": exc.detail}}
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        reply = {"id": call_id, "result": None,
                                 "error": {"status_code": 502, "detail": "Application LLM relay unavailable."}}
                    replies[call_id] = reply
                # Cache the response before transport: a lost acknowledgment must not
                # repeat a paid provider call. The broker accepts repeated reply IDs.
                try:
                    broker_json(client, "POST", endpoint + "/reply", json=replies[call_id], max_bytes=4096)
                except (httpx.TimeoutException, httpx.NetworkError):
                    time.sleep(.1)
            return failed("Remote sandbox execution timed out.")
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return failed("Execution broker unavailable or returned an invalid response.")
        finally:
            if job_id and not complete:
                try:
                    broker_json(client, "DELETE", base + "/v1/legacy/jobs/" + job_id, max_bytes=4096)
                except (httpx.HTTPError, ValueError, TypeError):
                    pass  # Broker wall-time expiry also reaps abandoned work.
