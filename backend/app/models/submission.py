from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending | running | completed | failed

    code: Mapped[str] = mapped_column(Text)
    entrypoint: Mapped[str] = mapped_column(String(256), default="main.py")

    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Scores (0.0 – 1.0)
    score_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_prompt_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_efficiency: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_reliability: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_orchestration: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_code_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_overall: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_llm_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
