from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.challenge import Challenge

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
    "gpt-4-turbo": (10.00 / 1_000_000, 30.00 / 1_000_000),
    "gpt-3.5-turbo": (0.50 / 1_000_000, 1.50 / 1_000_000),
}
_DEFAULT_PRICING = (5.00 / 1_000_000, 15.00 / 1_000_000)


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return round((prompt_tokens * prompt_rate) + (completion_tokens * completion_rate), 6)


def _build_system_prompt(challenge: Challenge) -> str:
    desc = challenge.description or challenge.title
    constraints = challenge.constraints or {}
    parts = [
        "You are a helpful coding assistant for the PromptCode platform.",
        "The user is working on a prompt‑engineering challenge. Help them iteratively improve their solution instead of rewriting everything from scratch.",
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
        "\n- If the user pastes code, refer to specific parts of it (e.g., “in your anomaly detection loop…”) and give targeted improvements."
    )
    return "\n".join(parts)


def _get_api_url(settings) -> str:
    base = settings.openai_base_url.rstrip("/") if settings.openai_base_url else "https://api.openai.com/v1"
    return f"{base}/chat/completions"


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
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

    try:
        url = _get_api_url(settings)
        body = {
            "model": settings.openai_model,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.7,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body, headers=headers)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)

        if resp.status_code == 401:
            raise HTTPException(
                status_code=502,
                detail="Invalid API key — check PROMPTCODE_OPENAI_API_KEY in .env",
            )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"AI API returned {resp.status_code}: {resp.text[:300]}",
            )

        data = resp.json()
        reply = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        model_name = str(data.get("model") or settings.openai_model)
        estimated_cost = _estimate_cost_usd(model_name, prompt_tokens, completion_tokens)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {e}") from e

    return ChatResponse(
        reply=reply,
        model=model_name,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": int(usage.get("total_tokens") or (prompt_tokens + completion_tokens)),
        },
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost,
    )


@router.post("/playground-run", response_model=PlaygroundRunResponse)
async def playground_run(payload: PlaygroundRunRequest):
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="AI assistant not configured — set PROMPTCODE_OPENAI_API_KEY in .env",
        )

    model = payload.model or settings.openai_model
    messages: list[dict[str, str]] = []
    if payload.system.strip():
        messages.append({"role": "system", "content": payload.system})
    for m in payload.messages[-30:]:
        messages.append({"role": m.role, "content": m.content})

    if not any(m["role"] == "user" and m["content"].strip() for m in messages):
        raise HTTPException(status_code=400, detail="Playground requires at least one user message")

    url = _get_api_url(settings)
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max(1, min(int(payload.max_tokens), 4096)),
        "temperature": max(0.0, min(float(payload.temperature), 2.0)),
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, json=body, headers=headers)
        latency_ms = round((time.perf_counter() - start) * 1000, 1)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {e}") from e

    if resp.status_code == 401:
        raise HTTPException(
            status_code=502,
            detail="Invalid API key — check PROMPTCODE_OPENAI_API_KEY in .env",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"AI API returned {resp.status_code}: {resp.text[:300]}",
        )

    data = resp.json()
    output = data["choices"][0]["message"]["content"] or ""
    usage_raw = data.get("usage", {}) or {}
    prompt_tokens = int(usage_raw.get("prompt_tokens") or 0)
    completion_tokens = int(usage_raw.get("completion_tokens") or 0)
    total_tokens = int(usage_raw.get("total_tokens") or (prompt_tokens + completion_tokens))
    model_name = str(data.get("model") or model)

    return PlaygroundRunResponse(
        output=output,
        model=model_name,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        latency_ms=latency_ms,
        estimated_cost_usd=_estimate_cost_usd(model_name, prompt_tokens, completion_tokens),
        raw_id=str(data.get("id") or ""),
    )
