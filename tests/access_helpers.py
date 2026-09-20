"""Explicit authenticated clients for API fixtures; never an application bypass."""
from app.extensions import db
from app.models.access import User
from app.routes.access import init_access
from app.services.access_service import create_initial_admin, create_user

PASSWORD = 'Testpassword123!'


def create_test_admin(app):
    init_access(app)
    with app.app_context():
        if db.session.query(User).filter_by(username='testadmin').first() is None:
            if not db.session.query(User).first():
                create_initial_admin('testadmin', PASSWORD, '测试管理员')
            else:
                create_user({'username': 'testadmin', 'password': PASSWORD, 'role': 'admin'})


def login_client(client, username='testadmin', password=PASSWORD, transport_headers=None):
    headers = dict(transport_headers or {})
    session = client.get('/api/auth/session', headers=headers).get_json()
    response = client.post('/api/auth/login', json={'username': username, 'password': password},
                           headers={**headers, 'X-CSRF-Token': session['csrf_token']})
    assert response.status_code == 200, response.get_json()
    return {**headers, 'X-CSRF-Token': response.get_json()['csrf_token']}


def authenticated_client(app, transport_headers=None):
    create_test_admin(app)
    client = app.test_client()
    headers = login_client(client, transport_headers=transport_headers)
    client.environ_base.update({'HTTP_' + key.upper().replace('-', '_'): value for key, value in headers.items()})
    return client
