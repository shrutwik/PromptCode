"""Add password_reset_tokens for hashed single-use resets.

Revision ID: b7e1c4a9d2f0
Revises: a0b1c2d3e4f5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7e1c4a9d2f0"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "password_reset_tokens" not in existing:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_password_reset_tokens_user_id",
            "password_reset_tokens",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "ix_password_reset_tokens_token_hash",
            "password_reset_tokens",
            ["token_hash"],
            unique=True,
        )
        op.create_index(
            "ix_password_reset_tokens_expires_at",
            "password_reset_tokens",
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
