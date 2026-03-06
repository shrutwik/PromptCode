"""Add worker heartbeats for deployment readiness.

Revision ID: 6d16b920a3b4
Revises: 9fb7f8d6f3b1
Create Date: 2026-03-06 18:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "6d16b920a3b4"
down_revision = "9fb7f8d6f3b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "worker_heartbeats" not in existing:
        op.create_table(
            "worker_heartbeats",
            sa.Column("worker_id", sa.String(length=128), primary_key=True, nullable=False),
            sa.Column("hostname", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="idle"),
            sa.Column("current_job_id", sa.String(length=36), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        op.create_index("ix_worker_heartbeats_hostname", "worker_heartbeats", ["hostname"], unique=False)
        op.create_index("ix_worker_heartbeats_status", "worker_heartbeats", ["status"], unique=False)
        op.create_index("ix_worker_heartbeats_last_seen_at", "worker_heartbeats", ["last_seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
    op.drop_index("ix_worker_heartbeats_status", table_name="worker_heartbeats")
    op.drop_index("ix_worker_heartbeats_hostname", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
