"""Frozen grading jobs and human review/appeal history."""
from alembic import op
import sqlalchemy as sa
from app.db.types import GUID, JSONType
revision = 'audit03_interview_grading'
down_revision = 'audit02_rate_counters'
branch_labels = None
depends_on = None

def ident(name='id', fk=None, **kwargs):
    args = [GUID()]
    if fk: args.append(sa.ForeignKey(fk))
    return sa.Column(name, *args, **kwargs)

def created():
    return sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

def upgrade():
    op.create_table('interview_grading_jobs', ident(primary_key=True), ident('session_id','interview_sessions.id',nullable=False,unique=True),
        sa.Column('source_digest',sa.String(64),nullable=False),sa.Column('snapshot_path',sa.String(512),nullable=False),
        sa.Column('snapshot_manifest',JSONType(),nullable=False),sa.Column('challenge_slug',sa.String(128),nullable=False),
        sa.Column('challenge_version',sa.String(64),nullable=False),sa.Column('status',sa.String(32),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('max_attempts',sa.Integer(),nullable=False),
        sa.Column('lease_token',sa.String(64)),sa.Column('lease_expires_at',sa.DateTime(timezone=True)),
        sa.Column('available_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),created(),
        sa.Column('started_at',sa.DateTime(timezone=True)),sa.Column('finished_at',sa.DateTime(timezone=True)),
        sa.Column('last_error',sa.Text()),sa.Column('result',JSONType()))
    op.create_index('ix_interview_grading_jobs_session_id','interview_grading_jobs',['session_id'],unique=True)
    op.create_index('ix_interview_grading_jobs_status','interview_grading_jobs',['status'])
    op.create_table('interview_grade_reviews',ident(primary_key=True),ident('session_id','interview_sessions.id',nullable=False),
        ident('reviewer_id','users.id',nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('packet_digest',sa.String(64),nullable=False),sa.Column('source_digest',sa.String(64),nullable=False),
        sa.Column('review',JSONType(),nullable=False),sa.Column('outcome',JSONType(),nullable=False),
        ident('supersedes_id','interview_grade_reviews.id'),created(),
        sa.UniqueConstraint('session_id','revision',name='uq_grade_review_revision'))
    op.create_index('ix_interview_grade_reviews_session_id','interview_grade_reviews',['session_id'])
    op.create_table('interview_grade_appeals',ident(primary_key=True),ident('session_id','interview_sessions.id',nullable=False),
        ident('review_id','interview_grade_reviews.id',nullable=False),ident('candidate_id','users.id',nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),sa.Column('status',sa.String(32),nullable=False),created(),
        sa.UniqueConstraint('review_id',name='uq_grade_appeal_review'))
    op.create_index('ix_interview_grade_appeals_session_id','interview_grade_appeals',['session_id'])
    op.create_table('interview_appeal_decisions',ident(primary_key=True),ident('appeal_id','interview_grade_appeals.id',nullable=False,unique=True),
        ident('reviewer_id','users.id',nullable=False),sa.Column('disposition',sa.String(32),nullable=False),
        sa.Column('reason',sa.Text(),nullable=False),created())

def downgrade():
    for name in ('interview_appeal_decisions','interview_grade_appeals','interview_grade_reviews','interview_grading_jobs'):
        op.drop_table(name)
