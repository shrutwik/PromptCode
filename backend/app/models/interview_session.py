from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import GUID, JSONType


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True, index=True
    )
    owner_token: Mapped[str] = mapped_column(String(64), index=True)
    challenge_slug: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    workspace_path: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    failed_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ai_request_count: Mapped[int] = mapped_column(Integer, default=0)
    test_run_count: Mapped[int] = mapped_column(Integer, default=0)
    runner_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    feedback_realism: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_meta: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    challenge_version: Mapped[str] = mapped_column(String(64), default="1")
    scoring_version: Mapped[str] = mapped_column(String(32), default="v1")
    abandon_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    wall_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    infra_blocked_ms: Mapped[int] = mapped_column(Integer, default=0)
    infra_failure_tags: Mapped[dict | list | None] = mapped_column(JSONType(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InterviewSessionEvent(Base):
    __tablename__ = "interview_session_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interview_sessions.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class InterviewSessionFile(Base):
    __tablename__ = "interview_session_files"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interview_sessions.id"), index=True
    )
    path: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InterviewAIMessage(Base):
    __tablename__ = "interview_ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interview_sessions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("interview_sessions.id"), unique=True, index=True
    )
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    rubric: Mapped[dict] = mapped_column(JSONType(), default=dict)
    metrics: Mapped[dict] = mapped_column(JSONType(), default=dict)
    insights: Mapped[list] = mapped_column(JSONType(), default=list)
    test_summary: Mapped[dict] = mapped_column(JSONType(), default=dict)
    defend_questions: Mapped[list] = mapped_column(JSONType(), default=list)
    scoring_version: Mapped[str] = mapped_column(String(32), default="v1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
