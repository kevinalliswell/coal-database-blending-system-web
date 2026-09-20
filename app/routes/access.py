"""Authentication endpoints and centralized API authorization."""
import hashlib
import hmac
import os
import secrets
import time

import click
from flask import Blueprint, current_app, g, jsonify, request

from app.extensions import db
from app.models.access import AuthSession, User
from app.services.access_service import (
    AccessError, ROLE_PERMISSIONS, authenticate, change_password, create_initial_admin,
    create_user, get_settings, setup_required, update_settings, update_user, user_dict,
)

bp = Blueprint('access', __name__, url_prefix='/api')
COOKIE = 'cbos_session'
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def _body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise AccessError('请求体必须是 JSON 对象')
    return value


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _session():
    if not hasattr(g, 'access_session'):
        token = request.cookies.get(COOKIE, '')
        row = db.session.get(AuthSession, _digest(token)) if token and len(token) <= 128 else None
        if row is not None and row.expires_at <= int(time.time()):
            db.session.delete(row); db.session.commit(); row = None
        g.access_session = row
        user = db.session.get(User, row.user_id) if row and row.user_id is not None else None
        g.current_user = g.user = user if user and user.active else None
    return g.access_session


def _new_session(user=None):
    previous = _session()
    if previous:
        db.session.delete(previous)
    token = secrets.token_urlsafe(32)
    ttl = 8 * 3600 if user else 15 * 60
    row = AuthSession(token_hash=_digest(token), csrf_token=secrets.token_urlsafe(32),
                      user_id=user.id if user else None, expires_at=int(time.time()) + ttl)
    db.session.query(AuthSession).filter(AuthSession.expires_at <= int(time.time())).delete(synchronize_session=False)
    db.session.add(row)
    db.session.commit()
    g.access_session, g.current_user, g.user = row, user, user
    g.access_cookie = (token, ttl)
    return row


def _session_response():
    row = _session() or _new_session()
    return {'status': 'success', 'user': user_dict(g.current_user) if g.current_user else None,
            'csrf_token': row.csrf_token, 'setup_required': setup_required(),
            'desktop_mode': bool(current_app.config.get('DESKTOP_MODE'))}


def _check_csrf():
    row = _session()
    supplied = request.headers.get('X-CSRF-Token', '')
    if not row or not supplied or not supplied.isascii() or not hmac.compare_digest(row.csrf_token, supplied):
        raise AccessError('会话校验失败，请刷新页面后重试', 403, 'csrf_failed')
    origin = request.headers.get('Origin')
    expected = current_app.config.get('PUBLIC_ORIGIN') or request.host_url.rstrip('/')
    desktop = current_app.config.get('DESKTOP_MODE') and request.environ.get('cbos.transport_authenticated') is True
    if origin and origin != ('cbos://app' if desktop else expected):
        raise AccessError('不允许跨站请求', 403, 'origin_rejected')


def _permissions_for_request():
    path, method = request.path.rstrip('/'), request.method
    if path.startswith('/api/users'):
        return {'admin'}
    if path == '/api/settings':
        return {'read'} if method in SAFE_METHODS else {'admin'}
    if path.startswith('/api/auth/') or path == '/api/system/info':
        return {'read'}
    if 'export' in path or path.endswith('/template'):
        return {'export'}
    if path == '/api/assays/preview':
        return {'data_write', 'calculate'}
    if path.startswith('/api/optimization'):
        return {'read'} if method in SAFE_METHODS else {'calculate'}
    if path.startswith('/api/replacement_ratio/history'):
        return {'read'}
    if path in ('/api/calculate_theory_ratio', '/api/calculate_actual_ratio'):
        return {'calculate'}
    if any(path == prefix or path.startswith(prefix + '/') for prefix in (
            '/api/coals', '/api/coal', '/api/upload', '/api/catalog', '/api/batches', '/api/assays')):
        return {'read'} if method in SAFE_METHODS else {'data_write'}
    # Unknown endpoints do not accidentally become public when added later.
    return {'admin'}


def authorize_api():
    if not request.path.startswith('/api/'):
        return
    _session()
    public = ((request.path == '/api/auth/session' and request.method == 'GET') or
              (request.path in ('/api/auth/login', '/api/auth/setup') and request.method == 'POST'))
    if not public and not g.current_user:
        raise AccessError('请先登录', 401, 'login_required')
    if request.method not in SAFE_METHODS:
        _check_csrf()
    if not public and not (_permissions_for_request() & set(ROLE_PERMISSIONS[g.current_user.role])):
        raise AccessError('当前账号没有此操作权限', 403, 'permission_denied')


