"""Real sessions and CSRF protect the new catalog routes."""
import io
import json

import pytest

from app import create_app
from app.extensions import db
from app.services.access_service import create_initial_admin, create_user


@pytest.fixture
def client(tmp_path):
    app = create_app(config_overrides={
        'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "api.db"}',
        'AUTO_INITIALIZE_COAL_DATA': False, 'SESSION_COOKIE_SECURE': False,
    })
    with app.app_context():
        db.create_all()
        create_initial_admin('admin', 'Catalog-test-123')
    client = app.test_client()
    csrf = client.get('/api/auth/session').get_json()['csrf_token']
    login = client.post('/api/auth/login', json={'username': 'admin', 'password': 'Catalog-test-123'},
                        headers={'X-CSRF-Token': csrf})
    assert login.status_code == 200
    client.environ_base['HTTP_X_CSRF_TOKEN'] = login.get_json()['csrf_token']
    yield client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_catalog_api_partial_record_and_archive(client):
    coal = client.post('/api/catalog', json={'name': '新煤', 'type': '烟煤'})
    assert coal.status_code == 201
    coal_id = coal.get_json()['data']['id']
    batch = client.post(f'/api/catalog/{coal_id}/batches', json={'code': 'batch-1'}).get_json()['data']
    first = client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': {'ash_content': {'value': 10}}})
    assert first.status_code == 201
    record = first.get_json()['data']
    assert not record['eligibility']['blending']['eligible']
    assert record['raw']['ash_content']['basis'] == 'unknown'
    assert client.patch(f'/api/assays/{record["id"]}', json={'raw': {}}).status_code in (404, 405)
    assert client.patch(f'/api/batches/{batch["id"]}', json={'archived': True}).status_code == 200
    assert client.get('/api/assays').get_json()['data'] == []
    assert client.get('/api/assays?include_archived=true').get_json()['data'][0]['archived']
    assert client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': {}}).status_code == 400


def test_import_commit_does_not_accept_client_modified_rows(client):
    text = 'coal_name,type,batch_code\n导入煤,无烟煤,2026-09\n'
    preview = client.post('/api/catalog/import/preview', json={'text': text}).get_json()['data']
    assert preview['can_commit']
    tampered = client.post('/api/catalog/import/commit', json={'preview_token': preview['preview_token'], 'rows': []})
    assert tampered.status_code == 400
    commit = client.post('/api/catalog/import/commit', json={'preview_token': preview['preview_token']})
    assert commit.status_code == 201
    assert commit.get_json()['data']['created_revisions'] == 1
    assert client.post('/api/catalog/import/commit', json={'preview_token': preview['preview_token']}).status_code in (400, 409)
    export = client.get('/api/catalog/export?format=xlsx')
    assert export.status_code == 200
    imported = client.post('/api/catalog/import/preview', data={'file': (io.BytesIO(export.data), '化验完整.xlsx')})
    assert imported.get_json()['data']['can_commit']


def test_readonly_user_can_read_and_export_but_cannot_import(client):
    with client.application.app_context():
        create_user({'username': 'viewer', 'password': 'Catalog-test-456', 'role': 'viewer'})
    client.post('/api/auth/logout')
    csrf = client.get('/api/auth/session').get_json()['csrf_token']
    login = client.post('/api/auth/login', headers={'X-CSRF-Token': csrf},
                        json={'username': 'viewer', 'password': 'Catalog-test-456'})
    client.environ_base['HTTP_X_CSRF_TOKEN'] = login.get_json()['csrf_token']
    assert client.get('/api/catalog').status_code == 200
    assert client.get('/api/catalog/export').status_code == 200
    assert client.get('/api/catalog/test-data?format=xlsx').status_code == 200
    assert client.get('/api/catalog/test-data?format=csv').status_code == 200
    assert client.post('/api/catalog', json={'name': 'forbidden', 'type': '烟煤'}).status_code == 403
    assert client.post('/api/catalog/import/preview', json={'text': 'x'}).status_code == 403


@pytest.mark.parametrize('text', ['', 'coal_name,coal_name\nA,B', 'coal_name,type,batch_code\nA,烟煤,B,extra'])
def test_invalid_tables_return_clear_400(client, text):
    response = client.post('/api/catalog/import/preview', json={'text': text})
    assert response.status_code == 400
    assert response.get_json()['message']
