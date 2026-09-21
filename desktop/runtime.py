"""Authenticated loopback service with writable user data and bundled resources."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import threading

logger = logging.getLogger(__name__)


def resource_root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


class TokenMiddleware:
    """Authenticate before Flask routing, including static files and OPTIONS."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode('ascii')

    def __call__(self, environ, start_response):
        supplied = environ.get('HTTP_X_CBOS_TOKEN', '').encode('utf-8')
        if not hmac.compare_digest(supplied, self.token):
            body = b'{"status":"error","message":"Unauthorized"}'
            start_response('401 Unauthorized', [('Content-Type', 'application/json'),
                                                ('Content-Length', str(len(body))),
                                                ('Cache-Control', 'no-store')])
            return [body]
        environ['cbos.transport_authenticated'] = True
        return self.app(environ, start_response)


def persistent_app_secret(data_dir: Path) -> str:
    """Application secret belongs to the data, not the per-launch transport."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / '.app-secret'
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(secrets.token_hex(32))
            stream.flush()
            os.fsync(stream.fileno())
    secret = path.read_text(encoding='ascii').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', secret):
        raise RuntimeError('本机应用密钥文件损坏，请恢复数据备份；不会自动替换密钥。')
    return secret


from app.services.database_service import _database_state, _online_backup, _migrate_database


@contextmanager
def exclusive_data_lock(data_dir: Path):
    """OS lock is released on process exit, including crashes; no stale PID file."""
    data_dir = Path(data_dir)
    if not data_dir.is_absolute():
        raise ValueError('数据目录必须为绝对路径')
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / '.backend.lock').open('a+b') as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('数据目录正在使用，请先完全关闭 CBOS，再执行账号恢复。') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def reset_local_password(data_dir: Path, username: str, password: str):
    """Local recovery only; caller holds the data lock and collects hidden input."""
    data_dir = Path(data_dir)
    database = data_dir / 'coal_system.db'
    if not data_dir.is_absolute() or not database.is_file():
        raise ValueError('恢复操作只允许指定包含现有 coal_system.db 的绝对数据目录')
    with closing(sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)) as connection:
        exists = connection.execute("select name from sqlite_master where type='table' and name='app_user'").fetchone()
        if not exists:
            raise ValueError('现有数据库尚无用户表，请先使用匹配版本正常升级')
    from app import create_app
    from app.extensions import db
    from app.models.access import User
    from app.services.access_service import change_password
    app = create_app('production', config_overrides={
        'DESKTOP_MODE': True, 'DEBUG': False, 'TESTING': False,
        'SECRET_KEY': persistent_app_secret(data_dir), 'DATA_STORAGE_MODE': 'sqlite',
        'DATA_DIR': str(data_dir), 'UPLOAD_FOLDER': str(data_dir / 'uploads'),
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database.as_posix()}',
    })
    with app.app_context():
        try:
            user = db.session.query(User).filter_by(username=username.lower()).first()
            if user is None:
                raise ValueError('指定账号不存在；恢复命令不会创建账号')
            change_password(user, password)
        finally:
            db.session.remove(); db.engine.dispose()


def create_desktop_app(data_dir=None, token=None, resources=None):
    """Create and migrate before listening; never inherit a web DATABASE_URL."""
    data_dir = data_dir if data_dir is not None else os.environ.get('CBOS_DESKTOP_DATA_DIR', '')
    token = token if token is not None else os.environ.get('CBOS_DESKTOP_TOKEN', '')
    if not data_dir or not Path(data_dir).is_absolute():
        raise ValueError('CBOS_DESKTOP_DATA_DIR 必须是用户数据目录的绝对路径')
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', token):
        raise ValueError('CBOS_DESKTOP_TOKEN 必须为每次启动生成的 64 位十六进制令牌')
    data_dir = Path(data_dir).resolve()
    resources = Path(resources).resolve() if resources is not None else resource_root()
    required_files = ['migrations/alembic.ini', 'migrations/env.py']
    if getattr(sys, 'frozen', False):
        required_files.append('frontend/dist/index.html')
    for required in required_files:
        if not (resources / required).is_file():
            raise RuntimeError(f'安装资源缺失: {required}')
    database = data_dir / 'coal_system.db'
    from app import create_app
    from app.extensions import db
    app = create_app('production', config_overrides={
        'DESKTOP_MODE': True, 'DEBUG': False, 'TESTING': False,
        'SECRET_KEY': persistent_app_secret(data_dir), 'DATA_STORAGE_MODE': 'sqlite',
        'DATA_DIR': str(data_dir), 'UPLOAD_FOLDER': str(data_dir / 'uploads'),
        'DATABASE_PATH': str(database), 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database.as_posix()}',
        'SPA_DIST_DIR': str(resources / 'frontend' / 'dist'), 'AUTO_INITIALIZE_COAL_DATA': False,
    })
    try:
        _migrate_database(app, resources, database)
    except Exception:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        raise
    app.wsgi_app = TokenMiddleware(app.wsgi_app, token)
    return app


def create_loopback_server(app):
    from waitress import create_server
    return create_server(app, host='127.0.0.1', port=0, ipv4=True, ipv6=False,
                         threads=4, asyncore_loop_timeout=.2, ident='CBOS')


def stop_server(server):
    from waitress import wasyncore
    server.close()
    server.task_dispatcher.shutdown(timeout=3)
    wasyncore.close_all(map=server._map, ignore_all=True)


def run_backend(protocol_stdout=None, parent_stdin=None) -> int:
    """The parent holds stdin open; EOF is the local service's shutdown signal."""
    protocol_stdout = protocol_stdout if protocol_stdout is not None else sys.stdout
    parent_stdin = parent_stdin if parent_stdin is not None else sys.stdin
    if protocol_stdout is None or parent_stdin is None:
        raise RuntimeError('桌面后端需要父进程提供 stdin/stdout 管道')
    app = create_desktop_app()
    from app.extensions import db
    server = create_loopback_server(app)
    serving = threading.Thread(target=server.run, name='cbos-loopback', daemon=True)
    serving.start()
    try:
        protocol_stdout.write(json.dumps({'type': 'ready', 'port': int(server.effective_port)}) + '\n')
        protocol_stdout.flush()
        while parent_stdin.read(1):
            pass
    finally:
        stop_server(server)
        serving.join(timeout=2)
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
    return 0
