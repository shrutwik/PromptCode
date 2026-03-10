from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.schemas.user import (
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)

router = APIRouter()

_AUTH_RATE_WINDOW = 60  # seconds
_AUTH_RATE_LIMIT = 10  # max attempts per IP per window


class _InMemoryRateLimiter:
    def __init__(
        self,
        *,
        window_seconds: int,
        max_attempts: int,
        sweep_interval: int = 256,
    ) -> None:
        self.window_seconds = float(window_seconds)
        self.max_attempts = max_attempts
        self.sweep_interval = max(1, sweep_interval)
        self._events: dict[str, deque[float]] = {}
        self._checks_since_sweep = 0
        self._lock = asyncio.Lock()

    @staticmethod
    def _prune_expired(events: deque[float], cutoff: float) -> None:
        while events and events[0] <= cutoff:
            events.popleft()

    def _sweep_expired_keys(self, cutoff: float) -> None:
        stale_keys: list[str] = []
        for key, events in self._events.items():
            self._prune_expired(events, cutoff)
            if not events:
                stale_keys.append(key)
        for key in stale_keys:
            self._events.pop(key, None)

    async def check(self, key: str, *, now: float | None = None) -> None:
        current_time = time.monotonic() if now is None else now
        cutoff = current_time - self.window_seconds

        async with self._lock:
            self._checks_since_sweep += 1
            if self._checks_since_sweep >= self.sweep_interval:
                self._sweep_expired_keys(cutoff)
                self._checks_since_sweep = 0

            events = self._events.get(key)
            if events is None:
                events = deque()
                self._events[key] = events
            else:
                self._prune_expired(events, cutoff)

            if len(events) >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts. Please try again later.",
                    headers={"Retry-After": str(int(self.window_seconds))},
                )

            events.append(current_time)


_auth_rate_limiter = _InMemoryRateLimiter(
    window_seconds=_AUTH_RATE_WINDOW,
    max_attempts=_AUTH_RATE_LIMIT,
)


def _hash_token(token: str) -> str:
    """SHA-256 hex digest of a raw token string (64 chars)."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _revoke_refresh_token(
    db: AsyncSession,
    *,
    refresh_token: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    token_hash = _hash_token(refresh_token)
    expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    await db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
    existing = await db.execute(
        select(RevokedToken).where(RevokedToken.token_hash == token_hash)
    )
    if existing.scalar_one_or_none() is None:
        db.add(RevokedToken(token_hash=token_hash, expires_at=expires_at))


def _auth_client_key(request: Request) -> str:
    peer_host = request.client.host if request.client and request.client.host else ""
    try:
        peer_ip = ipaddress.ip_address(peer_host)
    except ValueError:
        peer_ip = None

    if peer_ip is not None:
        trusted_proxy_cidrs = get_settings().auth_trusted_proxy_cidrs
        trusted_proxy_networks = tuple(
            ipaddress.ip_network(cidr, strict=False)
            for cidr in trusted_proxy_cidrs
        )
        if any(peer_ip in network for network in trusted_proxy_networks):
            forwarded_for = request.headers.get("x-forwarded-for", "").strip()
            if forwarded_for:
                for candidate in forwarded_for.split(","):
                    client_ip = candidate.strip()
                    try:
                        return str(ipaddress.ip_address(client_ip))
                    except ValueError:
                        continue
            real_ip = request.headers.get("x-real-ip", "").strip()
            if real_ip:
                try:
                    return str(ipaddress.ip_address(real_ip))
                except ValueError:
                    pass
        return str(peer_ip)

    if peer_host:
        return peer_host
    return "unknown"


async def _check_auth_rate_limit(request: Request, *, now: float | None = None) -> None:
    await _auth_rate_limiter.check(_auth_client_key(request), now=now)


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await _check_auth_rate_limit(request)
    existing = await db.execute(
        select(User).where(
            (func.lower(User.email) == payload.email) | (User.username == payload.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    settings = get_settings()
    access_token = create_access_token(user.id, settings.jwt_secret)
    refresh_token = create_refresh_token(user.id, settings.jwt_secret)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await _check_auth_rate_limit(request)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    settings = get_settings()
    access_token = create_access_token(user.id, settings.jwt_secret)
    refresh_token = create_refresh_token(user.id, settings.jwt_secret)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await _check_auth_rate_limit(request)
    settings = get_settings()
    user_id = decode_refresh_token(payload.refresh_token, settings.jwt_secret)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    revoked = await db.execute(
        select(RevokedToken).where(RevokedToken.token_hash == _hash_token(payload.refresh_token))
    )
    if revoked.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    await _revoke_refresh_token(db, refresh_token=payload.refresh_token)
    new_access = create_access_token(user.id, settings.jwt_secret)
    new_refresh = create_refresh_token(user.id, settings.jwt_secret)
    await db.commit()
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a refresh token. Requires a valid access token."""
    user_id = decode_refresh_token(payload.refresh_token, get_settings().jwt_secret)
    if user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token does not belong to the current user",
        )
    now = datetime.now(timezone.utc)
    await _revoke_refresh_token(
        db,
        refresh_token=payload.refresh_token,
        now=now,
    )
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user
