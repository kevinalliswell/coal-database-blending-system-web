"""Batch records preserve raw assays independently of calculation eligibility."""
import pytest
from flask import Flask

from app.extensions import db


@pytest.fixture
def catalog_app(tmp_path):
    from app.models.catalog import AssayRevision, CoalBatch, ImportPreview  # noqa: F401
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI=f'sqlite:///{tmp_path / "catalog.db"}',
                      SQLALCHEMY_TRACK_MODIFICATIONS=False, SECRET_KEY='test-only')
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_partial_assay_can_be_saved_and_each_revision_is_retained(catalog_app):
    from app.services.catalog_service import create_coal, create_batch, create_assay, serialize_assay
    coal = create_coal({'name': '未完整化验煤', 'type': '烟煤'})
    batch = create_batch(coal.id, {'code': 'B-001'})
    first = create_assay(batch.id, {'raw': {'ash_content': {'value': 12, 'unit': '%', 'basis': 'unknown'}}})
    second = create_assay(batch.id, {'raw': {'ash_content': {'value': 13, 'unit': '%', 'basis': 'd'}}})
    db.session.commit()
    assert (first.revision, second.revision) == (1, 2)
    assert first.raw['ash_content']['value'] == 12
    result = serialize_assay(first, {'ratio_basis': 'ar', 'heat_type': 'net_v'})
    assert not result['eligibility']['blending']['eligible']
    assert result['raw']['ash_content']['basis'] == 'unknown'
    assert result['label'] != serialize_assay(second, {})['label']


def test_two_batches_of_same_coal_have_independent_revisions(catalog_app):
    from app.services.catalog_service import create_coal, create_batch, create_assay
    coal = create_coal({'name': '煤 A', 'type': '无烟煤'})
    batches = [create_batch(coal.id, {'code': code}) for code in ('批次一', '批次二')]
    records = [create_assay(batch.id, {'raw': {}}) for batch in batches]
    db.session.commit()
    assert len({r.id for r in records}) == 2
    assert [r.revision for r in records] == [1, 1]


def test_assay_revisions_cannot_be_changed_or_deleted(catalog_app):
    from app.services.catalog_service import create_coal, create_batch, create_assay
    coal = create_coal({'name': '煤 A', 'type': '烟煤'})
    record = create_assay(create_batch(coal.id, {'code': 'b'}).id, {'raw': {}})
    db.session.commit()
    record.notes = 'overwrite'
    with pytest.raises(ValueError, match='不可修改'):
        db.session.commit()
    db.session.rollback()
    db.session.delete(record)
    with pytest.raises(ValueError, match='不可删除'):
        db.session.commit()
    db.session.rollback()


def test_archived_batch_keeps_records_but_cannot_accept_new_revisions(catalog_app):
    from app.services.catalog_service import create_coal, create_batch, create_assay, update_batch, serialize_assay
    coal = create_coal({'name': '煤 A', 'type': '烟煤'})
    batch = create_batch(coal.id, {'code': 'b'})
    record = create_assay(batch.id, {'raw': {}})
    update_batch(batch.id, {'archived': True})
    assert serialize_assay(record, {})['archived'] is True
    with pytest.raises(ValueError, match='归档'):
        create_assay(batch.id, {'raw': {}})


def test_legacy_backfill_is_idempotent_and_does_not_invent_dates_or_heat_type(catalog_app):
    from app.models.coal import Coal
    from app.models.catalog import AssayRevision, CoalBatch
    from app.services.catalog_service import backfill_legacy_catalog
    coal = Coal(id=77, name='旧煤', type='烟煤', price=600, calorific_value=6000,
                ash_content=10, volatile_matter=20, fixed_carbon=65, total_sulfur=0.5,
                calorific_type='net', analysis_basis='unknown')
    db.session.add(coal)
    db.session.commit()
    assert backfill_legacy_catalog() == 1
    assert backfill_legacy_catalog() == 0
    record = AssayRevision.query.one()
    batch = CoalBatch.query.one()
    assert batch.coal_id == 77 and batch.received_at is None
    assert record.sampled_at is None
    assert record.raw['calorific_value'] == {'value': 6000, 'unit': 'kcal/kg', 'basis': 'unknown', 'heat_type': 'unknown'}
    assert record.raw['ash_content']['value'] == 10
    assert record.raw['ash_content']['basis'] == 'unknown'


@pytest.mark.parametrize('raw', [{'ash_content': {'value': True}}, {'price': {'value': float('inf')}}, {'typo': {'value': 10}}])
def test_storage_rejects_malformed_numbers_and_unknown_fields(catalog_app, raw):
    from app.services.catalog_service import create_coal, create_batch, create_assay
    coal = create_coal({'name': '煤 A', 'type': '烟煤'})
    batch = create_batch(coal.id, {'code': 'b'})
    with pytest.raises(ValueError):
        create_assay(batch.id, {'raw': raw})
