"""Beta access: invite codes + optional email allowlist."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.beta_ops import InviteCode


def _allowlist() -> set[str]:
    raw = (get_settings().beta_email_allowlist or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def beta_gate_enabled() -> bool:
    return bool(get_settings().beta_invite_required)


async def consume_invite_or_allowlist(
    db: AsyncSession,
    *,
    email: str,
    invite_code: str | None,
) -> tuple[InviteCode | None, str, str]:
    """Validate invite/allowlist. Returns (invite, cohort, signup_source).

    Failed invites never leak whether a code exists — generic 403 only.
    Existing users are unaffected (gate only on signup).
    """
    if not beta_gate_enabled():
        return None, "open", "direct"

    email_l = email.strip().lower()
    allow = _allowlist()
    if allow and email_l in allow:
        return None, get_settings().beta_default_cohort, "allowlist"

    code = (invite_code or "").strip()
    if not code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite required for private beta",
        )

    result = await db.execute(select(InviteCode).where(InviteCode.code == code))
    invite = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        invite is None
        or (invite.expires_at is not None and invite.expires_at < now)
        or invite.use_count >= invite.max_uses
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite required for private beta",
        )

    invite.use_count += 1
    return invite, invite.cohort or get_settings().beta_default_cohort, "invite"


def generate_invite_code() -> str:
    return secrets.token_urlsafe(12)


async def create_invite(
    db: AsyncSession,
    *,
    cohort: str = "beta",
    max_uses: int = 1,
    note: str | None = None,
    created_by: str | None = None,
    expires_at: datetime | None = None,
    code: str | None = None,
) -> InviteCode:
    invite = InviteCode(
        code=code or generate_invite_code(),
        cohort=cohort,
        max_uses=max(1, max_uses),
        note=(note or "")[:256] or None,
        created_by=(created_by or "")[:128] or None,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite
