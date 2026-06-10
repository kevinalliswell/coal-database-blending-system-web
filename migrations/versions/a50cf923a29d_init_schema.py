"""init schema

Revision ID: a50cf923a29d
Revises:
Create Date: 2026-04-24 10:57:14.521895

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a50cf923a29d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'coal_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('calorific_value', sa.Float(), nullable=False),
        sa.Column('ash_content', sa.Float(), nullable=False),
        sa.Column('volatile_matter', sa.Float(), nullable=False),
        sa.Column('fixed_carbon', sa.Float(), nullable=False),
        sa.Column('total_sulfur', sa.Float(), nullable=False),
        sa.Column('total_moisture', sa.Float(), nullable=True),
        sa.Column('air_dry_moisture', sa.Float(), nullable=True),
        sa.Column('supplier', sa.String(length=100), nullable=True),
        sa.Column('hgi', sa.Float(), nullable=True),
        sa.Column('burnout_rate', sa.Float(), nullable=True),
        sa.Column('carbon_content', sa.Float(), nullable=True),
        sa.Column('hydrogen_content', sa.Float(), nullable=True),
        sa.Column('nitrogen_content', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_coal_data_name'), 'coal_data', ['name'], unique=True)
    op.create_index(op.f('ix_coal_data_type'), 'coal_data', ['type'], unique=False)

    op.create_table(
        'optimization_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.String(length=20), nullable=False),
        sa.Column('coal_names', sa.Text(), nullable=False),
        sa.Column('optimal_ratios', sa.Text(), nullable=False),
        sa.Column('constraints', sa.Text(), nullable=False),
        sa.Column('total_price', sa.Float(), nullable=True),
        sa.Column('total_heat', sa.Float(), nullable=True),
        sa.Column('total_ash', sa.Float(), nullable=True),
        sa.Column('total_volatile', sa.Float(), nullable=True),
        sa.Column('total_fixed_carbon', sa.Float(), nullable=True),
        sa.Column('total_sulfur', sa.Float(), nullable=True),
        sa.Column('performance_price_ratio', sa.Float(), nullable=True),
        sa.Column('iterations', sa.Integer(), nullable=True),
        sa.Column('time_taken', sa.Float(), nullable=True),
        sa.Column('fitness_value', sa.Float(), nullable=True),
        sa.Column('constraints_satisfied', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_optimization_history_timestamp'),
        'optimization_history',
        ['timestamp'],
        unique=False,
    )

    op.create_table(
        'upload_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('saved_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('upload_time', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('processed', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('upload_files')
    op.drop_index(op.f('ix_optimization_history_timestamp'), table_name='optimization_history')
    op.drop_table('optimization_history')
    op.drop_index(op.f('ix_coal_data_type'), table_name='coal_data')
    op.drop_index(op.f('ix_coal_data_name'), table_name='coal_data')
    op.drop_table('coal_data')
