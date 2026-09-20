from app.services.access_service import create_user
from app.routes.access import COOKIE
from test_catalog_api import client


def test_read_requests_with_stale_csrf_do_not_cross_cookie_identity(client):
    old_csrf = client.environ_base['HTTP_X_CSRF_TOKEN']
    with client.application.app_context():
        create_user({'username': 'other-reader', 'password': 'Other-reader-123', 'role': 'viewer'})
    login = client.post('/api/auth/login', json={'username': 'other-reader', 'password': 'Other-reader-123'})
    assert login.status_code == 200
    new_csrf = login.get_json()['csrf_token']
    # Cookies now identify the other user; another open tab still holds old_csrf.
    stale = client.get('/api/catalog', headers={'X-CSRF-Token': old_csrf})
    assert stale.status_code == 403
    assert stale.get_json()['code'] == 'csrf_failed'
    assert client.get('/api/catalog', headers={'X-CSRF-Token': new_csrf}).status_code == 200
    assert client.get('/api/auth/session', headers={'X-CSRF-Token': old_csrf}).get_json()['csrf_token'] == new_csrf
    del client.environ_base['HTTP_X_CSRF_TOKEN']
    assert client.get('/api/catalog').status_code == 200  # Existing read clients stay compatible.


def test_logout_leaves_one_anonymous_cookie_for_both_tabs_to_reuse(client):
    previous_cookie = client.get_cookie(COOKIE).value
    response = client.post('/api/auth/logout')
    assert response.status_code == 200
    anonymous_cookie = client.get_cookie(COOKIE)
    assert anonymous_cookie is not None and anonymous_cookie.value != previous_cookie
    token = response.get_json()['csrf_token']
    assert response.get_json()['user'] is None
    # Browser tabs share the post-logout cookie, but read independently.
    other_tab = client.application.test_client()
    other_tab.set_cookie(COOKIE, anonymous_cookie.value)
    first = client.get('/api/auth/session')
    second = other_tab.get('/api/auth/session')
    assert first.get_json()['csrf_token'] == second.get_json()['csrf_token'] == token
    assert first.headers.get('Set-Cookie') is None
    assert second.headers.get('Set-Cookie') is None
    login = client.post('/api/auth/login', headers={'X-CSRF-Token': token},
                        json={'username': 'admin', 'password': 'Catalog-test-123'})
    assert login.status_code == 200
