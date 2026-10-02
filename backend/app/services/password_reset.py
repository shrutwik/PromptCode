"""Issue and consume hashed, single-use password reset tokens.

Reset requests are disabled unless SMTP and a reset-page origin are configured.
Delivery never logs the token or recipient.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse
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
    "If password reset is available for this account, instructions will be sent."
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


def password_reset_delivery_available() -> bool:
    settings = get_settings()
    origin = urlparse(settings.frontend_url)
    return bool(
        settings.smtp_host.strip()
        and settings.password_reset_from_email.strip()
        and origin.netloc
        and (origin.scheme == "https" or (settings.debug and origin.scheme == "http"))
    )


def _send_password_reset(email: str, raw_token: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.password_reset_from_email
    message["To"] = email
    message["Subject"] = "Reset your PromptCode password"
    message.set_content(
        f"Open {settings.frontend_url.rstrip('/')}/reset-password.html\n"
        f"Enter this single-use reset token: {raw_token}\n"
        "It expires in one hour. If you did not request this, ignore this email."
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def notify_password_reset(email: str, raw_token: str) -> None:
    if not password_reset_delivery_available():
        return
    try:
        await asyncio.wait_for(asyncio.to_thread(_send_password_reset, email, raw_token), timeout=12)
    except Exception:
        # Same HTTP response for delivery failures and unknown accounts; no PII/secrets.
        logger.warning("Password reset delivery failed")


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
