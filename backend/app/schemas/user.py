from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, ValidationInfo, field_validator

from app.core.security import BCRYPT_PASSWORD_MAX_BYTES

_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,62}[A-Za-z0-9]$")
_MAX_NAME_CHARS = 128
_MAX_EMAIL_CHARS = 256
_MAX_BIO_CHARS = 500


def _normalize_name(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if len(normalized) > _MAX_NAME_CHARS:
        raise ValueError(f"{field_name} must be at most {_MAX_NAME_CHARS} characters long.")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip()


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    first_name: str = ""
    last_name: str = ""
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) > _MAX_EMAIL_CHARS:
            raise ValueError(f"Email must be at most {_MAX_EMAIL_CHARS} characters long.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("Password must be at least 12 characters long.")
        if len(value.encode("utf-8")) > BCRYPT_PASSWORD_MAX_BYTES:
            raise ValueError(
                f"Password must be at most {BCRYPT_PASSWORD_MAX_BYTES} bytes long."
            )
        if not any(char.islower() for char in value):
            raise ValueError("Password must include a lowercase letter.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must include an uppercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must include a number.")
        if not any(not char.isalnum() for char in value):
            raise ValueError("Password must include a symbol.")
        return value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = value.strip()
        if not _USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Username must be 3-64 characters and use only letters, numbers, underscores, or hyphens."
            )
        return normalized

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name_fields(cls, value: str, info: ValidationInfo) -> str:
        field_name = (info.field_name or "name").replace("_", " ")
        return _normalize_name(value, field_name=field_name)


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        normalized = str(value).strip().lower()
        if len(normalized) > _MAX_EMAIL_CHARS:
            raise ValueError(f"Email must be at most {_MAX_EMAIL_CHARS} characters long.")
        return normalized


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_updated_name_fields(
        cls,
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        if value is None:
            return None
        field_name = (info.field_name or "name").replace("_", " ")
        return _normalize_name(value, field_name=field_name)

    @field_validator("bio")
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        normalized = _normalize_optional_text(value)
        if normalized is not None and len(normalized) > _MAX_BIO_CHARS:
            raise ValueError(f"Bio must be at most {_MAX_BIO_CHARS} characters long.")
        return normalized


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    first_name: str
    last_name: str
    bio: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublicResponse(BaseModel):
    username: str
    first_name: str
    last_name: str
    bio: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileStatsResponse(BaseModel):
    total_submissions: int
    challenges_solved: int
    total_challenges: int
    avg_score: float
    avg_accuracy: float
    avg_efficiency: float
    avg_reliability: float
    avg_orchestration: float
    avg_growth_score: float
    total_cost_usd: float
    avg_latency_ms: float


class UserProfileSubmissionResponse(BaseModel):
    id: uuid.UUID
    challenge_id: uuid.UUID
    challenge_title: str
    status: str
    score_overall: float | None = None
    growth_score: float | None = None
    total_cost_usd: float | None = None
    created_at: datetime | None = None


class UserProfileResponse(BaseModel):
    user: UserPublicResponse
    stats: UserProfileStatsResponse
    recent_submissions: list[UserProfileSubmissionResponse]


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    user: UserResponse
