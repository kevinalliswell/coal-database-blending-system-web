"""Local identity and settings policy; no test-mode authorization exceptions."""
from copy import deepcopy
import hashlib
import math
import re
import time

from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.access import AccessState, AuthSession, LoginAttempt, SystemSettings, User

ROLE_PERMISSIONS = {
    'admin': ('read', 'export', 'data_write', 'calculate', 'admin'),
    'data_manager': ('read', 'export', 'data_write'),
    'calculator': ('read', 'export', 'calculate'),
    'viewer': ('read', 'export'),
}
DEFAULT_SETTINGS = {
    'system_name': 'CBOS 煤炭智能配煤系统', 'organization': '',
    'ratio_basis': 'ar', 'heat_type': 'net_v', 'heat_unit': 'MJ/kg',
    # Heat values stay in kcal/kg at the API and algorithm boundary.
    'constraints': {'heat_min': 6000, 'heat_max': 7800, 'ash_min': 0, 'ash_max': 20,
                    'volatile_min': 8, 'volatile_max': 40, 'fixed_carbon_min': 50,
                    'fixed_carbon_max': 85, 'sulfur_min': 0, 'sulfur_max': 1.2,
                    'price_min': 0, 'price_max': 1500},
    'ga_params': {'population_size': 500, 'max_generations': 3000, 'mutation_rate': .2,
                  'crossover_rate': .85, 'tournament_size': 7, 'early_stopping_patience': 200,
                  'adaptive_mutation': True, 'convergence_threshold': 1e-6,
                  'pareto_solution_limit': 20},
}


class AccessError(ValueError):
    def __init__(self, message, status=400, code='invalid_request'):
        super().__init__(message)
        self.status = status
        self.code = code


def ensure_access_rows():
    """Migrations seed these; explicit create_all test fixtures use this same data."""
    changed = False
    if db.session.get(AccessState, 1) is None:
        db.session.add(AccessState(id=1, initialized=False, lock_version=0)); changed = True
    if db.session.get(SystemSettings, 1) is None:
        db.session.add(SystemSettings(id=1, version=1, payload=deepcopy(DEFAULT_SETTINGS))); changed = True
    if changed:
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # Another request inserted the singleton first.


def setup_required():
    ensure_access_rows()
    return not db.session.get(AccessState, 1).initialized


def user_dict(user):
    return {'id': user.id, 'username': user.username, 'display_name': user.display_name,
            'role': user.role, 'active': user.active,
            'permissions': list(ROLE_PERMISSIONS.get(user.role, ()))}


