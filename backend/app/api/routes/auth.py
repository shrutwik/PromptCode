from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip_from_request
from app.core.config import get_settings
from app.core.deps import (
    ACCESS_COOKIE,
    _extract_access_token,
    bearer_scheme,
    get_current_user,
)
from app.core.ratelimit import enforce_rate_limit, limit_from_env
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
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
    ForgotPasswordRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.password_reset import (
    FORGOT_PASSWORD_MESSAGE,
    PASSWORD_UPDATED_MESSAGE,
    ResetTokenError,
    issue_password_reset,
    notify_password_reset,
    password_reset_delivery_available,
    reset_password_with_token,
)
from app.services.interview.analytics import track_event
from app.services.interview.beta_access import consume_invite_or_allowlist

router = APIRouter()

_AUTH_RATE_WINDOW = 60  # seconds
_AUTH_RATE_LIMIT = limit_from_env("PROMPTCODE_AUTH_RATE_LIMIT", 120)
REFRESH_COOKIE = "pc_refresh_token"


def _set_auth_cookies(response: Response, *, access: str, refresh: str) -> None:
    settings = get_settings()
    if not settings.auth_cookie_enabled:
        return
    common = {
        "httponly": True,
        "secure": bool(settings.auth_cookie_secure),
        "samesite": settings.auth_cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def _hash_token(token: str) -> str:
    """SHA-256 hex digest of a raw token string (64 chars)."""
    return hashlib.sha256(token.encode()).hexdigest()


async def _revoke_access_token(
    db: AsyncSession,
    *,
    access_token: str,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    token_hash = _hash_token(access_token)
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    existing = await db.execute(
        select(RevokedToken).where(RevokedToken.token_hash == token_hash)
    )
    if existing.scalar_one_or_none() is None:
        db.add(RevokedToken(token_hash=token_hash, expires_at=expires_at))


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
    return client_ip_from_request(request)


async def _check_auth_rate_limit(
    request: Request,
    *,
    db: AsyncSession,
    now: datetime | None = None,
    identity: str | None = None,
) -> None:
    await enforce_rate_limit(
        db=db,
        key=f"auth:{_auth_client_key(request)}",
        limit=_AUTH_RATE_LIMIT,
        window_seconds=_AUTH_RATE_WINDOW,
        now=now,
    )
    if identity:
        import hmac
        digest = hmac.new(get_settings().jwt_secret.encode(), identity.lower().encode(), hashlib.sha256).hexdigest()
        await enforce_rate_limit(db=db, key="auth-account:" + digest, limit=10,
                                 window_seconds=_AUTH_RATE_WINDOW, now=now)


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(
    payload: UserCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await _check_auth_rate_limit(request, db=db, identity=payload.email)
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

    invite, cohort, signup_source = await consume_invite_or_allowlist(
        db,
        email=payload.email,
        invite_code=payload.invite_code,
    )

    display = (payload.first_name or payload.username or "").strip()
    user = User(
        email=payload.email,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        display_name=display,
        password_hash=hash_password(payload.password),
        beta_status="active",
        beta_cohort=cohort,
        signup_source=signup_source,
        invite_code_id=invite.id if invite else None,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await track_event(
        db,
        event_name="user_signed_up",
        user_id=user.id,
        properties={"signup_source": signup_source, "cohort": cohort},
        commit=True,
    )

    settings = get_settings()
    access_token = create_access_token(user.id, settings.jwt_secret)
    refresh_token = create_refresh_token(user.id, settings.jwt_secret)
    _set_auth_cookies(response, access=access_token, refresh=refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    await _check_auth_rate_limit(request, db=db, identity=payload.email)
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if (user.beta_status or "active") == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await track_event(db, event_name="logged_in", user_id=user.id, commit=False)
    settings = get_settings()
    access_token = create_access_token(user.id, settings.jwt_secret)
    refresh_token = create_refresh_token(user.id, settings.jwt_secret)
    await db.commit()
    await db.refresh(user)
    _set_auth_cookies(response, access=access_token, refresh=refresh_token)
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
    await _check_auth_rate_limit(request, db=db)
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
    if (user.beta_status or "active") == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    payload: LogoutRequest,
    request: Request,
    response: Response,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke the caller's refresh token and the access token used for this call."""
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
    access_token = _extract_access_token(request, creds)
    if access_token:
        await _revoke_access_token(db, access_token=access_token, now=now)
    await db.commit()
    _clear_auth_cookies(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await _check_auth_rate_limit(request, db=db)
    body: dict[str, str] = {"message": FORGOT_PASSWORD_MESSAGE}
    if not password_reset_delivery_available():
        return body
    result = await db.execute(select(User).where(func.lower(User.email) == payload.email))
    user = result.scalar_one_or_none()
    if user is not None:
        raw_token = await issue_password_reset(db, user)
        await notify_password_reset(user.email, raw_token)
    return body


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await _check_auth_rate_limit(request, db=db)
    try:
        await reset_password_with_token(
            db,
            raw_token=payload.token,
            new_password=payload.new_password,
        )
    except ResetTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from None
    return {"message": PASSWORD_UPDATED_MESSAGE}
