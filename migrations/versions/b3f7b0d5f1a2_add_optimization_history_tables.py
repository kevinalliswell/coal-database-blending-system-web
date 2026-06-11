"""add optimization history tables

Revision ID: b3f7b0d5f1a2
Revises: a50cf923a29d
Create Date: 2026-04-25 19:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3f7b0d5f1a2'
down_revision = 'a50cf923a29d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('optimization_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('request_payload', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('result_payload', sa.Text(), nullable=True))

    op.create_table(
        'replacement_ratio_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('calculation_type', sa.String(length=20), nullable=False),
        sa.Column('calculation_mode', sa.String(length=20), nullable=False),
        sa.Column('ratio_value', sa.Float(), nullable=False),
        sa.Column('parameter_summary', sa.Text(), nullable=False),
        sa.Column('request_payload', sa.Text(), nullable=True),
        sa.Column('result_payload', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('replacement_ratio_history')

    with op.batch_alter_table('optimization_history', schema=None) as batch_op:
        batch_op.drop_column('result_payload')
        batch_op.drop_column('request_payload')
