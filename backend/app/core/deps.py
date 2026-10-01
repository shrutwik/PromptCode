from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

ACCESS_COOKIE = "pc_access_token"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def _access_token_is_revoked(*, db: AsyncSession, token: str) -> bool:
    now = datetime.now(timezone.utc)
    revoked = await db.execute(
        select(RevokedToken.id).where(
            RevokedToken.token_hash == _hash_token(token),
            RevokedToken.expires_at >= now,
        )
    )
    return revoked.scalar_one_or_none() is not None


def _extract_access_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> str | None:
    if creds is not None and creds.credentials:
        return creds.credentials
    settings = get_settings()
    if settings.auth_cookie_enabled:
        cookie = request.cookies.get(ACCESS_COOKIE)
        if cookie:
            return cookie
    return None


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_access_token(request, creds)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    settings = get_settings()
    user_id = decode_access_token(token, settings.jwt_secret)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if await _access_token_is_revoked(db=db, token=token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if (user.beta_status or "active") == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )
    return user


async def get_optional_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns the user if a valid token is present, otherwise None."""
    token = _extract_access_token(request, creds)
    if not token:
        return None
    settings = get_settings()
    user_id = decode_access_token(token, settings.jwt_secret)
    if user_id is None:
        return None
    if await _access_token_is_revoked(db=db, token=token):
        return None
    user = await db.get(User, user_id)
    if user is None or (user.beta_status or "active") == "disabled":
        return None
    return user
