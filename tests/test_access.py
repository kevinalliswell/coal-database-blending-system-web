import pytest

from flask import Flask
from app.extensions import db
from app.routes.access import init_access
from app.services.access_service import create_initial_admin


@pytest.fixture
def access_app(tmp_path):
    app = Flask(__name__)
    app.config.update({
        'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{(tmp_path / "access.db").as_posix()}',
        'DATA_DIR': str(tmp_path), 'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'COAL_DATA_PATH': str(tmp_path / 'absent.csv'), 'AUTO_INITIALIZE_COAL_DATA': False,
        'SESSION_COOKIE_SECURE': False,
    })
    db.init_app(app)
    init_access(app)
    # These probes exercise the central guard independently of catalog/calculation implementation.
    app.add_url_rule('/api/catalog', 'access_catalog_probe', lambda: {'status': 'success'}, methods=['GET', 'POST'])
    app.add_url_rule('/api/assays/preview', 'access_preview_probe', lambda: {'status': 'success'}, methods=['POST'])
    app.add_url_rule('/api/optimization/history', 'access_history_probe', lambda: {'status': 'success'})
    app.add_url_rule('/api/optimization/export/current', 'access_export_probe', lambda: {'status': 'success'}, methods=['POST'])
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def login(client, username='admin', password='Testpassword123!'):
    token = client.get('/api/auth/session').get_json()['csrf_token']
    response = client.post('/api/auth/login', json={'username': username, 'password': password},
                           headers={'X-CSRF-Token': token})
    assert response.status_code == 200, response.get_json()
    return {'X-CSRF-Token': response.get_json()['csrf_token']}


def bootstrap(app):
    with app.app_context():
        create_initial_admin('admin', 'Testpassword123!', '管理员')


def test_production_and_testing_both_require_login(access_app):
    client = access_app.test_client()
    assert client.get('/api/settings').status_code == 401
    session = client.get('/api/auth/session').get_json()
    assert session['setup_required'] and session['user'] is None and session['csrf_token']
    assert client.post('/api/auth/setup', json={'username': 'admin', 'password': 'Testpassword123!'},
                       headers={'X-CSRF-Token': session['csrf_token']}).status_code == 403


def test_setup_requires_desktop_transport_and_only_happens_once(access_app):
    access_app.config['DESKTOP_MODE'] = True
    client = access_app.test_client()
    token = client.get('/api/auth/session').get_json()['csrf_token']
    body = {'username': 'admin', 'password': 'Testpassword123!', 'display_name': '管理员'}
    headers = {'X-CSRF-Token': token}
    assert client.post('/api/auth/setup', json=body, headers=headers).status_code == 403
    trusted = {'cbos.transport_authenticated': True}
    response = client.post('/api/auth/setup', json=body, headers=headers, environ_overrides=trusted)
    assert response.status_code == 201
    headers = {'X-CSRF-Token': response.get_json()['csrf_token']}
    assert client.post('/api/auth/setup', json=body, headers=headers, environ_overrides=trusted).status_code == 409


def test_login_rotates_session_and_logout_revokes_cookie(access_app):
    bootstrap(access_app)
    client = access_app.test_client()
    client.get('/api/auth/session')
    before = client.get_cookie('cbos_session').value
    headers = login(client)
    cookie = client.get_cookie('cbos_session').value
    assert before != cookie
    assert client.get('/api/settings').status_code == 200
    assert client.post('/api/auth/logout').status_code == 403
    assert client.post('/api/auth/logout', headers=headers).status_code == 200
    client.set_cookie('cbos_session', cookie)
    assert client.get('/api/settings').status_code == 401


@pytest.mark.parametrize('role,write,preview,admin', [
    ('admin', 200, 200, 200), ('data_manager', 200, 200, 403),
    ('calculator', 403, 200, 403), ('viewer', 403, 403, 403),
])
def test_role_permissions_are_checked_on_direct_api(access_app, role, write, preview, admin):
    bootstrap(access_app)
    client = access_app.test_client()
    headers = login(client)
    if role != 'admin':
        assert client.post('/api/users', json={'username': role, 'password': 'Testpassword123!', 'role': role}, headers=headers).status_code == 201
        headers = login(client, role)
    assert client.get('/api/catalog').status_code == 200
    assert client.post('/api/catalog', json={}, headers=headers).status_code == write
    assert client.post('/api/assays/preview', json={}, headers=headers).status_code == preview
    assert client.get('/api/users').status_code == admin
    assert client.get('/api/optimization/history').status_code == 200
    # Read-only report export POST is permissioned as export, not data_write.
    assert client.post('/api/optimization/export/current', json={}, headers=headers).status_code != 403


