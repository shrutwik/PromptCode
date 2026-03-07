from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.auth_rate_limit import AuthRateLimitEvent
from app.models.user import User
from app.schemas.user import (
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


def _auth_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _check_auth_rate_limit(request: Request, db: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=_AUTH_RATE_WINDOW)
    client_ip = _auth_client_key(request)
    await db.execute(
        delete(AuthRateLimitEvent).where(
            AuthRateLimitEvent.client_key == client_ip,
            AuthRateLimitEvent.created_at < cutoff,
        )
    )
    count_result = await db.execute(
        select(func.count())
        .select_from(AuthRateLimitEvent)
        .where(AuthRateLimitEvent.client_key == client_ip)
    )
    attempt_count = int(count_result.scalar_one() or 0)
    if attempt_count >= _AUTH_RATE_LIMIT:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
            headers={"Retry-After": str(_AUTH_RATE_WINDOW)},
        )
    db.add(AuthRateLimitEvent(client_key=client_ip))
    await db.commit()


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    payload: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await _check_auth_rate_limit(request, db)
    existing = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.username)
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
):
    await _check_auth_rate_limit(request, db)
    result = await db.execute(select(User).where(User.email == payload.email))
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
):
    await _check_auth_rate_limit(request, db)
    settings = get_settings()
    user_id = decode_refresh_token(payload.refresh_token, settings.jwt_secret)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    new_access = create_access_token(user.id, settings.jwt_secret)
    new_refresh = create_refresh_token(user.id, settings.jwt_secret)
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user
