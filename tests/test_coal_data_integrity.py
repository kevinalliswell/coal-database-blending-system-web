import io

import pandas as pd
import pytest

from app import create_app
from app.extensions import db
from app.models import Coal
from app.services.coal_data_service import import_dataframe
from backend.utils.validation import validate_coal_data
from access_helpers import authenticated_client


def coal_payload(**changes):
    return dict(name='测试煤', type='烟煤', price=600, calorific_value=6000,
                ash_content=10, volatile_matter=20, fixed_carbon=65,
                total_sulfur=0.5, **changes)


@pytest.fixture
def client(tmp_path):
    app = create_app(config_overrides={'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "coals.db"}',
        'COAL_DATA_PATH': str(tmp_path / 'absent.csv'), 'UPLOAD_FOLDER': str(tmp_path),
        'AUTO_INITIALIZE_COAL_DATA': False})
    with app.app_context():
        db.create_all()
    yield authenticated_client(app)
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
    field = {'moisture': 'total_moisture', 'mad': 'air_dry_moisture'}.get(field, field)
    response = client.post('/api/assays/preview', json={'raw': {field: {'value': value}}})
    assert response.status_code == 400
    assert client.get('/api/assays').get_json()['data'] == []


def test_import_and_manual_entry_share_physical_validation(client):
    payload = coal_payload()
    payload['ash_content'] = 150
    assert client.post('/api/assays/preview', json={'raw': {'ash_content': {'value': 150}}}).status_code == 400
    with client.application.app_context():
        summary = import_dataframe(pd.DataFrame([payload]))
        assert summary.created_count == 0
        assert summary.skipped_count == 1
        assert '灰分' in summary.errors[0]
        assert Coal.query.count() == 0


def test_alias_updates_replace_old_values_and_can_clear_them(client):
    # The legacy seed/import adapter still supports its published water aliases;
    # v2 API records have canonical per-metric raw fields instead of these aliases.
    from app.services.coal_data_service import coal_to_api_dict
    payload = coal_payload(moisture=8.5, mad=1.2)
    with client.application.app_context():
        assert import_dataframe(pd.DataFrame([payload])).created_count == 1
        payload.update(moisture=12, mad=2)
        assert import_dataframe(pd.DataFrame([payload])).updated_count == 1
        values = coal_to_api_dict(Coal.query.one())
        assert (values['moisture'], values['total_moisture'], values['mad'], values['air_dry_moisture']) == (12, 12, 2, 2)
        payload.update(moisture=None, mad=None)
        assert import_dataframe(pd.DataFrame([payload])).updated_count == 1
        cleared = coal_to_api_dict(Coal.query.one())
        assert cleared['total_moisture'] is None and cleared['air_dry_moisture'] is None


def test_canonical_water_fields_win_if_both_are_supplied(client):
    payload = coal_payload(moisture=8, total_moisture=9, mad=1, air_dry_moisture=2)
    from app.services.coal_data_service import coal_to_api_dict, create_coal
    with client.application.app_context():
        result = coal_to_api_dict(create_coal(payload))
        assert result['moisture'] == 9 and result['mad'] == 2


def test_zero_page_size_and_all_export_include_more_than_ten_coals(client):
    for index in range(12):
        coal = client.post('/api/catalog', json={'name': f'煤{index}', 'type': '烟煤'}).get_json()['data']
        batch = client.post(f'/api/catalog/{coal["id"]}/batches', json={'code': 'B'}).get_json()['data']
        assert client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': {}}).status_code == 201
    result = client.get('/api/assays?page_size=0').get_json()
    assert len(result['data']) == 12
    assert result['pagination']['page_size'] == 0
    export = client.get('/api/catalog/export')
    assert export.status_code == 200
    assert len(pd.read_excel(io.BytesIO(export.data))) == 12


@pytest.mark.parametrize('bad_value', ['NaN', 'Infinity', '-Infinity'])
def test_csv_upload_rejects_nonfinite_optional_values(client, bad_value):
    csv = ('coal_name,type,batch_code,hgi.value,hgi.unit,hgi.basis\n'
           f'非法煤,烟煤,B,{bad_value},index,unknown\n')
    response = client.post('/api/catalog/import/preview', data={'file': (io.BytesIO(csv.encode()), 'coals.csv')})
    payload = response.get_json()
    assert not payload['data']['can_commit']
    assert payload['data']['rows'][0]['issues']
    assert client.get('/api/catalog').get_json()['data'] == []


def test_export_with_blank_optional_values_can_be_reimported(client):
    coal = client.post('/api/catalog', json={'name': '缺项煤', 'type': '烟煤'}).get_json()['data']
    batch = client.post(f'/api/catalog/{coal["id"]}/batches', json={'code': 'B'}).get_json()['data']
    assert client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': {}}).status_code == 201
    exported = client.get('/api/catalog/export')
    response = client.post('/api/catalog/import/preview', data={'file': (io.BytesIO(exported.data), 'coals.xlsx')})
    preview = response.get_json()['data']
    assert preview['can_commit']
    response = client.post('/api/catalog/import/commit', json={'preview_token': preview['preview_token']})
    assert response.get_json()['data']['created_revisions'] == 1
    assert len(client.get(f'/api/batches/{batch["id"]}/assays').get_json()['data']) == 2


@pytest.mark.parametrize('method,url', [('post', '/api/coals'), ('put', '/api/coals/1'),
                                       ('delete', '/api/coals/1'), ('post', '/api/coals/upload')])
def test_retired_legacy_write_endpoints_return_upgrade_required(client, method, url):
    response = getattr(client, method)(url, json=coal_payload())
    assert response.status_code == 410
    assert response.get_json()['code'] == 'api_upgrade_required'
    assert client.get('/api/catalog').get_json()['data'] == []
