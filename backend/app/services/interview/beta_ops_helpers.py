"""Shared helpers for private-beta internal APIs."""

from __future__ import annotations

import hmac
import os

from fastapi import HTTPException, Request

_INSECURE_INTERNAL_TOKENS = {
    "change-me-internal-token",
    "change-me",
}


def _expected_internal_token() -> str:
    token = (os.getenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN") or "").strip()
    from app.core.startup_security import invalid_deployment_token

    if invalid_deployment_token(token):
        return ""
    return token


def require_internal(request: Request) -> None:
    """404 when unauthorized — do not leak that internal tools exist.

    Debug mode does not bypass this. A missing or placeholder token fails closed.
    """
    internal_token = (request.headers.get("X-PromptCode-Internal-Token") or "").strip()
    expected = _expected_internal_token()
    allowed = bool(expected) and hmac.compare_digest(internal_token.encode("utf-8"), expected.encode("utf-8"))
    if not allowed:
        raise HTTPException(status_code=404, detail="Not found")


def tag_infra_failure(session, tag: str, blocked_ms: int = 0) -> None:
    tags = list(session.infra_failure_tags or [])
    if tag not in tags:
        tags.append(tag)
    session.infra_failure_tags = tags
    if blocked_ms > 0:
        session.infra_blocked_ms = int(session.infra_blocked_ms or 0) + int(blocked_ms)
