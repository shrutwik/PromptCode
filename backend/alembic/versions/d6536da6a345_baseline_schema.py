"""baseline schema

Revision ID: d6536da6a345
Revises: 
Create Date: 2026-03-02 15:11:04.176758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6536da6a345'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("email", sa.String(length=256), nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("first_name", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("last_name", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("password_hash", sa.String(length=256), nullable=False),
            sa.Column("bio", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    if "challenges" not in existing:
        op.create_table(
            "challenges",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("slug", sa.String(length=128), nullable=False),
            sa.Column("title", sa.String(length=256), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("difficulty", sa.String(length=32), nullable=False, server_default="medium"),
            sa.Column("category", sa.String(length=64), nullable=False, server_default="extraction"),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("company_context", sa.Text(), nullable=False, server_default=""),
            sa.Column("input_format", sa.String(length=32), nullable=False, server_default="text"),
            sa.Column("output_format", sa.String(length=32), nullable=False, server_default="json"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("sample_input", sa.JSON(), nullable=True),
            sa.Column("sample_output", sa.JSON(), nullable=True),
            sa.Column("constraints", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_challenges_slug", "challenges", ["slug"], unique=True)
        op.create_index("ix_challenges_category", "challenges", ["category"], unique=False)

    if "submissions" not in existing:
        op.create_table(
            "submissions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("challenge_id", sa.String(length=36), sa.ForeignKey("challenges.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("code", sa.Text(), nullable=False),
            sa.Column("entrypoint", sa.String(length=256), nullable=False, server_default="main.py"),
            sa.Column("report", sa.JSON(), nullable=True),
            sa.Column("score_accuracy", sa.Float(), nullable=True),
            sa.Column("score_prompt_quality", sa.Float(), nullable=True),
            sa.Column("score_efficiency", sa.Float(), nullable=True),
            sa.Column("score_reliability", sa.Float(), nullable=True),
            sa.Column("score_orchestration", sa.Float(), nullable=True),
            sa.Column("score_code_quality", sa.Float(), nullable=True),
            sa.Column("score_rule_adherence", sa.Float(), nullable=True),
            sa.Column("score_edge_cases", sa.Float(), nullable=True),
            sa.Column("score_overall", sa.Float(), nullable=True),
            sa.Column("delta_overall", sa.Float(), nullable=True),
            sa.Column("delta_accuracy", sa.Float(), nullable=True),
            sa.Column("delta_robustness", sa.Float(), nullable=True),
            sa.Column("delta_efficiency", sa.Float(), nullable=True),
            sa.Column("growth_score", sa.Float(), nullable=True),
            sa.Column("mastery_state", sa.String(length=24), nullable=True),
            sa.Column("total_cost_usd", sa.Float(), nullable=True),
            sa.Column("total_latency_ms", sa.Float(), nullable=True),
            sa.Column("total_llm_calls", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_submissions_challenge_id", "submissions", ["challenge_id"], unique=False)
        op.create_index("ix_submissions_user_id", "submissions", ["user_id"], unique=False)
    else:
        submission_columns = {c["name"] for c in inspector.get_columns("submissions")}
        if "delta_overall" not in submission_columns:
            op.add_column("submissions", sa.Column("delta_overall", sa.Float(), nullable=True))
        if "delta_accuracy" not in submission_columns:
            op.add_column("submissions", sa.Column("delta_accuracy", sa.Float(), nullable=True))
        if "delta_robustness" not in submission_columns:
            op.add_column("submissions", sa.Column("delta_robustness", sa.Float(), nullable=True))
        if "delta_efficiency" not in submission_columns:
            op.add_column("submissions", sa.Column("delta_efficiency", sa.Float(), nullable=True))
        if "growth_score" not in submission_columns:
            op.add_column("submissions", sa.Column("growth_score", sa.Float(), nullable=True))
        if "mastery_state" not in submission_columns:
            op.add_column("submissions", sa.Column("mastery_state", sa.String(length=24), nullable=True))

    if "runs" not in existing:
        op.create_table(
            "runs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("submission_id", sa.String(length=36), sa.ForeignKey("submissions.id"), nullable=False),
            sa.Column("run_type", sa.String(length=32), nullable=False),
            sa.Column("run_index", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("output", sa.JSON(), nullable=True),
            sa.Column("telemetry", sa.JSON(), nullable=True),
            sa.Column("tokens_total", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("llm_calls", sa.Integer(), nullable=True),
            sa.Column("retries", sa.Integer(), nullable=True),
            sa.Column("accuracy", sa.Float(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_runs_submission_id", "runs", ["submission_id"], unique=False)

    if "leaderboard" not in existing:
        op.create_table(
            "leaderboard",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("challenge_id", sa.String(length=36), sa.ForeignKey("challenges.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("submission_id", sa.String(length=36), sa.ForeignKey("submissions.id"), nullable=False),
            sa.Column("score_overall", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_accuracy", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_prompt_quality", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_efficiency", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_reliability", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_orchestration", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_code_quality", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_rule_adherence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("score_edge_cases", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_llm_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rank", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("submission_id", name="uq_leaderboard_submission_id"),
        )
        op.create_index("ix_leaderboard_challenge_id", "leaderboard", ["challenge_id"], unique=False)
        op.create_index("ix_leaderboard_user_id", "leaderboard", ["user_id"], unique=False)

    if "evaluation_jobs" not in existing:
        op.create_table(
            "evaluation_jobs",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("submission_id", sa.String(length=36), sa.ForeignKey("submissions.id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("submission_id", name="uq_evaluation_jobs_submission_id"),
        )
        op.create_index("ix_evaluation_jobs_status", "evaluation_jobs", ["status"], unique=False)
        op.create_index("ix_evaluation_jobs_available_at", "evaluation_jobs", ["available_at"], unique=False)
        op.create_index("ix_evaluation_jobs_submission_id", "evaluation_jobs", ["submission_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_evaluation_jobs_submission_id", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_available_at", table_name="evaluation_jobs")
    op.drop_index("ix_evaluation_jobs_status", table_name="evaluation_jobs")
    op.drop_table("evaluation_jobs")

    op.drop_index("ix_leaderboard_user_id", table_name="leaderboard")
    op.drop_index("ix_leaderboard_challenge_id", table_name="leaderboard")
    op.drop_table("leaderboard")

    op.drop_index("ix_runs_submission_id", table_name="runs")
    op.drop_table("runs")

    op.drop_index("ix_submissions_user_id", table_name="submissions")
    op.drop_index("ix_submissions_challenge_id", table_name="submissions")
    op.drop_table("submissions")

    op.drop_index("ix_challenges_category", table_name="challenges")
    op.drop_index("ix_challenges_slug", table_name="challenges")
    op.drop_table("challenges")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
