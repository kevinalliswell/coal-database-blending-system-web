"""Catalog storage never treats missing analytical data as a numeric zero."""
from copy import deepcopy
from datetime import date, datetime

from sqlalchemy import func

from app.extensions import db
from app.models.coal import Coal
from app.models.catalog import AssayRevision, CoalBatch


METRICS = ('ash_content', 'volatile_matter', 'fixed_carbon', 'total_sulfur',
           'calorific_value', 'total_moisture', 'air_dry_moisture', 'price',
           'carbon_content', 'hydrogen_content', 'nitrogen_content', 'sio2_content',
           'hgi', 'burnout_rate')


class CatalogConflict(ValueError):
    """A unique identity or preview target changed concurrently."""


def text_field(value, field, limit=100, required=False):
    if value is None:
        value = ''
    if not isinstance(value, str):
        raise ValueError(f'{field}必须是文字')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{field}不能为空')
    if len(value) > limit:
        raise ValueError(f'{field}不能超过{limit}个字符')
    return value or None


def date_field(value, field):
    value = text_field(value, field, 40)
    if value:
        try:
            if len(value) == 10:
                date.fromisoformat(value)
            else:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f'{field}须为ISO日期或日期时间') from None
    return value


def object_fields(payload, allowed):
    if not isinstance(payload, dict):
        raise ValueError('请求必须为JSON对象')
    extra = set(payload) - set(allowed)
    if extra:
        raise ValueError(f'不支持的字段: {", ".join(sorted(extra))}')


def get_coal(coal_id):
    coal = db.session.get(Coal, coal_id)
    if coal is None:
        raise LookupError('煤种不存在')
    return coal


def get_batch(batch_id):
    batch = db.session.get(CoalBatch, batch_id)
    if batch is None:
        raise LookupError('批次不存在')
    return batch


def create_coal(payload):
    object_fields(payload, ('name', 'type', 'supplier'))
    name = text_field(payload.get('name'), '煤种名称', required=True)
    if Coal.query.filter_by(name=name).first():
        raise CatalogConflict('煤种名称已存在，请在现有煤种下新增批次')
    coal = Coal(name=name, type=text_field(payload.get('type'), '煤种类型', 50, True),
                supplier=text_field(payload.get('supplier'), '供应商'))
    db.session.add(coal)
    db.session.flush()
    return coal


def update_coal(coal_id, payload):
    object_fields(payload, ('name', 'type', 'supplier', 'archived'))
    coal = get_coal(coal_id)
    for key in ('name', 'type', 'supplier'):
        if key in payload:
            value = text_field(payload[key], key, 50 if key == 'type' else 100, key != 'supplier')
            if key == 'name' and Coal.query.filter(Coal.name == value, Coal.id != coal.id).first():
                raise CatalogConflict('煤种名称已存在')
            setattr(coal, key, value)
    if 'archived' in payload:
        if not isinstance(payload['archived'], bool):
            raise ValueError('archived必须为布尔值')
        coal.archived = payload['archived']
    db.session.flush()
    return coal


def create_batch(coal_id, payload):
    object_fields(payload, ('code', 'supplier', 'received_at'))
    coal = get_coal(coal_id)
    if coal.archived:
        raise ValueError('煤种已归档')
    code = text_field(payload.get('code'), '批次编号', required=True)
    if CoalBatch.query.filter_by(coal_id=coal.id, code=code).first():
        raise CatalogConflict('该煤种的批次编号已存在')
    batch = CoalBatch(coal=coal, code=code,
                      supplier=text_field(payload.get('supplier'), '供应商'),
                      received_at=date_field(payload.get('received_at'), '收货日期'))
    db.session.add(batch)
    db.session.flush()
    return batch


def update_batch(batch_id, payload):
    object_fields(payload, ('archived',))
    batch = get_batch(batch_id)
    if not isinstance(payload.get('archived'), bool):
        raise ValueError('archived必须为布尔值')
    batch.archived = payload['archived']
    db.session.flush()
    return batch


