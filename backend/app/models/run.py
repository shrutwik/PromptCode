from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID, JSONType


class Run(Base):
    """One execution of a submission inside the sandbox.

    A single submission triggers multiple runs (normal + adversarial).
    """

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    submission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("submissions.id"), index=True
    )
    run_type: Mapped[str] = mapped_column(String(32))
    run_index: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )

    output: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    telemetry: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)

    tokens_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retries: Mapped[int | None] = mapped_column(Integer, nullable=True)

    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
