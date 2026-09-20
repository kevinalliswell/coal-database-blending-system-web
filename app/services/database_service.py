"""Shared, explicit Web/desktop migration with SQLite upgrade backups."""
from contextlib import closing
from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
import sys

logger = logging.getLogger(__name__)

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


def _migrate_database(app, resources: Path, database: Path):
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from alembic.script import ScriptDirectory
    from app.extensions import db

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
                # Reuse the escaped path; Flask-Migrate's wrapper rebuilds it
                # without escaping '%' in valid installation directory names.
                # env.py still reads the registered Flask-Migrate extension.
                command.upgrade(config, 'head')
            db.session.remove()
    finally:
        sys.dont_write_bytecode = previous_bytecode



def initialize_database(app):
    from sqlalchemy.engine import make_url
    from flask_migrate import upgrade
    resources = Path(app.config['BASE_DIR'])
    url = make_url(app.config['SQLALCHEMY_DATABASE_URI'])
    if url.get_backend_name() == 'sqlite':
        if not url.database or url.database == ':memory:':
            raise RuntimeError('生产初始化需要持久化 SQLite 文件')
        database = Path(url.database).resolve()
        database.parent.mkdir(parents=True, exist_ok=True)
        _migrate_database(app, resources, database)
    else:
        # MySQL backups are deployment-owned and must precede this command.
        with app.app_context():
            upgrade(directory=str(resources / 'migrations'))
