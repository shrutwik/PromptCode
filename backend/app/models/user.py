from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    last_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    bio: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
