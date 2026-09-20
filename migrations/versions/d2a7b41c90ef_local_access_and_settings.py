"""Local accounts, revocable sessions and versioned calculation settings.

Revision ID: d2a7b41c90ef
Revises: c8a1d24f5e67
"""
from alembic import op
import sqlalchemy as sa

revision = 'd2a7b41c90ef'
down_revision = 'c8a1d24f5e67'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('app_user',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False, unique=True),
        sa.Column('display_name', sa.String(80), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(24), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False))
    op.create_table('auth_session',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('csrf_token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False))
    op.create_index('ix_auth_session_user_id', 'auth_session', ['user_id'])
    op.create_index('ix_auth_session_expires_at', 'auth_session', ['expires_at'])
    state = op.create_table('access_state',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('initialized', sa.Boolean(), nullable=False),
        sa.Column('lock_version', sa.Integer(), nullable=False))
    settings = op.create_table('system_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False))
    op.create_table('login_attempt',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('window_start', sa.Integer(), nullable=False))
    op.bulk_insert(state, [{'id': 1, 'initialized': False, 'lock_version': 0}])
    op.bulk_insert(settings, [{'id': 1, 'version': 1, 'payload': {
        'system_name': 'CBOS 煤炭智能配煤系统', 'organization': '',
        'ratio_basis': 'ar', 'heat_type': 'net_v', 'heat_unit': 'MJ/kg',
        'constraints': {'heat_min': 6000, 'heat_max': 7800, 'ash_min': 0, 'ash_max': 20,
                        'volatile_min': 8, 'volatile_max': 40, 'fixed_carbon_min': 50,
                        'fixed_carbon_max': 85, 'sulfur_min': 0, 'sulfur_max': 1.2,
                        'price_min': 0, 'price_max': 1500},
        'ga_params': {'population_size': 500, 'max_generations': 3000, 'mutation_rate': .2,
                      'crossover_rate': .85, 'tournament_size': 7, 'early_stopping_patience': 200,
                      'adaptive_mutation': True, 'convergence_threshold': 1e-6,
                      'pareto_solution_limit': 20}}}])


def downgrade():
    for table in ('login_attempt', 'system_settings', 'access_state', 'auth_session', 'app_user'):
        op.drop_table(table)
