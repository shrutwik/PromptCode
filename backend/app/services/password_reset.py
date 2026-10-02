"""Issue and consume hashed, single-use password reset tokens.

No SMTP provider is configured. ``notify_password_reset`` is the delivery hook.
It must not log or return the raw token. Tests monkeypatch it.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User

logger = logging.getLogger(__name__)

RESET_TOKEN_TTL = timedelta(hours=1)
FORGOT_PASSWORD_MESSAGE = (
    "If an account exists for that email, we sent password reset instructions."
)
PASSWORD_UPDATED_MESSAGE = "Password updated."


class ResetTokenError(Exception):
    """Raised when a reset token is missing, expired, or already used."""


def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def issue_password_reset(db: AsyncSession, user: User) -> str:
    """Create a reset row and return the raw token to the caller. Not for HTTP responses."""
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + RESET_TOKEN_TTL,
        )
    )
    await db.commit()
    return raw_token


async def notify_password_reset(email: str, raw_token: str) -> None:
    """Dev-only delivery hook. The raw token stays with the caller, never the log."""
    del raw_token
    if get_settings().debug:
        logger.info("Dev password reset requested for %s", email)


async def reset_password_with_token(
    db: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
) -> None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_reset_token(raw_token)
        )
    )
    row = result.scalar_one_or_none()
    if row is None or row.used_at is not None or _as_utc(row.expires_at) <= now:
        raise ResetTokenError()
    user = await db.get(User, row.user_id)
    if user is None:
        raise ResetTokenError()
    user.password_hash = hash_password(new_password)
    row.used_at = now
    await db.commit()