def test_csrf_and_cross_origin_write_are_rejected(access_app):
    bootstrap(access_app)
    client = access_app.test_client()
    headers = login(client)
    assert client.post('/api/catalog', json={}).status_code == 403
    assert client.post('/api/catalog', json={}, headers={**headers, 'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/catalog', json={}, headers={**headers, 'Origin': 'http://localhost'}).status_code == 200


def test_admin_cannot_remove_last_admin_and_disable_revokes_sessions(access_app):
    bootstrap(access_app)
    admin = access_app.test_client(); headers = login(admin)
    user = admin.get('/api/auth/session').get_json()['user']
    for data in ({'active': False}, {'role': 'viewer'}):
        assert admin.patch(f'/api/users/{user["id"]}', json=data, headers=headers).status_code == 409
    created = admin.post('/api/users', json={'username': 'operator', 'password': 'Testpassword123!', 'role': 'calculator'}, headers=headers).get_json()['data']
    operator = access_app.test_client(); login(operator, 'operator')
    assert admin.patch(f'/api/users/{created["id"]}', json={'active': False}, headers=headers).status_code == 200
    assert operator.get('/api/settings').status_code == 401


def test_password_change_revokes_other_session_and_checks_current_password(access_app):
    bootstrap(access_app)
    first = access_app.test_client(); headers = login(first)
    second = access_app.test_client(); login(second)
    assert first.put('/api/auth/password', json={'current_password': 'wrong', 'password': 'Newpassword123!'}, headers=headers).status_code == 400
    assert first.put('/api/auth/password', json={'current_password': 'Testpassword123!', 'password': 'Newpassword123!'}, headers=headers).status_code == 200
    assert second.get('/api/settings').status_code == 401
    login(first, password='Newpassword123!')


def test_settings_version_and_basis_confirmation_are_atomic(access_app):
    bootstrap(access_app)
    client = access_app.test_client(); headers = login(client)
    initial = client.get('/api/settings').get_json()['data']
    assert (initial['ratio_basis'], initial['heat_type'], initial['heat_unit']) == ('ar', 'net_v', 'MJ/kg')
    assert client.put('/api/settings', json={'version': initial['version'], 'ratio_basis': 'd'}, headers=headers).status_code == 400
    changed = client.put('/api/settings', json={**initial, 'ratio_basis': 'd', 'constraints_confirmed': True}, headers=headers)
    assert changed.status_code == 200
    assert changed.get_json()['data']['version'] == initial['version'] + 1
    assert client.put('/api/settings', json={**initial, 'system_name': 'stale'}, headers=headers).status_code == 409
    final = client.get('/api/settings').get_json()['data']
    assert final['ratio_basis'] == 'd' and final['system_name'] != 'stale'
    assert client.put('/api/settings', json={**final, 'constraints': {**final['constraints'], 'sulfur_max': float('nan')}}, headers=headers).status_code == 400


def test_cli_bootstrap_and_system_info(access_app):
    result = access_app.test_cli_runner().invoke(args=['users', 'create-admin', '--username', 'admin', '--display-name', 'Admin'],
                                                input='Testpassword123!\nTestpassword123!\n')
    assert result.exit_code == 0, result.output
    assert 'Testpassword123!' not in result.output
    client = access_app.test_client(); login(client)
    info = client.get('/api/system/info').get_json()['data']
    from app.__version__ import __version__
    assert info['version'] == __version__ and info['mode'] == 'web'


def test_first_admin_race_creates_exactly_one_account(access_app):
    from concurrent.futures import ThreadPoolExecutor
    from app.models.access import User
    from app.services.access_service import AccessError, ensure_access_rows
    with access_app.app_context():
        ensure_access_rows()
    def create(name):
        with access_app.app_context():
            try:
                create_initial_admin(name, 'Testpassword123!')
                return 201
            except AccessError as error:
                return error.status
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, ('first', 'second')))
    assert sorted(results) == [201, 409]
    with access_app.app_context():
        assert db.session.query(User).count() == 1


def test_role_change_expiry_and_password_reset_revoke_sessions(access_app):
    import time
    from app.models.access import AuthSession
    bootstrap(access_app)
    admin = access_app.test_client(); headers = login(admin)
    created = admin.post('/api/users', json={'username': 'operator', 'password': 'Testpassword123!', 'role': 'calculator'}, headers=headers).get_json()['data']
    operator = access_app.test_client(); login(operator, 'operator')
    assert admin.patch(f'/api/users/{created["id"]}', json={'role': 'viewer'}, headers=headers).status_code == 200
    assert operator.get('/api/settings').status_code == 401
    login(operator, 'operator')
    assert admin.put(f'/api/users/{created["id"]}/password', json={'password': 'Resetpassword123!'}, headers=headers).status_code == 200
    assert operator.get('/api/settings').status_code == 401
    login(operator, 'operator', 'Resetpassword123!')
    with access_app.app_context():
        db.session.query(AuthSession).filter_by(user_id=created['id']).update({'expires_at': int(time.time()) - 1})
        db.session.commit()
    assert operator.get('/api/settings').status_code == 401


def test_login_throttle_and_bad_role_shape(access_app):
    bootstrap(access_app)
    client = access_app.test_client(); headers = login(client)
    assert client.post('/api/users', json={'username': 'baduser', 'password': 'Testpassword123!', 'role': []}, headers=headers).status_code == 400
    for _ in range(8):
        assert client.post('/api/auth/login', json={'username': 'missing', 'password': 'wrong'}, headers=headers).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'missing', 'password': 'wrong'}, headers=headers).status_code == 429
