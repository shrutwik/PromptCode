"""Add optional users.role for interviewer answer guides.

Revision ID: c4d5e6f7a8b9
Revises: b7e1c4a9d2f0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b7e1c4a9d2f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "role" not in cols:
        op.add_column("users", sa.Column("role", sa.String(length=32), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "users" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("users")}
    if "role" in cols:
        op.drop_column("users", "role")
