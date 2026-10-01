"""Add interview simulation session tables.

Revision ID: e7f8a9b0c1d2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-18 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "interview_sessions" not in existing:
        op.create_table(
            "interview_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("owner_token", sa.String(length=64), nullable=False),
            sa.Column("challenge_slug", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("workspace_path", sa.String(length=512), nullable=False),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"])
        op.create_index("ix_interview_sessions_owner_token", "interview_sessions", ["owner_token"])
        op.create_index(
            "ix_interview_sessions_challenge_slug", "interview_sessions", ["challenge_slug"]
        )
        op.create_index("ix_interview_sessions_status", "interview_sessions", ["status"])

    if "interview_session_events" not in existing:
        op.create_table(
            "interview_session_events",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "session_id",
                sa.String(length=36),
                sa.ForeignKey("interview_sessions.id"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_interview_session_events_session_id",
            "interview_session_events",
            ["session_id"],
        )
        op.create_index(
            "ix_interview_session_events_event_type",
            "interview_session_events",
            ["event_type"],
        )
        op.create_index(
            "ix_interview_session_events_created_at",
            "interview_session_events",
            ["created_at"],
        )

    if "interview_session_files" not in existing:
        op.create_table(
            "interview_session_files",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "session_id",
                sa.String(length=36),
                sa.ForeignKey("interview_sessions.id"),
                nullable=False,
            ),
            sa.Column("path", sa.String(length=512), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_interview_session_files_session_id",
            "interview_session_files",
            ["session_id"],
        )

    if "interview_ai_messages" not in existing:
        op.create_table(
            "interview_ai_messages",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "session_id",
                sa.String(length=36),
                sa.ForeignKey("interview_sessions.id"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("meta", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_interview_ai_messages_session_id",
            "interview_ai_messages",
            ["session_id"],
        )

    if "interview_evaluations" not in existing:
        op.create_table(
            "interview_evaluations",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "session_id",
                sa.String(length=36),
                sa.ForeignKey("interview_sessions.id"),
                nullable=False,
            ),
            sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("rubric", sa.JSON(), nullable=False),
            sa.Column("metrics", sa.JSON(), nullable=False),
            sa.Column("insights", sa.JSON(), nullable=False),
            sa.Column("test_summary", sa.JSON(), nullable=False),
            sa.Column("defend_questions", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_interview_evaluations_session_id",
            "interview_evaluations",
            ["session_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_table("interview_evaluations")
    op.drop_table("interview_ai_messages")
    op.drop_table("interview_session_files")
    op.drop_table("interview_session_events")
    op.drop_table("interview_sessions")