@bp.get('/auth/session')
def session_info():
    return jsonify(_session_response())


@bp.post('/auth/setup')
def setup():
    if not current_app.config.get('DESKTOP_MODE') or request.environ.get('cbos.transport_authenticated') is not True:
        raise AccessError('Web 部署请使用服务器上的 users create-admin 命令初始化', 403, 'setup_transport_required')
    data = _body()
    user = create_initial_admin(data.get('username'), data.get('password'), data.get('display_name'))
    _new_session(user)
    return jsonify(_session_response()), 201


@bp.post('/auth/login')
def login():
    data = _body()
    user = authenticate(data.get('username'), data.get('password'))
    _new_session(user)
    return jsonify(_session_response())


@bp.post('/auth/logout')
def logout():
    db.session.delete(_session()); db.session.commit()
    g.access_session = None
    g.access_cookie = ('', 0)
    return jsonify(status='success')


@bp.put('/auth/password')
def password():
    data = _body()
    change_password(g.current_user, data.get('password'), data.get('current_password'), require_current=True)
    g.access_cookie = ('', 0)
    return jsonify(status='success', message='密码已修改，请重新登录')


@bp.get('/users')
def users():
    return jsonify(status='success', data=[user_dict(user) for user in db.session.query(User).order_by(User.id)])


@bp.post('/users')
def add_user():
    return jsonify(status='success', data=user_dict(create_user(_body()))), 201


@bp.patch('/users/<int:user_id>')
def edit_user(user_id):
    return jsonify(status='success', data=user_dict(update_user(user_id, _body())))


@bp.put('/users/<int:user_id>/password')
def reset_password(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise AccessError('用户不存在', 404, 'not_found')
    change_password(user, _body().get('password'))
    if user.id == g.current_user.id:
        g.access_cookie = ('', 0)
    return jsonify(status='success')


@bp.get('/settings')
def settings():
    return jsonify(status='success', data=get_settings())


@bp.put('/settings')
def save_settings():
    return jsonify(status='success', data=update_settings(_body()))


@bp.get('/system/info')
def system_info():
    from app.build_info import build_info
    return jsonify(status='success', data={**build_info(),
        'mode': 'desktop' if current_app.config.get('DESKTOP_MODE') else 'web',
        'storage_mode': current_app.config.get('DATA_STORAGE_MODE', 'sqlite')})


def init_access(app):
    """Called once by the factory after extensions; safe for explicit test fixtures."""
    if app.extensions.get('cbos_access'):
        return
    app.extensions['cbos_access'] = True
    app.register_blueprint(bp)
    app.before_request(authorize_api)

    @app.errorhandler(AccessError)
    def access_error(error):
        db.session.rollback()
        return jsonify(status='error', message=str(error), code=error.code), error.status

    @app.after_request
    def access_response(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        if hasattr(g, 'access_cookie'):
            value, ttl = g.access_cookie
            response.set_cookie(COOKIE, value, max_age=ttl, httponly=True,
                                secure=bool(app.config.get('SESSION_COOKIE_SECURE') or request.is_secure),
                                samesite='Lax', path='/')
        return response

    @app.cli.group('users')
    def users_cli():
        """Manage this deployment's local accounts."""

    @users_cli.command('create-admin')
    @click.option('--username', prompt='管理员账号')
    @click.option('--display-name', default=None)
    def create_admin_cli(username, display_name):
        password = click.prompt('密码（至少 12 位）', hide_input=True, confirmation_prompt=True)
        try:
            user = create_initial_admin(username, password, display_name)
        except AccessError as error:
            raise click.ClickException(str(error))
        click.echo(f'已创建管理员 {user.username}')

    app.cli.add_command(create_admin_cli, 'init-admin')

    @users_cli.command('reset-password')
    @click.option('--username', prompt='账号')
    def reset_password_cli(username):
        password = click.prompt('新密码（至少 12 位）', hide_input=True, confirmation_prompt=True)
        user = db.session.query(User).filter_by(username=username.lower()).first()
        if user is None:
            raise click.ClickException('用户不存在')
        try:
            change_password(user, password)
        except AccessError as error:
            raise click.ClickException(str(error))
        click.echo('密码已更新，全部会话已撤销')
