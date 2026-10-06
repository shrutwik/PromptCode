"""Index the durable job queues for claim, lease recovery and age metrics.

`claim_next_job` filters on status + available_at and orders by created_at, and
`operational_metrics` reads the oldest queued row and counts expired leases. None
of those had a supporting index, so each poll and scrape scanned the table.

Index creation here is intentionally plain (not CONCURRENTLY): Alembic runs this
revision inside a transaction at deploy time and the tables are small relative to
a live grading queue. Creating them concurrently would require autocommit and an
online round-trip outside the migration, which this deployment does not support.
"""
from alembic import op

revision = "audit04_job_queue_indexes"
down_revision = "audit03_interview_grading"
branch_labels = None
depends_on = None

_INDEXES = (
    ("ix_interview_grading_jobs_status_available", "interview_grading_jobs", ["status", "available_at"]),
    ("ix_interview_grading_jobs_status_lease", "interview_grading_jobs", ["status", "lease_expires_at"]),
    ("ix_interview_grading_jobs_created_at", "interview_grading_jobs", ["created_at"]),
    ("ix_evaluation_jobs_status_available", "evaluation_jobs", ["status", "available_at"]),
)


def upgrade():
    for name, table, columns in _INDEXES:
        # Tables come from earlier revisions; skip any that are absent so this
        # revision stays safe on a partially provisioned database.
        if not _table_exists(table):
            continue
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _columns in _INDEXES:
        if _table_exists(table):
            op.drop_index(name, table_name=table)


def _table_exists(table: str) -> bool:
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    return table in inspector.get_table_names()
