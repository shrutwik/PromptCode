from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID, JSONType


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(32), default="medium")
    category: Mapped[str] = mapped_column(String(64), default="extraction", index=True)
    tags: Mapped[list[str]] = mapped_column(JSONType(), default=list)
    company_context: Mapped[str] = mapped_column(Text, default="")
    input_format: Mapped[str] = mapped_column(String(32), default="text")
    output_format: Mapped[str] = mapped_column(String(32), default="json")
    version: Mapped[int] = mapped_column(Integer, default=1)

    config: Mapped[dict] = mapped_column(JSONType(), default=dict)

    sample_input: Mapped[dict | list | None] = mapped_column(JSONType(), nullable=True)
    sample_output: Mapped[dict | list | None] = mapped_column(JSONType(), nullable=True)

    constraints: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
