"""Persistent AI request/token/cost reservations."""
from alembic import op
import sqlalchemy as sa
revision='audit01_ai_budgets'
down_revision='a0b1c2d3e4f5'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('ai_budgets',sa.Column('key',sa.String(160),primary_key=True),
                    sa.Column('requests',sa.Integer(),nullable=False),sa.Column('tokens',sa.BigInteger(),nullable=False),
                    sa.Column('cost_micros',sa.BigInteger(),nullable=False))


def downgrade():
    op.drop_table('ai_budgets')
