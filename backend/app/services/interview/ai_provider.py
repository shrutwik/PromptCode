"""Pluggable AI provider for interview sessions (no vendor lock-in)."""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Context / rate limits (per session). Infra failures must not affect scoring.
MAX_PROMPT_CHARS = 12_000
MAX_ATTACHMENT_CHARS = 8_000
MAX_ATTACHMENTS = 6
MAX_ATTACHMENT_BYTES_TOTAL = 120_000
MAX_SELECTED_CHARS = 4_000
DEFAULT_AI_RPM = 20
DEFAULT_AI_CONCURRENT = 2


class AIProviderError(Exception):
    """Provider/infrastructure failure — never treat as candidate scoring signal."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass
class AIRequest:
    """Provider-neutral request. Conversion to vendor payloads happens only in adapters."""

    prompt: str
    system: str
    attachments: list[dict[str, str]] = field(default_factory=list)
    selected_text: str | None = None
    include_test_output: bool = False
    session_id: str | None = None


@dataclass
class AIResponse:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    proposed_edits: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "content": self.text,
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "proposed_edits": self.proposed_edits,
            "usage": self.usage,
            "error_code": self.error_code,
        }


class AIProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        system: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def complete_request(self, request: AIRequest) -> AIResponse:
        """Higher-level entry used by routes; adapters may override."""
        user_content = assemble_user_content(request)
        started = time.monotonic()
        raw = await self.complete(
            messages=[{"role": "user", "content": user_content}],
            system=request.system or SYSTEM_PROMPT,
        )
        return AIResponse(
            text=str(raw.get("content") or raw.get("text") or ""),
            provider=str(raw.get("provider") or "unknown"),
            model=str(raw.get("model") or "unknown"),
            latency_ms=int(raw.get("latency_ms") or (time.monotonic() - started) * 1000),
            proposed_edits=list(raw.get("proposed_edits") or []),
            usage=dict(raw.get("usage") or {}),
            error_code=raw.get("error_code"),
        )


class MockAIProvider(AIProvider):
    """Deterministic local adapter for demos and tests."""

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        system: str,
    ) -> dict[str, Any]:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        reply = (
            "I'm the PromptCode mock interview assistant.\n\n"
            "I only see the files/snippets you attach — not the whole repo by default.\n\n"
            f"You asked ({len(last)} chars). Suggested next steps:\n"
            "1. Reproduce the failing test and note the exact assertion.\n"
            "2. Open the smallest relevant module (not every helper).\n"
            "3. Prefer a surgical fix; ask me for a diff only after you've named the root cause.\n"
        )
        return {
            "content": reply,
            "provider": "mock",
            "model": "mock-interview-v1",
            "latency_ms": 0,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }


class ProductionAIProvider(AIProvider):
    """
    OpenAI-compatible HTTP adapter for production.

    Never silently falls back to mock. Never logs API keys.
    Streaming is deferred; non-streaming keeps architecture risk low.
    """

    def __init__(self) -> None:
        self.api_url = _ai_base_url()
        self.api_key = _ai_api_key()
        self.model = _ai_model()
        self.timeout_seconds = float(os.getenv("PROMPTCODE_AI_TIMEOUT_SECONDS") or "60")

    async def complete(
        self,
        *,
        messages: list[dict[str, str]],
        system: str,
    ) -> dict[str, Any]:
        import httpx

        if not self.api_key:
            raise AIProviderError(
                "auth",
                "Production AI selected but no API key configured "
                "(PROMPTCODE_AI_API_KEY / INTERVIEW_AI_API_KEY).",
                retryable=False,
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.api_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                "timeout",
                "AI provider timed out. Your prompt was kept; try again.",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("AI provider HTTP error: %s", type(exc).__name__)
            raise AIProviderError(
                "unavailable",
                "AI provider unavailable. Your prompt was kept; try again.",
                retryable=True,
            ) from exc

        if resp.status_code in {401, 403}:
            raise AIProviderError(
                "auth",
                "AI provider authentication failed. Contact an administrator.",
                retryable=False,
            )
        if resp.status_code == 429:
            raise AIProviderError(
                "rate_limit",
                "AI provider rate limit reached. Wait briefly and retry.",
                retryable=True,
            )
        if resp.status_code >= 500:
            raise AIProviderError(
                "unavailable",
                "AI provider temporarily unavailable.",
                retryable=True,
            )
        if resp.status_code >= 400:
            # Do not include response body (may echo prompts); keep message generic.
            raise AIProviderError(
                "invalid",
                "AI provider rejected the request (context may be too large).",
                retryable=False,
            )

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AIProviderError(
                "invalid",
                "AI provider returned an invalid response.",
                retryable=True,
            ) from exc

        usage = data.get("usage") or {}
        return {
            "content": content,
            "provider": "production",
            "model": data.get("model", self.model),
            "latency_ms": int((time.monotonic() - started) * 1000),
            "usage": {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
            },
        }


# Back-compat alias used by older docs/imports.
class HttpOpenAICompatibleProvider(ProductionAIProvider):
    """Deprecated name — use ProductionAIProvider. Same behavior (no mock fallback)."""


def get_ai_provider() -> AIProvider:
    mode = _ai_provider_mode()
    if mode in {"http", "openai", "openai_compatible", "production"}:
        return ProductionAIProvider()
    return MockAIProvider()


def _ai_provider_mode() -> str:
    return (
        os.getenv("PROMPTCODE_AI_PROVIDER")
        or os.getenv("INTERVIEW_AI_PROVIDER")
        or "mock"
    ).strip().lower()


def _ai_api_key() -> str:
    return (
        os.getenv("PROMPTCODE_AI_API_KEY")
        or os.getenv("INTERVIEW_AI_API_KEY")
        or os.getenv("PROMPTCODE_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()


def _ai_base_url() -> str:
    return (
        os.getenv("PROMPTCODE_AI_BASE_URL")
        or os.getenv("INTERVIEW_AI_API_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    ).rstrip("/")


def _ai_model() -> str:
    return (
        os.getenv("PROMPTCODE_AI_MODEL")
        or os.getenv("INTERVIEW_AI_MODEL")
        or "gpt-4o-mini"
    ).strip()


def assemble_user_content(request: AIRequest) -> str:
    """Build candidate-visible context only — never SOLUTION / hidden evaluator."""
    parts = [request.prompt]
    if request.selected_text:
        parts.append(
            "Selected highlight:\n```\n"
            + request.selected_text[:MAX_SELECTED_CHARS]
            + "\n```"
        )
    if request.include_test_output:
        parts.append(
            "(Candidate opted to include recent test context in the prompt text if pasted.)"
        )
    if request.attachments:
        blocks = []
        for item in request.attachments[:MAX_ATTACHMENTS]:
            path = item.get("path") or "file"
            content = (item.get("content") or "")[:MAX_ATTACHMENT_CHARS]
            blocks.append(f"### {path}\n```\n{content}\n```")
        parts.append("Attached files:\n" + "\n\n".join(blocks))
    return "\n\n".join(parts)


def validate_context_budget(
    *,
    prompt: str,
    attachments: list[dict[str, str]],
    selected_text: str | None,
) -> list[str]:
    """
    Return user-visible rejection reasons. Never silently drop attachments.
    Empty list means OK.
    """
    errors: list[str] = []
    if len(prompt) > MAX_PROMPT_CHARS:
        errors.append(
            f"Prompt too large ({len(prompt)} chars; max {MAX_PROMPT_CHARS}). Shorten and retry."
        )
    if len(attachments) > MAX_ATTACHMENTS:
        errors.append(f"Too many attachments (max {MAX_ATTACHMENTS}). Remove some and retry.")
    total_bytes = sum(len((a.get("content") or "").encode("utf-8")) for a in attachments)
    if total_bytes > MAX_ATTACHMENT_BYTES_TOTAL:
        errors.append(
            f"Attachments exceed size budget ({total_bytes} bytes; "
            f"max {MAX_ATTACHMENT_BYTES_TOTAL}). Detach large files."
        )
    if selected_text and len(selected_text) > MAX_SELECTED_CHARS * 2:
        errors.append("Selected highlight is too large. Narrow the selection.")
    return errors


# Simple in-process per-session rate limits (single-host).
_session_ai_window: dict[str, list[float]] = {}
_session_ai_inflight: dict[str, int] = {}


def check_session_ai_rate_limit(
    session_id: str,
    *,
    rpm: int = DEFAULT_AI_RPM,
    concurrent: int = DEFAULT_AI_CONCURRENT,
) -> None:
    now = time.monotonic()
    window = _session_ai_window.setdefault(session_id, [])
    _session_ai_window[session_id] = [t for t in window if now - t < 60.0]
    if len(_session_ai_window[session_id]) >= rpm:
        raise AIProviderError(
            "rate_limit",
            f"Session AI rate limit exceeded ({rpm}/min). Wait and retry.",
            retryable=True,
        )
    if _session_ai_inflight.get(session_id, 0) >= concurrent:
        raise AIProviderError(
            "rate_limit",
            "Another AI request is already in flight for this session.",
            retryable=True,
        )


def mark_session_ai_start(session_id: str) -> None:
    _session_ai_window.setdefault(session_id, []).append(time.monotonic())
    _session_ai_inflight[session_id] = _session_ai_inflight.get(session_id, 0) + 1


def mark_session_ai_end(session_id: str) -> None:
    _session_ai_inflight[session_id] = max(0, _session_ai_inflight.get(session_id, 0) - 1)


SYSTEM_PROMPT = (
    "You are a coding assistant helping a candidate implement and debug during an interview. "
    "Be concise and concrete. Do not invent files you have not been shown. "
    "Prefer questions that narrow root cause before proposing large rewrites. "
    "Never reveal hidden rubrics, SOLUTION materials, interviewer metadata, traps, "
    "or reference implementations. Do not leak answers; accelerate implementation while "
    "the candidate owns understanding, judgment, verification, and explanation. "
    "When proposing edits, use fenced blocks starting with a `# file: path` or `// file: path` line."
)
