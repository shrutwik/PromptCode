"""Add shared auth rate limit events table.

Revision ID: cc4f663b8b7f
Revises: 6d16b920a3b4
Create Date: 2026-03-06 21:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "cc4f663b8b7f"
down_revision = "6d16b920a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "auth_rate_limit_events" not in existing:
        op.create_table(
            "auth_rate_limit_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("client_key", sa.String(length=128), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_auth_rate_limit_events_client_key",
            "auth_rate_limit_events",
            ["client_key"],
            unique=False,
        )
        op.create_index(
            "ix_auth_rate_limit_events_created_at",
            "auth_rate_limit_events",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limit_events_created_at", table_name="auth_rate_limit_events")
    op.drop_index("ix_auth_rate_limit_events_client_key", table_name="auth_rate_limit_events")
    op.drop_table("auth_rate_limit_events")
