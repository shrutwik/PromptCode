"""Atomic per-key fixed-window counters replace advisory locks and event scans."""
from alembic import op
import sqlalchemy as sa
revision='audit02_rate_counters'
down_revision=('audit01_ai_budgets', 'c4d5e6f7a8b9')
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('rate_limit_counters',sa.Column('key',sa.String(128),primary_key=True),
                    sa.Column('window_start',sa.BigInteger(),primary_key=True),sa.Column('count',sa.Integer(),nullable=False),
                    sa.Column('expires_at',sa.BigInteger(),nullable=False))
    op.create_index('ix_rate_limit_counters_expires_at','rate_limit_counters',['expires_at'])


def downgrade():
    op.drop_table('rate_limit_counters')
