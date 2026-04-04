from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


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


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    settings = get_settings()
    user_id = decode_access_token(creds.credentials, settings.jwt_secret)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if await _access_token_is_revoked(db=db, token=creds.credentials):
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
    return user


async def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns the user if a valid token is present, otherwise None."""
    if creds is None:
        return None
    settings = get_settings()
    user_id = decode_access_token(creds.credentials, settings.jwt_secret)
    if user_id is None:
        return None
    if await _access_token_is_revoked(db=db, token=creds.credentials):
        return None
    return await db.get(User, user_id)
