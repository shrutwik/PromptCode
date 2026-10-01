"""Shared helpers for private-beta internal APIs."""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

from app.core.config import get_settings


def require_internal(request: Request) -> None:
    """404 when unauthorized — do not leak that internal tools exist."""
    settings = get_settings()
    internal_token = (request.headers.get("X-PromptCode-Internal-Token") or "").strip()
    expected = (os.getenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN") or "").strip()
    allowed = bool(settings.debug) or (expected and internal_token == expected)
    if not allowed:
        raise HTTPException(status_code=404, detail="Not found")


def tag_infra_failure(session, tag: str, blocked_ms: int = 0) -> None:
    tags = list(session.infra_failure_tags or [])
    if tag not in tags:
        tags.append(tag)
    session.infra_failure_tags = tags
    if blocked_ms > 0:
        session.infra_blocked_ms = int(session.infra_blocked_ms or 0) + int(blocked_ms)
