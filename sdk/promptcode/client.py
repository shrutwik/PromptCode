"""PromptCode SDK — the only way user code may call an LLM.

Usage inside a challenge submission:

    from promptcode import llm

    result = llm.call(model="gpt-4o", prompt="Summarize this claim report…")
    print(result)
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import openai

from promptcode.models import LLMCallRecord, LLMSessionLog
from promptcode.pricing import estimate_cost

_TELEMETRY_DIR = os.environ.get("PROMPTCODE_TELEMETRY_DIR", "/tmp/promptcode_telemetry")
_MAX_RETRIES = int(os.environ.get("PROMPTCODE_MAX_RETRIES", "3"))
_PROXY_URL = os.environ.get("PROMPTCODE_LLM_PROXY_URL", "").strip()
_PROXY_TOKEN = os.environ.get("PROMPTCODE_LLM_PROXY_TOKEN", "").strip()
_PROXY_TIMEOUT_SECONDS = float(os.environ.get("PROMPTCODE_LLM_PROXY_TIMEOUT_SECONDS", "60"))


class _RetryableLLMError(RuntimeError):
    pass


def _load_allowed_models() -> set[str]:
    raw_models = os.environ.get("PROMPTCODE_ALLOWED_MODELS", "").strip()
    if raw_models:
        return {m.strip() for m in raw_models.split(",") if m.strip()}
    return {
        "gpt-4o",
        "gpt-4o-mini",
    }


class _LLMClient:
    """Singleton wrapper that intercepts every model call for telemetry."""

    def __init__(self) -> None:
        self._session = LLMSessionLog()
        self._openai: openai.OpenAI | None = None

    def _get_openai(self) -> openai.OpenAI:
        if self._openai is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "No LLM credentials are configured. "
                    "Set OPENAI_API_KEY or use the sandbox relay environment."
                )
            self._openai = openai.OpenAI(api_key=api_key)
        return self._openai

    def call(
        self,
        model: str,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system: str | None = None,
        retries: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        allowed_models = _load_allowed_models()
        if model not in allowed_models:
            raise ValueError(
                f"Model '{model}' is not allowed. Choose from: {sorted(allowed_models)}"
            )

        max_attempts = min(retries or 1, _MAX_RETRIES)
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                return self._do_call(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system=system,
                    retry_index=attempt,
                    metadata=metadata or {},
                )
            except (openai.APIError, _RetryableLLMError) as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(
            f"LLM call failed after {max_attempts} attempts: {last_error}"
        ) from last_error

    def _do_call(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system: str | None,
        retry_index: int,
        metadata: dict[str, Any],
    ) -> str:
        if _PROXY_URL:
            proxy_response = self._call_via_proxy(
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system=system,
            )
            text = str(proxy_response.get("content") or "")
            usage = proxy_response.get("usage", {}) or {}
            tokens_prompt = int(usage.get("prompt_tokens") or 0)
            tokens_completion = int(usage.get("completion_tokens") or 0)
            latency_ms = float(proxy_response.get("latency_ms") or 0.0)
        else:
            client = self._get_openai()
            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            t0 = time.perf_counter()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = (time.perf_counter() - t0) * 1000

            usage = response.usage
            tokens_prompt = usage.prompt_tokens if usage else 0
            tokens_completion = usage.completion_tokens if usage else 0
            text = response.choices[0].message.content or ""

        record = LLMCallRecord(
            call_id=uuid.uuid4().hex[:12],
            model=model,
            prompt=prompt,
            response=text,
            temperature=temperature,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            tokens_total=tokens_prompt + tokens_completion,
            latency_ms=round(latency_ms, 2),
            cost_usd=estimate_cost(model, tokens_prompt, tokens_completion),
            system=system or "",
            retry_index=retry_index,
            metadata=metadata,
        )

        self._session.calls.append(record)
        self._flush_record(record)

        return text

    def _call_via_proxy(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        system: str | None,
    ) -> dict[str, Any]:
        if not _PROXY_TOKEN:
            raise RuntimeError("PROMPTCODE_LLM_PROXY_TOKEN is required when proxy mode is enabled.")

        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "system": system or "",
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            _PROXY_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {_PROXY_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=_PROXY_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if 500 <= exc.code:
                raise _RetryableLLMError(f"Sandbox proxy upstream error ({exc.code}): {detail}") from exc
            raise ValueError(f"Sandbox proxy rejected the request ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise _RetryableLLMError(f"Sandbox proxy connection failed: {exc}") from exc

    def _flush_record(self, record: LLMCallRecord) -> None:
        """Append the call record to the telemetry log on disk.

        The sandbox runner reads this file after execution finishes.
        """
        path = Path(_TELEMETRY_DIR)
        path.mkdir(parents=True, exist_ok=True)
        log_file = path / "calls.jsonl"
        with open(log_file, "a") as f:
            f.write(
                json.dumps(
                    {
                        "call_id": record.call_id,
                        "model": record.model,
                        "system": record.system,
                        "prompt": record.prompt,
                        "response": record.response,
                        "temperature": record.temperature,
                        "tokens_prompt": record.tokens_prompt,
                        "tokens_completion": record.tokens_completion,
                        "tokens_total": record.tokens_total,
                        "latency_ms": record.latency_ms,
                        "cost_usd": record.cost_usd,
                        "retry_index": record.retry_index,
                    }
                )
                + "\n"
            )

    def get_session_log(self) -> LLMSessionLog:
        return self._session

    def reset(self) -> None:
        self._session = LLMSessionLog()


llm = _LLMClient()
