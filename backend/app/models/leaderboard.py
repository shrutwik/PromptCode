from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeaderboardEntry(Base):
    """Denormalized view for fast leaderboard queries.

    Updated whenever a submission finishes evaluation.
    """

    __tablename__ = "leaderboard"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("challenges.id"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id"), unique=True
    )

    score_overall: Mapped[float] = mapped_column(Float, default=0.0)
    score_accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    score_prompt_quality: Mapped[float] = mapped_column(Float, default=0.0)
    score_efficiency: Mapped[float] = mapped_column(Float, default=0.0)
    score_reliability: Mapped[float] = mapped_column(Float, default=0.0)
    score_orchestration: Mapped[float] = mapped_column(Float, default=0.0)
    score_code_quality: Mapped[float] = mapped_column(Float, default=0.0)

    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_llm_calls: Mapped[int] = mapped_column(Integer, default=0)

    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
