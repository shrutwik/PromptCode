from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.model_policy import OPENAI_CHAT_MODELS, resolve_allowed_model
from app.db.session import get_db
from app.models.challenge import Challenge
from app.models.user import User

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    challenge_id: uuid.UUID
    messages: list[ChatMessage]
    code: str = ""


class ChatResponse(BaseModel):
    reply: str
    model: str | None = None
    usage: dict[str, int] | None = None
    latency_ms: float | None = None
    estimated_cost_usd: float | None = None


class PlaygroundMessage(BaseModel):
    role: str
    content: str


class PlaygroundRunRequest(BaseModel):
    system: str = ""
    messages: list[PlaygroundMessage]
    model: str | None = None
    temperature: float = 0.0
    max_tokens: int = 1000


class PlaygroundRunResponse(BaseModel):
    output: str
    model: str
    usage: dict[str, int]
    latency_ms: float
    estimated_cost_usd: float
    raw_id: str = ""


_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
    "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
}
_DEFAULT_PRICING = (5.00 / 1_000_000, 15.00 / 1_000_000)
_SUPPORTED_MODELS = OPENAI_CHAT_MODELS
_MAX_CHAT_MESSAGES = 30
_MAX_MESSAGE_CHARS = 6_000
_MAX_CODE_CHARS = 120_000
_MAX_SYSTEM_CHARS = 6_000
_COACH_MAX_TOKENS = 1024
_MAX_AUTO_CONTINUATIONS = 3
_RATE_WINDOW_SECONDS = 60
_COACH_RATE_LIMIT = 20
_PLAYGROUND_RATE_LIMIT = 30
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = asyncio.Lock()
_CONTINUE_PROMPT = (
    "Continue exactly where you stopped. "
    "Do not repeat prior text. Keep the same format and finish the answer."
)
_CompletionRequester = Callable[[list[dict[str, Any]]], Awaitable[tuple[dict[str, Any], float]]]


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return round((prompt_tokens * prompt_rate) + (completion_tokens * completion_rate), 6)


def _resolve_requested_model(requested_model: str | None, settings: Any) -> tuple[str, str]:
    raw_model = str(requested_model or settings.openai_model or "gpt-4o").strip()
    if not raw_model:
        raw_model = "gpt-4o"

    canonical_model = resolve_allowed_model(raw_model, _SUPPORTED_MODELS)
    if not canonical_model:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model '{raw_model}'. Choose one of: {', '.join(_SUPPORTED_MODELS)}.",
        )
    return raw_model, canonical_model


def _resolve_model_name(requested_model: str | None, settings: Any) -> str:
    _raw_model, canonical_model = _resolve_requested_model(requested_model, settings)
    return canonical_model


def _build_model_candidates(raw_model: str, canonical_model: str) -> list[str]:
    candidates: list[str] = []

    def _add(model_id: str) -> None:
        candidate = str(model_id or "").strip()
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    _add(raw_model)
    _add(canonical_model)
    _add(f"protected.{canonical_model}")
    _add(f"openai/{canonical_model}")
    _add(f"openai:{canonical_model}")
    return candidates


def _is_model_not_found_error(status_code: int, body_text: str) -> bool:
    if status_code not in (400, 404):
        return False
    text = str(body_text or "").lower()
    return "model not found" in text or "model_not_found" in text or "unknown model" in text


