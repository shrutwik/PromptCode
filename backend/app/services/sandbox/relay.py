from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

import httpx

from app.core.model_policy import OPENAI_CHAT_MODELS, resolve_allowed_model

logger = logging.getLogger(__name__)

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
    "gpt-4-turbo": (10.00 / 1_000_000, 30.00 / 1_000_000),
    "gpt-3.5-turbo": (0.50 / 1_000_000, 1.50 / 1_000_000),
}
_DEFAULT_PRICING = (5.00 / 1_000_000, 15.00 / 1_000_000)
_DEFAULT_TIMEOUT_SECONDS = 60.0

RequestSender = Callable[[dict[str, Any]], tuple[dict[str, Any], float]]


@dataclass(frozen=True)
class SandboxLLMBudget:
    allowed_models: tuple[str, ...]
    max_calls: int
    max_prompt_chars: int
    max_completion_tokens: int
    max_total_tokens: int
    max_total_cost_usd: float


class RelayError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class SandboxLLMRelay:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        host_alias: str,
        budget: SandboxLLMBudget,
        request_sender: RequestSender | None = None,
    ):
        self._api_key = api_key
        self._base_url = str(base_url or "https://api.openai.com/v1").rstrip("/")
        self._host_alias = host_alias
        self._budget = budget
        self._request_sender = request_sender or self._send_upstream_request
        self._token = uuid.uuid4().hex
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._calls_started = 0
        self._total_tokens = 0
        self._total_cost_usd = 0.0

    @property
    def token(self) -> str:
        return self._token

    @property
    def proxy_url(self) -> str:
        return f"http://{self._host_alias}:{self.port}/v1/llm/call"

    @property
    def local_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1/llm/call"

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("Sandbox relay is not running")
        return int(self._server.server_address[1])

    def __enter__(self) -> SandboxLLMRelay:
        server = ThreadingHTTPServer(("0.0.0.0", 0), self._build_handler())
        server.daemon_threads = True
        server.relay = self  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="sandbox-llm-relay",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        relay = self

        class RelayHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/v1/llm/call":
                    self._write_error(HTTPStatus.NOT_FOUND, "Unknown sandbox relay path.")
                    return

                auth_header = str(self.headers.get("Authorization") or "")
                if auth_header != f"Bearer {relay.token}":
                    self._write_error(HTTPStatus.UNAUTHORIZED, "Invalid sandbox relay token.")
                    return

                try:
                    content_length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    self._write_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header.")
                    return

                try:
                    payload = json.loads(self.rfile.read(content_length) or b"{}")
                except json.JSONDecodeError:
                    self._write_error(HTTPStatus.BAD_REQUEST, "Malformed JSON body.")
                    return

                try:
                    response = relay.handle_request(payload)
                except RelayError as exc:
                    self._write_error(exc.status_code, exc.detail)
                    return
                except Exception:
                    logger.exception("Sandbox relay failed")
                    self._write_error(HTTPStatus.BAD_GATEWAY, "Sandbox relay upstream failure.")
                    return

                body = json.dumps(response).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def _write_error(self, status_code: int, detail: str) -> None:
                payload = json.dumps({"detail": detail}).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        return RelayHandler

    def handle_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = _validate_model(str(payload.get("model") or ""), self._budget.allowed_models)
        prompt = str(payload.get("prompt") or "")
        system = str(payload.get("system") or "")
        if not prompt.strip():
            raise RelayError(HTTPStatus.BAD_REQUEST, "Prompt cannot be empty.")
        if len(prompt) + len(system) > self._budget.max_prompt_chars:
            raise RelayError(
                HTTPStatus.BAD_REQUEST,
                f"Prompt too large for sandbox relay (>{self._budget.max_prompt_chars} chars).",
            )

        requested_max_tokens = int(payload.get("max_tokens") or 0)
        if requested_max_tokens <= 0:
            raise RelayError(HTTPStatus.BAD_REQUEST, "max_tokens must be a positive integer.")
        max_tokens = min(requested_max_tokens, self._budget.max_completion_tokens)
        temperature = max(0.0, min(float(payload.get("temperature") or 0.0), 2.0))

        with self._lock:
            if self._calls_started >= self._budget.max_calls:
                raise RelayError(HTTPStatus.TOO_MANY_REQUESTS, "Sandbox LLM call budget exhausted.")
            if self._total_tokens >= self._budget.max_total_tokens:
                raise RelayError(HTTPStatus.TOO_MANY_REQUESTS, "Sandbox token budget exhausted.")
            if self._total_cost_usd >= self._budget.max_total_cost_usd:
                raise RelayError(HTTPStatus.TOO_MANY_REQUESTS, "Sandbox cost budget exhausted.")
            self._calls_started += 1

        upstream_payload = {
            "model": model,
            "messages": _build_messages(system=system, prompt=prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        data, latency_ms = self._request_sender(upstream_payload)
        content, response_model, prompt_tokens, completion_tokens, total_tokens = _parse_upstream_payload(
            data,
            fallback_model=model,
        )
        cost_usd = _estimate_cost(response_model, prompt_tokens, completion_tokens)

        with self._lock:
            self._total_tokens += total_tokens
            self._total_cost_usd += cost_usd
            calls_used = self._calls_started
            remaining_calls = max(0, self._budget.max_calls - self._calls_started)

        return {
            "content": content,
            "model": response_model,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "latency_ms": round(latency_ms, 1),
            "cost_usd": round(cost_usd, 6),
            "limits": {
                "calls_used": calls_used,
                "calls_remaining": remaining_calls,
                "total_tokens_used": self._total_tokens,
                "total_cost_usd": round(self._total_cost_usd, 6),
            },
        }

    def _send_upstream_request(self, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        if not self._api_key:
            raise RelayError(HTTPStatus.BAD_GATEWAY, "Sandbox relay is missing an upstream API key.")

        start = time.perf_counter()
        with httpx.Client(timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        latency_ms = (time.perf_counter() - start) * 1000

        if response.status_code == 401:
            raise RelayError(HTTPStatus.BAD_GATEWAY, "Invalid upstream OpenAI API key.")
        if response.status_code != 200:
            detail = response.text[:300]
            raise RelayError(
                HTTPStatus.BAD_GATEWAY,
                f"Upstream model request failed with {response.status_code}: {detail}",
            )

        return response.json(), latency_ms


def _build_messages(*, system: str, prompt: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system.strip():
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _validate_model(model: str, allowed_models: tuple[str, ...]) -> str:
    canonical_model = resolve_allowed_model(model, allowed_models)
    if not canonical_model:
        supported = ", ".join(allowed_models or OPENAI_CHAT_MODELS)
        raise RelayError(
            HTTPStatus.BAD_REQUEST,
            f"Model '{model}' is not allowed in the sandbox. Choose one of: {supported}.",
        )
    return canonical_model


def _parse_upstream_payload(
    data: dict[str, Any],
    *,
    fallback_model: str,
) -> tuple[str, str, int, int, int]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RelayError(HTTPStatus.BAD_GATEWAY, "Upstream model response was missing choices.")

    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = message.get("content") or ""
    if not isinstance(content, str):
        content = str(content)

    usage_raw = data.get("usage", {}) or {}
    prompt_tokens = int(usage_raw.get("prompt_tokens") or 0)
    completion_tokens = int(usage_raw.get("completion_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or (prompt_tokens + completion_tokens))
    model_name = str(data.get("model") or fallback_model)
    return content, model_name, prompt_tokens, completion_tokens, total_tokens


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (prompt_tokens * prompt_rate) + (completion_tokens * completion_rate)
