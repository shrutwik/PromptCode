from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuthRateLimitEvent(Base):
    __tablename__ = "auth_rate_limit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
