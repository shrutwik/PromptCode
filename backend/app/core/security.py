from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from authlib.jose import jwt
from authlib.jose.errors import JoseError

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes — refresh tokens handle session continuity
REFRESH_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: uuid.UUID, secret_key: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": int(expire.timestamp())}
    token_bytes = jwt.encode({"alg": ALGORITHM}, payload, secret_key)
    return token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes


def decode_access_token(token: str, secret_key: str) -> uuid.UUID | None:
    try:
        claims = jwt.decode(token, secret_key)
        claims.validate()
        user_id = claims.get("sub")
        if user_id is None:
            return None
        return uuid.UUID(user_id)
    except (JoseError, ValueError):
        return None


def create_refresh_token(user_id: uuid.UUID, secret_key: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": int(expire.timestamp()), "type": "refresh"}
    token_bytes = jwt.encode({"alg": ALGORITHM}, payload, secret_key)
    return token_bytes.decode("utf-8") if isinstance(token_bytes, bytes) else token_bytes


def decode_refresh_token(token: str, secret_key: str) -> uuid.UUID | None:
    """Decode a refresh token. Returns None if invalid, expired, or not a refresh token."""
    try:
        claims = jwt.decode(token, secret_key)
        claims.validate()
        if claims.get("type") != "refresh":
            return None
        user_id = claims.get("sub")
        if user_id is None:
            return None
        return uuid.UUID(user_id)
    except (JoseError, ValueError):
        return None
