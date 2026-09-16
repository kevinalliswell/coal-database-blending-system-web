"""Authenticated loopback service with writable user data and bundled resources."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hmac
import json
import logging
import os
from pathlib import Path
import re
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
        return self.app(environ, start_response)


def _database_state(database: Path):
    if not database.exists() or database.stat().st_size == 0:
        return True, None
    with closing(sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)) as connection:
        tables = {row[0] for row in connection.execute(
            "select name from sqlite_master where type='table' and name not like 'sqlite_%'")}
        if not tables:
            return True, None
        if 'alembic_version' not in tables:
            raise RuntimeError('现有数据库缺少迁移版本记录；请先核实 schema 并迁移，桌面版不会自动 stamp。')
        versions = connection.execute('select version_num from alembic_version').fetchall()
        if len(versions) != 1:
            raise RuntimeError('现有数据库迁移版本无效；请先核实 schema，原数据未修改。')
        return False, versions[0][0]


def _online_backup(database: Path) -> Path:
    directory = database.parent / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = directory / f'coal_system-{timestamp}.db'
    # SQLite's backup API includes committed WAL pages; copying the file does not.
    with closing(sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
    return backup


def _migrate_and_seed(app, resources: Path, database: Path):
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    from flask_migrate import upgrade
    from app.extensions import db
    from app.services.coal_data_service import seed_from_csv

    migrations = resources / 'migrations'
    config = AlembicConfig(str(migrations / 'alembic.ini'))
    config.set_main_option('script_location', str(migrations).replace('%', '%%'))
    # Dynamic Alembic imports must not create __pycache__ in the install folder.
    previous_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        scripts = ScriptDirectory.from_config(config)
        head = scripts.get_current_head()
        fresh, revision = _database_state(database)
        if revision is not None:
            if revision not in {item.revision for item in scripts.walk_revisions()}:
                raise RuntimeError('数据库迁移版本不属于本应用，请使用匹配版本，原数据未修改。')
            if revision != head:
                backup = _online_backup(database)
                logger.info('数据库升级前已备份至 %s', backup)
        with app.app_context():
            if fresh or revision != head:
                upgrade(directory=str(migrations))
            if fresh:
                summary = seed_from_csv(resources / 'data' / 'test_coal_datas.csv')
                if summary.skipped_count or not summary.created_count:
                    raise RuntimeError('内置示例煤导入失败；请检查安装资源。')
            db.session.remove()
    finally:
        sys.dont_write_bytecode = previous_bytecode


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
    required_files = ['data/test_coal_datas.csv', 'migrations/alembic.ini', 'migrations/env.py']
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
        'SECRET_KEY': token, 'DATA_STORAGE_MODE': 'sqlite',
        'DATA_DIR': str(data_dir), 'UPLOAD_FOLDER': str(data_dir / 'uploads'),
        'DATABASE_PATH': str(database), 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{database.as_posix()}',
        'COAL_DATA_PATH': str(resources / 'data' / 'test_coal_datas.csv'),
        'SPA_DIST_DIR': str(resources / 'frontend' / 'dist'), 'AUTO_INITIALIZE_COAL_DATA': False,
    })
    try:
        _migrate_and_seed(app, resources, database)
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
