"""Durable grading jobs and append-only human review decisions."""
from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.types import GUID, JSONType

class InterviewGradingJob(Base):
    __tablename__ = "interview_grading_jobs"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("interview_sessions.id"), unique=True, index=True)
    source_digest: Mapped[str] = mapped_column(String(64))
    snapshot_path: Mapped[str] = mapped_column(String(512))
    snapshot_manifest: Mapped[dict] = mapped_column(JSONType(), default=dict)
    challenge_slug: Mapped[str] = mapped_column(String(128))
    challenge_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)

class InterviewGradeReview(Base):
    __tablename__ = "interview_grade_reviews"
    __table_args__ = (UniqueConstraint("session_id", "revision", name="uq_grade_review_revision"),)
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("interview_sessions.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    revision: Mapped[int] = mapped_column(Integer)
    packet_digest: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    review: Mapped[dict] = mapped_column(JSONType())
    outcome: Mapped[dict] = mapped_column(JSONType())
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("interview_grade_reviews.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class InterviewGradeAppeal(Base):
    __tablename__ = "interview_grade_appeals"
    __table_args__ = (UniqueConstraint("review_id", name="uq_grade_appeal_review"),)
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("interview_sessions.id"), index=True)
    review_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("interview_grade_reviews.id"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class InterviewAppealDecision(Base):
    __tablename__ = "interview_appeal_decisions"
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    appeal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("interview_grade_appeals.id"), unique=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    disposition: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
