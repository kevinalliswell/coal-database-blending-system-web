import io

import pandas as pd
import pytest

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Coal
from app.services.coal_data_service import import_dataframe
from backend.utils.validation import validate_coal_data


def coal_payload(**changes):
    return dict(name='测试煤', type='烟煤', price=600, calorific_value=6000,
                ash_content=10, volatile_matter=20, fixed_carbon=65,
                total_sulfur=0.5, **changes)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{tmp_path / "coals.db"}')
    monkeypatch.setattr(Config, 'COAL_DATA_PATH', str(tmp_path / 'absent.csv'))
    monkeypatch.setattr(Config, 'UPLOAD_FOLDER', str(tmp_path))
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
    yield app.test_client()
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_impossible_proximate_total_is_rejected():
    payload = coal_payload()
    payload.update(ash_content=20, volatile_matter=30, fixed_carbon=60, mad=10)
    valid, errors = validate_coal_data(payload)
    assert not valid
    assert any('100' in error for error in errors)


def test_unidentified_basis_does_not_assume_dry_coal():
    payload = coal_payload()
    payload.update(ash_content=8, volatile_matter=24, fixed_carbon=48, moisture=20)
    assert validate_coal_data(payload) == (True, [])


@pytest.mark.parametrize('field', ['price', 'calorific_value', 'hgi', 'moisture', 'mad', 'burnout_rate'])
@pytest.mark.parametrize('value', ['Infinity', '-Infinity', 'NaN', True, []])
def test_nonfinite_or_nonnumeric_fields_are_rejected(client, field, value):
    payload = coal_payload()
    payload[field] = value
    response = client.post('/api/coals', json=payload)
    assert response.status_code == 400
    assert client.get('/api/coals?page_size=0').get_json()['data'] == []


def test_import_and_manual_entry_share_physical_validation(client):
    payload = coal_payload()
    payload['ash_content'] = 150
    assert client.post('/api/coals', json=payload).status_code == 400
    with client.application.app_context():
        summary = import_dataframe(pd.DataFrame([payload]))
        assert summary.created_count == 0
        assert summary.skipped_count == 1
        assert '灰分' in summary.errors[0]
        assert Coal.query.count() == 0


def test_alias_updates_replace_old_values_and_can_clear_them(client):
    payload = coal_payload(moisture=8.5, mad=1.2)
    created = client.post('/api/coals', json=payload).get_json()['data']
    payload.update(moisture=12, mad=2)
    updated = client.put(f'/api/coals/{created["id"]}', json=payload)
    assert updated.status_code == 200
    values = updated.get_json()['data']
    assert (values['moisture'], values['total_moisture'], values['mad'], values['air_dry_moisture']) == (12, 12, 2, 2)
    payload.update(moisture=None, mad=None)
    cleared = client.put(f'/api/coals/{created["id"]}', json=payload).get_json()['data']
    assert cleared['total_moisture'] is None and cleared['air_dry_moisture'] is None


def test_canonical_water_fields_win_if_both_are_supplied(client):
    payload = coal_payload(moisture=8, total_moisture=9, mad=1, air_dry_moisture=2)
    result = client.post('/api/coals', json=payload).get_json()['data']
    assert result['moisture'] == 9 and result['mad'] == 2


def test_zero_page_size_and_all_export_include_more_than_ten_coals(client):
    for index in range(12):
        payload = coal_payload()
        payload['name'] = f'煤{index}'
        assert client.post('/api/coals', json=payload).status_code == 200
    result = client.get('/api/coals?page_size=0').get_json()
    assert len(result['data']) == 12
    assert result['pagination']['page_size'] == 0
    export = client.post('/api/coals/export', json={'export_all': True})
    assert export.status_code == 200
    assert len(pd.read_excel(io.BytesIO(export.data))) == 12


@pytest.mark.parametrize('bad_value', ['NaN', 'Infinity', '-Infinity'])
def test_csv_upload_rejects_nonfinite_optional_values(client, bad_value):
    csv = ('煤种名称,煤种类型,价格(元/吨),热值(kcal/kg),灰分(%),挥发分(%),固定碳(%),全硫(%),可磨性HGI\n'
           f'非法煤,烟煤,600,6000,10,20,65,0.5,{bad_value}\n')
    response = client.post('/api/coals/upload', data={'file': (io.BytesIO(csv.encode()), 'coals.csv')})
    payload = response.get_json()
    assert payload['status'] == 'error'
    assert client.get('/api/coals?page_size=0').get_json()['data'] == []


def test_export_with_blank_optional_values_can_be_reimported(client):
    assert client.post('/api/coals', json=coal_payload()).status_code == 200
    exported = client.post('/api/coals/export', json={'export_all': True})
    response = client.post('/api/coals/upload', data={'file': (io.BytesIO(exported.data), 'coals.xlsx')})
    assert response.get_json()['updated_count'] == 1