def validate_password(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise AccessError('密码长度必须为 12–128 个字符')
    return password


def _username(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{3,64}', value):
        raise AccessError('用户名须为 3–64 位字母、数字、点、下划线或连字符')
    return value.lower()


def _display_name(value, username):
    if value is None:
        return username
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        raise AccessError('显示名称须为 1–80 个字符')
    return value.strip()


def _new_user(username, password, display_name, role):
    username = _username(username)
    if not isinstance(role, str) or role not in ROLE_PERMISSIONS:
        raise AccessError('不支持的角色')
    return User(username=username, display_name=_display_name(display_name, username), role=role,
                password_hash=generate_password_hash(validate_password(password)),
                active=True, created_at=int(time.time()))


def _lock_access():
    # Serializes first-admin and last-admin changes, including separate workers.
    db.session.query(AccessState).filter_by(id=1).update(
        {AccessState.lock_version: AccessState.lock_version + 1}, synchronize_session=False)
    db.session.expire_all()


def create_initial_admin(username, password, display_name=None):
    ensure_access_rows()
    user = _new_user(username, password, display_name, 'admin')
    try:
        _lock_access()
        state = db.session.get(AccessState, 1)
        if state.initialized or db.session.query(User.id).first():
            raise AccessError('首位管理员已经初始化', 409, 'already_initialized')
        db.session.add(user)
        state.initialized = True
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()
        raise


def create_user(data):
    if set(data) - {'username', 'password', 'display_name', 'role'}:
        raise AccessError('用户请求包含不支持的字段')
    user = _new_user(data.get('username'), data.get('password'), data.get('display_name'), data.get('role'))
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise AccessError('用户名已存在', 409, 'username_exists')
    return user


def revoke_sessions(user_id):
    db.session.query(AuthSession).filter_by(user_id=user_id).delete(synchronize_session=False)


def update_user(user_id, data):
    if not data or set(data) - {'display_name', 'role', 'active'}:
        raise AccessError('仅支持修改显示名称、角色及启用状态')
    ensure_access_rows()
    try:
        _lock_access()
        user = db.session.get(User, user_id)
        if user is None:
            raise AccessError('用户不存在', 404, 'not_found')
        role = data.get('role', user.role)
        active = data.get('active', user.active)
        if not isinstance(role, str) or role not in ROLE_PERMISSIONS or type(active) is not bool:
            raise AccessError('角色或启用状态无效')
        if user.role == 'admin' and user.active and (role != 'admin' or not active):
            if db.session.query(User).filter_by(role='admin', active=True).count() <= 1:
                raise AccessError('必须保留至少一位启用的管理员', 409, 'last_admin')
        if role != user.role or active != user.active:
            revoke_sessions(user.id)
        user.role, user.active = role, active
        if 'display_name' in data:
            user.display_name = _display_name(data['display_name'], user.username)
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()
        raise


def change_password(user, password, current_password=None, require_current=False):
    validate_password(password)
    if require_current and (not isinstance(current_password, str) or not check_password_hash(user.password_hash, current_password)):
        raise AccessError('当前密码不正确')
    user.password_hash = generate_password_hash(password)
    revoke_sessions(user.id)
    db.session.commit()


def authenticate(username, password):
    # Never reflect whether the account exists, is disabled or is locked.
    supplied = username.lower() if isinstance(username, str) else ''
    key = hashlib.sha256(supplied.encode()).hexdigest()
    now = int(time.time())
    db.session.query(LoginAttempt).filter(LoginAttempt.window_start < now - 900).delete(synchronize_session=False)
    attempt = db.session.get(LoginAttempt, key)
    if attempt and attempt.failures >= 8:
        db.session.commit()
        raise AccessError('登录尝试过多，请 15 分钟后重试', 429, 'login_throttled')
    user = db.session.query(User).filter_by(username=supplied).first()
    valid = (isinstance(password, str) and len(password) <= 128 and user is not None
             and check_password_hash(user.password_hash, password) and user.active)
    if not valid:
        if attempt is None:
            attempt = LoginAttempt(key=key, failures=0, window_start=now)
            db.session.add(attempt)
        attempt.failures += 1
        db.session.commit()
        raise AccessError('用户名或密码不正确', 401, 'invalid_credentials')
    if attempt:
        db.session.delete(attempt)
    db.session.commit()
    return user


def get_settings():
    ensure_access_rows()
    row = db.session.get(SystemSettings, 1)
    return {'version': row.version, **deepcopy(row.payload)}


def _number(value, label, low=0, high=None, integer=False):
    try:
        finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise AccessError(f'{label} 必须是有限数值')
    if value < low or (high is not None and value > high) or (integer and int(value) != value):
        raise AccessError(f'{label} 超出允许范围')
    return int(value) if integer else value


def update_settings(data):
    current = get_settings()
    allowed = set(DEFAULT_SETTINGS) | {'version', 'constraints_confirmed'}
    if set(data) - allowed or type(data.get('version')) is not int:
        raise AccessError('设置字段无效，且必须提供整数版本号')
    if data['version'] != current['version']:
        raise AccessError('设置已由其他用户修改，请刷新后重试', 409, 'settings_conflict')
    proposed = {key: deepcopy(data.get(key, current[key])) for key in DEFAULT_SETTINGS}
    for key, maximum, allow_empty in [('system_name', 80, False), ('organization', 160, True)]:
        value = proposed[key]
        if not isinstance(value, str) or len(value.strip()) > maximum or (not allow_empty and not value.strip()):
            raise AccessError(f'{key} 长度无效')
        proposed[key] = value.strip()
    for key, values in [('ratio_basis', ('ar', 'd')), ('heat_type', ('net_v', 'gr_v')), ('heat_unit', ('MJ/kg', 'kcal/kg'))]:
        if proposed[key] not in values:
            raise AccessError(f'{key} 不支持该取值')
    changed_basis = any(proposed[key] != current[key] for key in ('ratio_basis', 'heat_type'))
    if changed_basis and (data.get('constraints_confirmed') is not True or 'constraints' not in data):
        raise AccessError('修改配比基准或热值类型时，必须重新核实并确认完整约束')
    constraints = proposed['constraints']
    if not isinstance(constraints, dict) or set(constraints) != set(DEFAULT_SETTINGS['constraints']):
        raise AccessError('约束须包含全部六组上下限，不允许额外字段')
    for key in ('heat', 'ash', 'volatile', 'fixed_carbon', 'sulfur', 'price'):
        high = 100 if key in ('ash', 'volatile', 'fixed_carbon', 'sulfur') else None
        lower = _number(constraints[key + '_min'], key + '_min', high=high)
        upper = _number(constraints[key + '_max'], key + '_max', high=high)
        if lower > upper:
            raise AccessError(f'{key} 下限不能大于上限')
    ga = proposed['ga_params']
    allowed_ga = set(DEFAULT_SETTINGS['ga_params']) | {'random_seed'}
    if not isinstance(ga, dict) or set(ga) - allowed_ga or not set(DEFAULT_SETTINGS['ga_params']) <= set(ga):
        raise AccessError('遗传算法参数缺失或包含无效字段')
    limits = {'population_size': (2, 2000, True), 'max_generations': (1, 10000, True),
              'mutation_rate': (0, 1, False), 'crossover_rate': (0, 1, False),
              'tournament_size': (2, 2000, True), 'early_stopping_patience': (1, 10000, True),
              'convergence_threshold': (0, 1, False), 'pareto_solution_limit': (1, 2000, True),
              'random_seed': (0, 4294967295, True)}
    if type(ga['adaptive_mutation']) is not bool:
        raise AccessError('adaptive_mutation 必须是布尔值')
    if ga.get('random_seed', 'absent') is None:
        del ga['random_seed']
    for key, (low, high, integer) in limits.items():
        if key in ga:
            ga[key] = _number(ga[key], key, low, high, integer)
    if ga['tournament_size'] > ga['population_size']:
        raise AccessError('锦标赛大小不能大于种群大小')
    affected = db.session.query(SystemSettings).filter_by(id=1, version=data['version']).update(
        {SystemSettings.payload: proposed, SystemSettings.version: data['version'] + 1}, synchronize_session=False)
    if affected != 1:
        db.session.rollback()
        raise AccessError('设置已由其他用户修改，请刷新后重试', 409, 'settings_conflict')
    db.session.commit()
    db.session.expire_all()
    return get_settings()
