"""Preserve legacy assays and record their unknown analysis bases.

Revision ID: c8a1d24f5e67
Revises: b3f7b0d5f1a2
"""

from alembic import op
import sqlalchemy as sa

revision = 'c8a1d24f5e67'
down_revision = 'b3f7b0d5f1a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('coal_data') as batch:
        for field in ('analysis_basis', 'calorific_basis', 'price_basis', 'calorific_type'):
            batch.add_column(sa.Column(field, sa.String(16), nullable=False, server_default='unknown'))


def downgrade():
    with op.batch_alter_table('coal_data') as batch:
        for field in ('calorific_type', 'price_basis', 'calorific_basis', 'analysis_basis'):
            batch.drop_column(field)
