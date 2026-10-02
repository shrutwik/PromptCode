"""Add private-beta invite, analytics, review, and version columns.

Revision ID: a0b1c2d3e4f5
Revises: f8a9b0c1d2e3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "invite_codes" not in tables:
        op.create_table(
            "invite_codes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("cohort", sa.String(64), server_default="beta", nullable=False),
            sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
            sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.String(128), nullable=True),
            sa.Column("note", sa.String(256), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("ix_invite_codes_code", "invite_codes", ["code"], unique=True)

    if "product_analytics_events" not in tables:
        op.create_table(
            "product_analytics_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("event_name", sa.String(64), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("session_id", sa.String(36), nullable=True),
            sa.Column("challenge_slug", sa.String(128), nullable=True),
            sa.Column("properties", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("ix_product_analytics_events_event_name", "product_analytics_events", ["event_name"])
        op.create_index("ix_product_analytics_events_user_id", "product_analytics_events", ["user_id"])
        op.create_index("ix_product_analytics_events_session_id", "product_analytics_events", ["session_id"])
        op.create_index("ix_product_analytics_events_challenge_slug", "product_analytics_events", ["challenge_slug"])
        op.create_index("ix_product_analytics_events_created_at", "product_analytics_events", ["created_at"])

    if "human_reviews" not in tables:
        op.create_table(
            "human_reviews",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "session_id",
                sa.String(36),
                sa.ForeignKey("interview_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("reviewer", sa.String(128), server_default="internal", nullable=False),
            sa.Column("notes", sa.Text(), server_default="", nullable=False),
            sa.Column("category_observations", sa.JSON(), nullable=True),
            sa.Column("disagreement", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("observed_difficulty", sa.String(32), nullable=True),
            sa.Column("observed_time_minutes", sa.Float(), nullable=True),
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
        op.create_index("ix_human_reviews_session_id", "human_reviews", ["session_id"])

    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "beta_cohort" not in cols:
            op.add_column(
                "users",
                sa.Column("beta_cohort", sa.String(64), server_default="open", nullable=False),
            )
        if "signup_source" not in cols:
            op.add_column(
                "users",
                sa.Column("signup_source", sa.String(64), server_default="direct", nullable=False),
            )
        if "invite_code_id" not in cols:
            op.add_column(
                "users",
                sa.Column("invite_code_id", sa.String(36), nullable=True),
            )

    if "interview_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("interview_sessions")}
        if "challenge_version" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("challenge_version", sa.String(64), server_default="1", nullable=False),
            )
        if "scoring_version" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("scoring_version", sa.String(32), server_default="v1", nullable=False),
            )
        if "abandon_reason" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("abandon_reason", sa.String(256), nullable=True),
            )
        if "wall_duration_ms" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("wall_duration_ms", sa.Integer(), nullable=True),
            )
        if "active_duration_ms" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("active_duration_ms", sa.Integer(), nullable=True),
            )
        if "infra_blocked_ms" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("infra_blocked_ms", sa.Integer(), server_default="0", nullable=False),
            )
        if "infra_failure_tags" not in cols:
            op.add_column(
                "interview_sessions",
                sa.Column("infra_failure_tags", sa.JSON(), nullable=True),
            )

    if "interview_evaluations" in tables:
        cols = {c["name"] for c in inspector.get_columns("interview_evaluations")}
        if "scoring_version" not in cols:
            op.add_column(
                "interview_evaluations",
                sa.Column("scoring_version", sa.String(32), server_default="v1", nullable=False),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "interview_evaluations" in tables:
        cols = {c["name"] for c in inspector.get_columns("interview_evaluations")}
        if "scoring_version" in cols:
            op.drop_column("interview_evaluations", "scoring_version")

    if "interview_sessions" in tables:
        cols = {c["name"] for c in inspector.get_columns("interview_sessions")}
        for col in (
            "infra_failure_tags",
            "infra_blocked_ms",
            "active_duration_ms",
            "wall_duration_ms",
            "abandon_reason",
            "scoring_version",
            "challenge_version",
        ):
            if col in cols:
                op.drop_column("interview_sessions", col)

    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        for col in ("invite_code_id", "signup_source", "beta_cohort"):
            if col in cols:
                op.drop_column("users", col)

    if "human_reviews" in tables:
        op.drop_index("ix_human_reviews_session_id", table_name="human_reviews")
        op.drop_table("human_reviews")
    if "product_analytics_events" in tables:
        op.drop_table("product_analytics_events")
    if "invite_codes" in tables:
        op.drop_index("ix_invite_codes_code", table_name="invite_codes")
        op.drop_table("invite_codes")
