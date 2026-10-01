"""Add beta user fields + interview session lifecycle columns.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "display_name" not in cols:
            op.add_column(
                "users",
                sa.Column("display_name", sa.String(length=128), server_default="", nullable=False),
            )
        if "last_login_at" not in cols:
            op.add_column(
                "users",
                sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "beta_status" not in cols:
            op.add_column(
                "users",
                sa.Column(
                    "beta_status",
                    sa.String(length=32),
                    server_default="active",
                    nullable=False,
                ),
            )

    if "interview_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("interview_sessions")}
        if "attempt_number" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("attempt_number", sa.Integer(), server_default="1", nullable=False),
            )
        if "expires_at" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            )
            op.create_index(
                "ix_interview_sessions_expires_at",
                "interview_sessions",
                ["expires_at"],
            )
        if "failed_reason" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("failed_reason", sa.String(length=256), nullable=True),
            )
        if "ai_request_count" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("ai_request_count", sa.Integer(), server_default="0", nullable=False),
            )
        if "test_run_count" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("test_run_count", sa.Integer(), server_default="0", nullable=False),
            )
        if "runner_duration_ms" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("runner_duration_ms", sa.Integer(), server_default="0", nullable=False),
            )
        if "feedback_realism" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("feedback_realism", sa.Integer(), nullable=True),
            )
        if "feedback_difficulty" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("feedback_difficulty", sa.Integer(), nullable=True),
            )
        if "feedback_text" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("feedback_text", sa.Text(), nullable=True),
            )
        if "feedback_meta" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("feedback_meta", sa.JSON(), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "interview_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("interview_sessions")}
        for col in (
            "feedback_meta",
            "feedback_text",
            "feedback_difficulty",
            "feedback_realism",
            "runner_duration_ms",
            "test_run_count",
            "ai_request_count",
            "failed_reason",
            "expires_at",
            "attempt_number",
        ):
            if col in cols:
                if col == "expires_at":
                    op.drop_index(
                        "ix_interview_sessions_expires_at",
                        table_name="interview_sessions",
                    )
                op.drop_column("interview_sessions", col)

    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        for col in ("beta_status", "last_login_at", "display_name"):
            if col in cols:
                op.drop_column("users", col)
