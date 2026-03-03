from __future__ import annotations

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

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=body, headers=headers)

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {e}") from e

    return ChatResponse(reply=reply)
