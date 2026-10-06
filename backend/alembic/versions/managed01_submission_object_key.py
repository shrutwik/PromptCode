"""Store the immutable submission's object key on the durable grading job.

Managed (Modal) workers run in ephemeral containers and cannot rely on the host
path recorded at submit time, so a job needs a provider-neutral way to find its
source. ``snapshot_key`` records ``submitted/<session_id>/<source_digest>`` — the
prefix of the immutable objects in the private bucket.

It is nullable so rows written before this revision keep resolving through
``snapshot_path`` (filesystem mode) or through ``source_digest`` (managed mode).
The guard mirrors ``audit04_job_queue_indexes``: a partially provisioned database
skips the missing table instead of failing the deploy.
"""
import sqlalchemy as sa

from alembic import op

revision = "managed01_submission_object_key"
down_revision = "audit04_job_queue_indexes"
branch_labels = None
depends_on = None

_JOBS = "interview_grading_jobs"


def upgrade():
    if _table_exists(_JOBS) and not _column_exists(_JOBS, "snapshot_key"):
        op.add_column(_JOBS, sa.Column("snapshot_key", sa.String(512), nullable=True))


def downgrade():
    if _table_exists(_JOBS) and _column_exists(_JOBS, "snapshot_key"):
        op.drop_column(_JOBS, "snapshot_key")


def _table_exists(table: str) -> bool:
    from sqlalchemy import inspect

    return table in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    from sqlalchemy import inspect

    return column in {item["name"] for item in inspect(op.get_bind()).get_columns(table)}
