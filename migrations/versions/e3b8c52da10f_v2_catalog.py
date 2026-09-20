"""Preserve legacy numbers in immutable batch assays; allow partial catalog rows.

Revision ID: e3b8c52da10f
Revises: d2a7b41c90ef
"""
from alembic import op
import sqlalchemy as sa

revision = 'e3b8c52da10f'
down_revision = 'd2a7b41c90ef'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('coal_data') as batch:
        for field in ('price', 'calorific_value', 'ash_content', 'volatile_matter', 'fixed_carbon', 'total_sulfur'):
            batch.alter_column(field, existing_type=sa.Float(), nullable=True)
        batch.add_column(sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()))
    batches = op.create_table('coal_batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('coal_id', sa.Integer(), sa.ForeignKey('coal_data.id'), nullable=False),
        sa.Column('code', sa.String(100), nullable=False),
        sa.Column('supplier', sa.String(100)), sa.Column('received_at', sa.String(40)),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('coal_id', 'code', name='uq_coal_batch_code'))
    op.create_index('ix_coal_batches_coal_id', 'coal_batches', ['coal_id'])
    assays = op.create_table('assay_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('coal_batches.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('raw', sa.JSON(), nullable=False),
        sa.Column('report_number', sa.String(120)), sa.Column('sampled_at', sa.String(40)),
        sa.Column('notes', sa.Text()),
        sa.Column('source', sa.String(32), nullable=False, server_default='manual'),
        sa.Column('created_by', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('batch_id', 'revision', name='uq_batch_assay_revision'))
    op.create_index('ix_assay_revisions_batch_id', 'assay_revisions', ['batch_id'])
    op.create_table('catalog_import_previews',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False), sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False), sa.Column('consumed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()))
    conn = op.get_bind()
    for coal in conn.execute(sa.text('SELECT * FROM coal_data ORDER BY id')).mappings():
        raw = {}
        for field in ('ash_content', 'volatile_matter', 'fixed_carbon', 'total_sulfur',
                      'calorific_value', 'total_moisture', 'air_dry_moisture', 'price',
                      'carbon_content', 'hydrogen_content', 'nitrogen_content', 'hgi', 'burnout_rate'):
            value = coal.get(field)
            if value is None:
                continue
            unit, basis = '%', 'unknown'
            if field == 'price':
                unit, basis = 'CNY/t', coal['price_basis'] or 'unknown'
            elif field == 'calorific_value':
                unit, basis = 'kcal/kg', coal['calorific_basis'] or 'unknown'
            elif field == 'hgi':
                unit = 'index'
            elif field not in ('total_moisture', 'air_dry_moisture', 'burnout_rate'):
                basis = coal['analysis_basis'] or 'unknown'
            raw[field] = {'value': value, 'unit': unit, 'basis': basis}
            if field == 'calorific_value':
                raw[field]['heat_type'] = coal['calorific_type'] if coal['calorific_type'] in ('net_v', 'net_p', 'gr_v') else 'unknown'
            if field == 'hydrogen_content':
                raw[field]['hydrogen_includes_moisture'] = None
        # Even an empty legacy row is retained as a historical record.
        inserted = conn.execute(batches.insert().values(coal_id=coal['id'], code='历史迁入', supplier=coal.get('supplier')))
        batch_id = inserted.inserted_primary_key[0]
        conn.execute(assays.insert().values(batch_id=batch_id, revision=1, raw=raw, source='legacy_migration',
                                          notes='历史数据原值迁入；未记录的基准、热值定义和日期保持未知。'))


def downgrade():
    raise RuntimeError('2.0批次历史不能无损降级；请恢复升级前数据库备份。')
