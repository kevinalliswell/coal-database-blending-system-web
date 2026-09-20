"""Independent adversarial checks for identity, concurrency and import ownership."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.extensions import db
from app.models.access import User
from app.services.access_service import AccessError, create_user, update_settings, update_user, get_settings
from test_access import access_app, bootstrap, login  # noqa: F401
from test_catalog_api import client  # noqa: F401


def test_non_ascii_csrf_header_is_rejected_without_server_exception(access_app):
    bootstrap(access_app)
    browser = access_app.test_client()
    login(browser)
    response = browser.post('/api/catalog', json={}, headers={'X-CSRF-Token': '非ASCII令牌'})
    assert response.status_code == 403
    assert response.get_json()['code'] == 'csrf_failed'


def test_non_ascii_desktop_transport_header_is_rejected_without_server_exception():
    from desktop.runtime import TokenMiddleware
    called, responses = [], []
    wrapped = TokenMiddleware(lambda environ, start_response: called.append(True) or [], 'a' * 64)
    wrapped({'HTTP_X_CBOS_TOKEN': 'é'}, lambda status, headers: responses.append(status))
    assert not called
    assert responses == ['401 Unauthorized']


def test_two_admins_cannot_concurrently_disable_each_other(access_app):
    bootstrap(access_app)
    with access_app.app_context():
        second = create_user({'username': 'second', 'password': 'Testpassword123!', 'role': 'admin'})
        ids = [user.id for user in User.query.all()]
        assert second.id in ids
    def disable(user_id):
        with access_app.app_context():
            try:
                update_user(user_id, {'active': False})
                return 200
            except AccessError as error:
                return error.status
    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(disable, ids))
    assert sorted(statuses) == [200, 409]
    with access_app.app_context():
        assert User.query.filter_by(role='admin', active=True).count() == 1


def test_parallel_settings_writes_keep_exactly_one_version(access_app):
    bootstrap(access_app)
    with access_app.app_context():
        before = get_settings()
    def save(name):
        with access_app.app_context():
            try:
                update_settings({'version': before['version'], 'system_name': name})
                return 200
            except AccessError as error:
                return error.status
    with ThreadPoolExecutor(max_workers=2) as workers:
        statuses = list(workers.map(save, ['first settings', 'second settings']))
    assert sorted(statuses) == [200, 409]
    with access_app.app_context():
        after = get_settings()
        assert after['version'] == before['version'] + 1
        assert after['system_name'] in ('first settings', 'second settings')


def test_import_token_is_not_transferable_between_data_managers(client):
    created = client.post('/api/users', json={'username': 'datamanager', 'password': 'Testpassword123!', 'role': 'data_manager'})
    assert created.status_code == 201
    text = 'coal_name,type,batch_code\n私有预览,烟煤,B\n'
    token = client.post('/api/catalog/import/preview', json={'text': text}).get_json()['data']['preview_token']
    other = client.application.test_client()
    csrf = other.get('/api/auth/session').get_json()['csrf_token']
    result = other.post('/api/auth/login', headers={'X-CSRF-Token': csrf}, json={'username': 'datamanager', 'password': 'Testpassword123!'})
    csrf = result.get_json()['csrf_token']
    attack = other.post('/api/catalog/import/commit', headers={'X-CSRF-Token': csrf}, json={'preview_token': token})
    assert attack.status_code == 400
    assert '不属于当前用户' in attack.get_json()['message']
    assert other.get('/api/catalog').get_json()['data'] == []
    assert client.post('/api/catalog/import/commit', json={'preview_token': token}).status_code == 201


def test_demoted_creator_cannot_commit_previously_issued_import(client):
    created = client.post('/api/users', json={'username': 'datamanager', 'password': 'Testpassword123!', 'role': 'data_manager'}).get_json()['data']
    worker = client.application.test_client()
    headers = login(worker, 'datamanager')
    token = worker.post('/api/catalog/import/preview', headers=headers,
                         json={'text': 'coal_name,type,batch_code\n待导入,烟煤,B\n'}).get_json()['data']['preview_token']
    assert client.patch(f'/api/users/{created["id"]}', json={'role': 'viewer'}).status_code == 200
    assert worker.post('/api/catalog/import/commit', headers=headers, json={'preview_token': token}).status_code == 401
    headers = login(worker, 'datamanager')
    assert worker.post('/api/catalog/import/commit', headers=headers, json={'preview_token': token}).status_code == 403
    assert client.get('/api/catalog').get_json()['data'] == []


@pytest.mark.parametrize('url', ['/api/catalog', '/api/assays', '/api/settings', '/api/users', '/api/catalog/export', '/api/optimization/history'])
def test_api_responses_are_not_cacheable_between_accounts(client, url):
    assert client.get(url).headers['Cache-Control'] == 'no-store'
