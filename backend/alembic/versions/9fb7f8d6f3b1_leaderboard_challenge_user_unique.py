"""Add unique leaderboard constraint for challenge/user pairs.

Revision ID: 9fb7f8d6f3b1
Revises: d6536da6a345
Create Date: 2026-03-06 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9fb7f8d6f3b1"
down_revision = "d6536da6a345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    inspector = sa.inspect(bind)

    # Keep the highest-score row per (challenge_id, user_id) before adding uniqueness.
    op.execute(
        sa.text(
            """
            DELETE FROM leaderboard
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY challenge_id, user_id
                               ORDER BY score_overall DESC, updated_at DESC, id DESC
                           ) AS row_num
                    FROM leaderboard
                ) ranked
                WHERE ranked.row_num > 1
            )
            """
            )
    )

    unique_constraints = {
        uc["name"]: tuple(uc.get("column_names") or ())
        for uc in inspector.get_unique_constraints("leaderboard")
    }
    existing_indexes = {
        ix["name"]: tuple(ix.get("column_names") or ())
        for ix in inspector.get_indexes("leaderboard")
    }
    target_columns = ("challenge_id", "user_id")
    has_target_uniqueness = any(
        cols == target_columns for cols in unique_constraints.values()
    ) or any(cols == target_columns for cols in existing_indexes.values())

    if has_target_uniqueness:
        return

    if dialect_name == "sqlite":
        op.create_index(
            "uq_leaderboard_challenge_user",
            "leaderboard",
            ["challenge_id", "user_id"],
            unique=True,
        )
    else:
        op.create_unique_constraint(
            "uq_leaderboard_challenge_user",
            "leaderboard",
            ["challenge_id", "user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.drop_index("uq_leaderboard_challenge_user", table_name="leaderboard")
    else:
        op.drop_constraint("uq_leaderboard_challenge_user", "leaderboard", type_="unique")