async def _post_chat_completion_with_model_fallback(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    model_candidates: list[str],
    messages: list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
) -> tuple[dict[str, Any], float, str]:
    latency_total_ms = 0.0
    if not model_candidates:
        raise HTTPException(status_code=502, detail="No model candidates available for AI request.")

    for idx, candidate in enumerate(model_candidates):
        body = {
            "model": candidate,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        start = time.perf_counter()
        resp = await client.post(url, json=body, headers=headers)
        latency_total_ms += (time.perf_counter() - start) * 1000

        if resp.status_code == 200:
            return resp.json(), latency_total_ms, candidate

        if resp.status_code == 401:
            raise HTTPException(
                status_code=502,
                detail="Invalid API key — check PROMPTCODE_OPENAI_API_KEY in .env",
            )

        resp_text = resp.text[:300]
        if _is_model_not_found_error(resp.status_code, resp_text) and idx < (len(model_candidates) - 1):
            continue

        if _is_model_not_found_error(resp.status_code, resp_text):
            tried = ", ".join(model_candidates)
            raise HTTPException(
                status_code=502,
                detail=f"Model not found for tried ids: {tried}. Update PROMPTCODE_OPENAI_MODEL to a provider-supported id.",
            )

        raise HTTPException(
            status_code=502,
            detail=f"AI API returned {resp.status_code}: {resp_text}",
        )

    tried = ", ".join(model_candidates)
    raise HTTPException(
        status_code=502,
        detail=f"Model selection failed for all tried ids: {tried}.",
    )


def _parse_completion_payload(data: dict[str, Any], fallback_model: str) -> tuple[str, str, str, int, int, int]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(status_code=502, detail="AI API returned malformed payload (missing choices).")

    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = message.get("content") or ""
    if not isinstance(content, str):
        content = str(content)

    usage_raw = data.get("usage", {}) or {}
    prompt_tokens = int(usage_raw.get("prompt_tokens") or 0)
    completion_tokens = int(usage_raw.get("completion_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or (prompt_tokens + completion_tokens))
    finish_reason = str(choice.get("finish_reason") or "")
    model_name = str(data.get("model") or fallback_model)
    return content, finish_reason, model_name, prompt_tokens, completion_tokens, total_tokens


async def _run_completion_with_auto_continue(
    *,
    base_messages: list[dict[str, Any]],
    model: str,
    request_completion: _CompletionRequester,
    max_auto_continuations: int = _MAX_AUTO_CONTINUATIONS,
) -> tuple[str, str, dict[str, int], float, str]:
    request_messages = [{"role": str(m["role"]), "content": str(m["content"])} for m in base_messages]

    reply_chunks: list[str] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    latency_total_ms = 0.0
    model_name = model
    raw_id = ""
    continuation_count = 0
    final_finish_reason = ""

    while True:
        data, latency_ms = await request_completion(request_messages)
        latency_total_ms += latency_ms
        raw_id = str(data.get("id") or raw_id)

        chunk, finish_reason, chunk_model, prompt_tokens, completion_tokens, chunk_total_tokens = _parse_completion_payload(
            data,
            fallback_model=model_name,
        )
        final_finish_reason = finish_reason
        model_name = chunk_model or model_name
        reply_chunks.append(chunk)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_tokens += chunk_total_tokens

        if finish_reason != "length":
            break
        if continuation_count >= max_auto_continuations:
            break

        continuation_count += 1
        if chunk.strip():
            request_messages.append({"role": "assistant", "content": chunk})
        request_messages.append({"role": "user", "content": _CONTINUE_PROMPT})

    reply = "".join(reply_chunks).strip()
    if final_finish_reason == "length" and continuation_count >= max_auto_continuations and reply:
        reply += '\n\n[Output may still be truncated. Ask "continue" for more.]'

    usage = {
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens or (total_prompt_tokens + total_completion_tokens),
    }
    return reply, model_name, usage, round(latency_total_ms, 1), raw_id


async def _enforce_rate_limit(*, key: str, max_requests: int, window_seconds: int = _RATE_WINDOW_SECONDS) -> None:
    now = time.time()
    async with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[key]
        while bucket and (now - bucket[0]) > window_seconds:
            bucket.popleft()
        if len(bucket) >= max_requests:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Retry in {retry_after}s.",
            )
        bucket.append(now)


def _validate_messages(messages: list[ChatMessage] | list[PlaygroundMessage]) -> None:
    if not messages:
        raise HTTPException(status_code=400, detail="At least one message is required.")
    if len(messages) > _MAX_CHAT_MESSAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many messages. Maximum {_MAX_CHAT_MESSAGES}.",
        )
    for m in messages:
        if m.role not in ("system", "user", "assistant"):
            raise HTTPException(status_code=400, detail=f"Invalid role: {m.role}")
        content = str(m.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="Message content cannot be empty.")
        if len(content) > _MAX_MESSAGE_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f"Message too long (>{_MAX_MESSAGE_CHARS} chars).",
            )


def _build_system_prompt(challenge: Challenge) -> str:
    desc = challenge.description or challenge.title
    constraints = challenge.constraints or {}
    parts = [
        "You are a helpful coding assistant for the PromptCode platform.",
        "The user is working on a prompt-engineering challenge. Help them iteratively improve their solution instead of rewriting everything from scratch.",
        f"\n## Challenge: {challenge.title}",
        f"\n{desc}",
    ]
    if constraints:
        parts.append("\n## Constraints")
        for k, v in constraints.items():
            parts.append(f"- {k}: {v}")

    parts.append(
        "\n## Guidelines"
        "\n- Keep responses short and focused: at most 6 bullet points or ~150 words unless the user explicitly asks for more detail."
        "\n- Start by briefly stating the main issue you see, then suggest specific, minimal changes (to prompts or code) rather than a full rewrite."
        "\n- Focus on prompt-engineering techniques: clear instructions, few-shot examples, explicit output formats (JSON schemas), and good defaults for temperature and max tokens."
        "\n- When relevant, explain how a change might affect the scoring dimensions: accuracy, prompt quality, rule adherence, efficiency, reliability, orchestration, code quality, and edge case handling."
        "\n- If you show code, only show the small function or snippet that needs to change, not the entire file."
        "\n- Respect the challenge spec (input/output formats, constraints, hidden tests) and do NOT reveal or guess ground-truth answers or hidden data."
        "\n- If the user pastes code, refer to specific parts of it (e.g., 'in your anomaly detection loop...') and give targeted improvements."
    )
    return "\n".join(parts)