def create_assay(batch_id, payload, user_id=None, source='manual'):
    from app.services.assay_conversion import validate_raw_assay
    object_fields(payload, ('raw', 'report_number', 'sampled_at', 'notes'))
    batch = get_batch(batch_id)
    if batch.archived or batch.coal.archived:
        raise ValueError('煤种或批次已归档')
    if 'raw' not in payload:
        raise ValueError('必须提供raw，空化验记录可使用{}')
    raw = validate_raw_assay(payload['raw'])
    maximum = db.session.query(func.max(AssayRevision.revision)).filter_by(batch_id=batch.id).scalar() or 0
    record = AssayRevision(batch=batch, revision=maximum + 1, raw=deepcopy(raw),
                           report_number=text_field(payload.get('report_number'), '报告编号', 120),
                           sampled_at=date_field(payload.get('sampled_at'), '采样日期'),
                           notes=text_field(payload.get('notes'), '备注', 10000),
                           created_by=user_id, source=source)
    db.session.add(record)
    db.session.flush()
    return record


def serialize_assay(record, settings):
    from app.services.assay_conversion import evaluate_assay
    batch = record.batch
    coal = batch.coal
    archived = bool(coal.archived or batch.archived)
    try:
        eligibility = evaluate_assay(record.raw, settings)
    except ValueError as exc:
        # Migration must preserve even old malformed/unsupported metadata. Such
        # records stay readable but cannot be passed to calculation kernels.
        eligibility = {kind: {'eligible': False, 'issues': [{'field': 'raw', 'code': 'invalid_legacy_raw', 'message': str(exc)}],
                              'values': {}, 'trace': []} for kind in ('blending', 'theory')}
    if archived:
        for result in eligibility.values():
            result['eligible'] = False
            result['issues'].append({'field': 'archived', 'code': 'archived', 'message': '煤种或批次已归档'})
    return {'id': record.id, 'coal_id': coal.id, 'batch_id': batch.id,
            'revision': record.revision, 'coal_name': coal.name, 'coal_type': coal.type,
            'batch_code': batch.code, 'label': f'{coal.name} / {batch.code} / R{record.revision} [#{record.id}]',
            'raw': deepcopy(record.raw), 'eligibility': eligibility, 'archived': archived,
            'report_number': record.report_number, 'sampled_at': record.sampled_at,
            'notes': record.notes, 'source': record.source, 'created_by': record.created_by,
            'created_at': record.created_at.isoformat() if record.created_at else None}


def serialize_batch(batch, settings):
    latest = max(batch.assays, key=lambda r: r.revision, default=None)
    return {'id': batch.id, 'coal_id': batch.coal_id, 'code': batch.code,
            'supplier': batch.supplier, 'received_at': batch.received_at,
            'archived': bool(batch.archived), 'revision_count': len(batch.assays),
            'latest_assay': serialize_assay(latest, settings) if latest else None}


def serialize_coal(coal, settings):
    return {'id': coal.id, 'name': coal.name, 'type': coal.type, 'supplier': coal.supplier,
            'archived': bool(coal.archived),
            'batches': [serialize_batch(batch, settings) for batch in sorted(coal.batches, key=lambda b: b.id)]}


def legacy_raw(coal):
    """Copy known legacy metadata, never infer a heat convention or sample date."""
    raw = {}
    for field in METRICS:
        value = getattr(coal, field, None)
        if value is None:
            continue
        basis = 'unknown'
        unit = '%'
        if field == 'price':
            unit, basis = 'CNY/t', coal.price_basis or 'unknown'
        elif field == 'calorific_value':
            unit, basis = 'kcal/kg', coal.calorific_basis or 'unknown'
        elif field == 'hgi':
            unit = 'index'
        elif field not in ('total_moisture', 'air_dry_moisture', 'burnout_rate', 'sio2_content'):
            basis = coal.analysis_basis or 'unknown'
        raw[field] = {'value': value, 'unit': unit, 'basis': basis}
        if field == 'calorific_value':
            raw[field]['heat_type'] = coal.calorific_type if coal.calorific_type in ('net_v', 'net_p', 'gr_v') else 'unknown'
        if field == 'hydrogen_content':
            raw[field]['hydrogen_includes_moisture'] = None
    return raw


def backfill_legacy_catalog():
    count = 0
    for coal in Coal.query.order_by(Coal.id).all():
        if CoalBatch.query.filter_by(coal_id=coal.id).first():
            continue
        raw = legacy_raw(coal)
        if not raw:
            continue
        batch = CoalBatch(coal=coal, code='历史迁入', supplier=coal.supplier)
        db.session.add(batch)
        db.session.flush()
        db.session.add(AssayRevision(batch=batch, revision=1, raw=raw, source='legacy_migration',
                                    notes='历史数据原值迁入；未记录的基准、热值定义和日期保持未知。'))
        count += 1
    db.session.commit()
    return count
