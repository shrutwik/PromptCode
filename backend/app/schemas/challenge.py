from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ChallengeBase(BaseModel):
    slug: str
    title: str
    description: str
    difficulty: str = "medium"
    category: str = "extraction"
    tags: list[str] = []
    company_context: str = ""
    input_format: str = "text"
    output_format: str = "json"
    constraints: dict[str, Any] | None = None
    sample_input: Any | None = None
    sample_output: Any | None = None


class ChallengeCreate(BaseModel):
    """Admin-only: includes config with ground truth and hidden test data."""

    slug: str
    title: str
    description: str
    difficulty: str = "medium"
    category: str = "extraction"
    tags: list[str] = []
    company_context: str = ""
    input_format: str = "text"
    output_format: str = "json"
    constraints: dict[str, Any] | None = None
    sample_input: Any | None = None
    sample_output: Any | None = None
    config: dict[str, Any] = {}


class ChallengeResponse(ChallengeBase):
    """Public response — never includes config (ground truth + hidden inputs)."""

    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChallengeListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    difficulty: str
    category: str
    tags: list[str]
    company_context: str
    created_at: datetime

    model_config = {"from_attributes": True}
