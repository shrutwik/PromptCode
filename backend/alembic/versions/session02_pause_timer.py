"""Persist paused practice time and a single editor lease."""
import sqlalchemy as sa
from alembic import op

revision = "session02_pause_timer"
down_revision = "managed01_submission_object_key"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interview_sessions", sa.Column("timer_elapsed_ms", sa.Integer(), nullable=True))
    op.add_column("interview_sessions", sa.Column("timer_last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interview_sessions", sa.Column("timer_editor_token", sa.String(64), nullable=True))
    # Preserve the old displayed duration at rollout, then resume unfinished rows paused.
    sessions = sa.table("interview_sessions",
        sa.column("timer_elapsed_ms", sa.Integer), sa.column("active_duration_ms", sa.Integer),
        sa.column("started_at", sa.DateTime), sa.column("submitted_at", sa.DateTime),
        sa.column("expires_at", sa.DateTime))
    now = sa.func.current_timestamp()
    end = sa.func.coalesce(sessions.c.submitted_at,
        sa.case((sessions.c.expires_at < now, sessions.c.expires_at), else_=now))
    if op.get_bind().dialect.name == "sqlite":
        duration = (sa.func.julianday(end) - sa.func.julianday(sessions.c.started_at)) * 86400000
    else:
        duration = sa.extract("epoch", end - sessions.c.started_at) * 1000
    duration = sa.cast(sa.case((duration < 0, 0), else_=duration), sa.Integer)
    op.execute(sessions.update().values(timer_elapsed_ms=sa.func.coalesce(
        sessions.c.active_duration_ms, duration, 0)))


def downgrade():
    for column in ("timer_editor_token", "timer_last_seen_at", "timer_elapsed_ms"):
        op.drop_column("interview_sessions", column)