def _get_api_url(settings) -> str:
    base = settings.openai_base_url.rstrip("/") if settings.openai_base_url else "https://api.openai.com/v1"
    return f"{base}/chat/completions"


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _enforce_rate_limit(key=f"coach:{user.id}", max_requests=_COACH_RATE_LIMIT)
    _validate_messages(payload.messages)
    if len(payload.code) > _MAX_CODE_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Code payload too large (>{_MAX_CODE_CHARS} chars).",
        )

    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant not configured — set PROMPTCODE_OPENAI_API_KEY in .env",
        )

    challenge = await db.get(Challenge, payload.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    system_prompt = _build_system_prompt(challenge)
    if payload.code:
        system_prompt += f"\n\n## User's current code\n```python\n{payload.code}\n```"

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for m in payload.messages[-20:]:
        messages.append({"role": m.role, "content": m.content})

    raw_model, canonical_model = _resolve_requested_model(None, settings)
    model_candidates = _build_model_candidates(raw_model, canonical_model)
    url = _get_api_url(settings)
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resolved_model: str | None = None

            async def _request_completion(current_messages: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
                nonlocal resolved_model
                current_candidates = [resolved_model] if resolved_model else model_candidates
                data, request_latency_ms, used_model = await _post_chat_completion_with_model_fallback(
                    client=client,
                    url=url,
                    headers=headers,
                    model_candidates=current_candidates,
                    messages=current_messages,
                    max_tokens=_COACH_MAX_TOKENS,
                    temperature=0.7,
                )
                resolved_model = used_model
                return data, request_latency_ms

            reply, model_name, usage_raw, latency_ms, _raw_id = await _run_completion_with_auto_continue(
                base_messages=messages,
                model=canonical_model,
                request_completion=_request_completion,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {e}") from e

    prompt_tokens = int(usage_raw.get("prompt_tokens") or 0)
    completion_tokens = int(usage_raw.get("completion_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or (prompt_tokens + completion_tokens))
    billing_model = resolve_allowed_model(model_name, _MODEL_PRICING.keys()) or canonical_model
    estimated_cost = _estimate_cost_usd(billing_model, prompt_tokens, completion_tokens)

    return ChatResponse(
        reply=reply,
        model=model_name,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost,
    )


@router.post("/playground-run", response_model=PlaygroundRunResponse)
async def playground_run(
    payload: PlaygroundRunRequest,
    user: User = Depends(get_current_user),
):
    await _enforce_rate_limit(key=f"playground:{user.id}", max_requests=_PLAYGROUND_RATE_LIMIT)
    _validate_messages(payload.messages)
    if len(payload.system) > _MAX_SYSTEM_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"System prompt too long (>{_MAX_SYSTEM_CHARS} chars).",
        )

    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant not configured — set PROMPTCODE_OPENAI_API_KEY in .env",
        )

    raw_model, canonical_model = _resolve_requested_model(payload.model, settings)
    model_candidates = _build_model_candidates(raw_model, canonical_model)
    messages: list[dict[str, str]] = []
    if payload.system.strip():
        messages.append({"role": "system", "content": payload.system})
    for m in payload.messages[-30:]:
        messages.append({"role": m.role, "content": m.content})

    if not any(m["role"] == "user" and m["content"].strip() for m in messages):
        raise HTTPException(status_code=400, detail="Playground requires at least one user message")

    url = _get_api_url(settings)
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    max_tokens = max(1, min(int(payload.max_tokens), 4096))
    temperature = max(0.0, min(float(payload.temperature), 2.0))

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resolved_model: str | None = None

            async def _request_completion(current_messages: list[dict[str, Any]]) -> tuple[dict[str, Any], float]:
                nonlocal resolved_model
                current_candidates = [resolved_model] if resolved_model else model_candidates
                data, request_latency_ms, used_model = await _post_chat_completion_with_model_fallback(
                    client=client,
                    url=url,
                    headers=headers,
                    model_candidates=current_candidates,
                    messages=current_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                resolved_model = used_model
                return data, request_latency_ms

            output, model_name, usage_raw, latency_ms, raw_id = await _run_completion_with_auto_continue(
                base_messages=messages,
                model=canonical_model,
                request_completion=_request_completion,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {e}") from e

    prompt_tokens = int(usage_raw.get("prompt_tokens") or 0)
    completion_tokens = int(usage_raw.get("completion_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or (prompt_tokens + completion_tokens))
    billing_model = resolve_allowed_model(model_name, _MODEL_PRICING.keys()) or canonical_model

    return PlaygroundRunResponse(
        output=output,
        model=model_name,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        latency_ms=latency_ms,
        estimated_cost_usd=_estimate_cost_usd(billing_model, prompt_tokens, completion_tokens),
        raw_id=raw_id,
    )
