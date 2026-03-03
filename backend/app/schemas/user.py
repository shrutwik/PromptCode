from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    first_name: str = ""
    last_name: str = ""
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None


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
    id: uuid.UUID
    username: str
    first_name: str
    last_name: str
    bio: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
