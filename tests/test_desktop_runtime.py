"""Desktop startup, isolated storage, authenticated loopback and parent lifetime."""
import io
import json
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'a1' * 32
HEADERS = {'X-CBOS-Token': TOKEN}


@pytest.fixture
def resources(tmp_path):
    root = tmp_path / 'read-only-install-resources'
    (root / 'frontend' / 'dist' / 'assets').mkdir(parents=True)
    (root / 'frontend' / 'dist' / 'index.html').write_text('<h1>desktop fixture</h1>', encoding='utf-8')
    (root / 'frontend' / 'dist' / 'assets' / 'app.js').write_text('window.desktopFixture=true;', encoding='utf-8')
    (root / 'data').mkdir()
    shutil.copyfile(ROOT / 'data' / 'test_coal_datas.csv', root / 'data' / 'test_coal_datas.csv')
    shutil.copytree(ROOT / 'migrations', root / 'migrations', ignore=shutil.ignore_patterns('__pycache__'))
    return root


def desktop_app(data_dir, resources):
    from desktop.runtime import create_desktop_app
    return create_desktop_app(data_dir, TOKEN, resources)


def close_app(app):
    from app.extensions import db
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


def test_token_protects_health_api_spa_and_assets_before_any_route(tmp_path, resources):
    app = desktop_app(tmp_path / 'user-data', resources)
    try:
        client = app.test_client()
        for route in ['/health', '/api/coals', '/', '/smart-blending', '/assets/app.js']:
            assert client.get(route).status_code == 401
            assert client.get(route, headers={'X-CBOS-Token': 'wrong'}).status_code == 401
            assert client.get(route, headers=HEADERS).status_code == 200
        assert client.open('/api/coals', method='OPTIONS').status_code == 401
        assert b'desktop fixture' in client.get('/', headers=HEADERS).data
        rows = client.get('/api/coals?page_size=0', headers=HEADERS).get_json()['data']
        assert len(rows) == 8
        assert all(coal['analysis_basis'] == 'unknown' for coal in rows)
        assert rows[0]['calorific_value'] == 7419
    finally:
        close_app(app)


def test_user_data_persists_and_deleted_demo_coals_do_not_return(tmp_path, resources, monkeypatch):
    data_dir = tmp_path / 'user data 中文'
    forbidden = tmp_path / 'inherited-production.db'
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{forbidden}')
    initial_files = sorted(str(path.relative_to(resources)) for path in resources.rglob('*'))
    app = desktop_app(data_dir, resources)
    try:
        assert Path(app.config['UPLOAD_FOLDER']) == data_dir / 'uploads'
        client = app.test_client()
        result = client.post('/api/coals', headers=HEADERS, json={
            'name': '我的煤', 'type': '烟煤', 'price': 650, 'calorific_value': 6500,
            'ash_content': 10, 'volatile_matter': 25, 'fixed_carbon': 60, 'total_sulfur': .5,
        })
        assert result.status_code == 200
        uploaded = client.post('/api/coals/upload', headers=HEADERS, data={'file': (
            io.BytesIO((resources / 'data' / 'test_coal_datas.csv').read_bytes()), 'coals.csv')})
        assert uploaded.status_code == 200
        assert list((data_dir / 'uploads').glob('*.csv'))
    finally:
        close_app(app)
    app = desktop_app(data_dir, resources)
    try:
        client = app.test_client()
        coals = client.get('/api/coals?page_size=0', headers=HEADERS).get_json()['data']
        assert len(coals) == 9 and any(coal['name'] == '我的煤' for coal in coals)
        for coal in coals:
            assert client.delete(f'/api/coals/{coal["id"]}', headers=HEADERS).status_code == 200
    finally:
        close_app(app)
    app = desktop_app(data_dir, resources)
    try:
        assert app.test_client().get('/api/coals', headers=HEADERS).get_json()['data'] == []
    finally:
        close_app(app)
    assert not forbidden.exists()
    assert sorted(str(path.relative_to(resources)) for path in resources.rglob('*')) == initial_files
    assert not list((data_dir / 'backups').glob('*.db'))  # no upgrade on an already-current database


def test_old_revision_gets_online_backup_before_upgrade(tmp_path, resources):
    data_dir = tmp_path / 'user-data'
    data_dir.mkdir()
    database = data_dir / 'coal_system.db'
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{database}'}
    env.pop('CBOS_DESKTOP_DATA_DIR', None)
    migrated = subprocess.run([sys.executable, '-m', 'flask', '--app', 'run.py', 'db', 'upgrade',
                               'b3f7b0d5f1a2'], cwd=ROOT, env=env, capture_output=True, text=True)
    assert migrated.returncode == 0, migrated.stderr
    # Keep WAL open so the online backup must include committed data outside the main file.
    with sqlite3.connect(database) as writer:
        writer.execute('pragma journal_mode=WAL')
        writer.execute("insert into coal_data (id,name,type,price,calorific_value,ash_content,volatile_matter,"
                       "fixed_carbon,total_sulfur) values (99,'旧煤','无烟煤',800,7000,10,10,77.5,.5)")
        writer.commit()
        app = desktop_app(data_dir, resources)
        close_app(app)
    backups = list((data_dir / 'backups').glob('*.db'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as saved:
        assert saved.execute('select version_num from alembic_version').fetchone()[0] == 'b3f7b0d5f1a2'
        assert saved.execute('select name,fixed_carbon from coal_data').fetchall() == [('旧煤', 77.5)]
    with sqlite3.connect(database) as current:
        assert current.execute('select analysis_basis,name,fixed_carbon from coal_data').fetchall() == [('unknown', '旧煤', 77.5)]


@pytest.mark.parametrize('existing_revision', [None, 'b3f7b0d5f1a2'])
def test_percent_in_install_and_user_paths_supports_first_start_and_upgrade(tmp_path, resources, existing_revision):
    install = tmp_path / '安装资源 100%'
    shutil.copytree(resources, install)
    data_dir = tmp_path / '用户%资料'
    data_dir.mkdir()
    database = data_dir / 'coal_system.db'
    if existing_revision:
        env = {**os.environ, 'DATABASE_URL': f'sqlite:///{database}'}
        env.pop('CBOS_DESKTOP_DATA_DIR', None)
        prepared = subprocess.run([sys.executable, '-m', 'flask', '--app', 'run.py', 'db',
                                   'upgrade', existing_revision], cwd=ROOT, env=env,
                                  capture_output=True, text=True)
        assert prepared.returncode == 0, prepared.stderr
        with sqlite3.connect(database) as connection:
            connection.execute("insert into coal_data (id,name,type,price,calorific_value,ash_content,"
                               "volatile_matter,fixed_carbon,total_sulfur) "
                               "values (99,'保留原值','无烟煤',800,7000,10,10,77.5,.5)")
    app = desktop_app(data_dir, install)
    try:
        rows = app.test_client().get('/api/coals?page_size=0', headers=HEADERS).get_json()['data']
        assert len(rows) == (1 if existing_revision else 8)
        assert all(row['analysis_basis'] == 'unknown' for row in rows)
        if existing_revision:
            assert (rows[0]['name'], rows[0]['fixed_carbon']) == ('保留原值', 77.5)
        with sqlite3.connect(database) as connection:
            assert connection.execute('select version_num from alembic_version').fetchone()[0] == 'c8a1d24f5e67'
    finally:
        close_app(app)
    backups = list((data_dir / 'backups').glob('*.db'))
    assert len(backups) == (1 if existing_revision else 0)
    if existing_revision:
        with sqlite3.connect(backups[0]) as backup:
            assert backup.execute('select version_num from alembic_version').fetchone()[0] == existing_revision
            assert backup.execute('select name,fixed_carbon from coal_data').fetchall() == [('保留原值', 77.5)]


def test_unversioned_existing_database_is_not_blindly_stamped(tmp_path, resources):
    data_dir = tmp_path / 'user-data'
    data_dir.mkdir()
    database = data_dir / 'coal_system.db'
    with sqlite3.connect(database) as connection:
        connection.execute('create table unknown_business_records (value text)')
        connection.execute("insert into unknown_business_records values ('keep')")
    before = database.read_bytes()
    with pytest.raises(RuntimeError, match='版本|version|schema'):
        desktop_app(data_dir, resources)
    assert database.read_bytes() == before


def test_frozen_resources_resolve_from_meipass_and_require_built_spa(tmp_path, resources, monkeypatch):
    from desktop.runtime import create_desktop_app
    monkeypatch.setattr(sys, '_MEIPASS', str(resources), raising=False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    app = create_desktop_app(tmp_path / 'user-data', TOKEN)
    try:
        assert app.config['SPA_DIST_DIR'] == str(resources / 'frontend' / 'dist')
        assert b'desktop fixture' in app.test_client().get('/', headers=HEADERS).data
    finally:
        close_app(app)
    (resources / 'frontend' / 'dist' / 'index.html').unlink()
    with pytest.raises(RuntimeError, match='资源|frontend'):
        create_desktop_app(tmp_path / 'other-user-data', TOKEN)


def test_desktop_config_never_loads_dotenv(tmp_path):
    env = {**os.environ, 'CBOS_DESKTOP_DATA_DIR': str(tmp_path), 'CBOS_DESKTOP_TOKEN': TOKEN}
    result = subprocess.run([sys.executable, '-c',
                             'import dotenv; dotenv.load_dotenv=lambda: (_ for _ in ()).throw('
                             'AssertionError("desktop must not load .env")); import app.config'],
                            env=env, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_chinese_csv_upload_preserves_extension_and_uses_unique_safe_names(tmp_path, resources):
    data_dir = tmp_path / 'user-data'
    app = desktop_app(data_dir, resources)
    try:
        client = app.test_client()
        names = []
        for filename in ['煤种 样本.csv', '煤种 样本.csv', '../../煤种 样本.csv']:
            response = client.post('/api/coals/upload', headers=HEADERS, data={'file': (
                io.BytesIO((resources / 'data' / 'test_coal_datas.csv').read_bytes()), filename)})
            assert response.status_code == 200, response.get_json()
            payload = response.get_json()
            assert payload['status'] == 'success'
            names.append(payload['filename'])
        assert len(set(names)) == 3
        assert all(Path(name).name == name and name.endswith('.csv') for name in names)
        assert len(list((data_dir / 'uploads').glob('*.csv'))) == 3
    finally:
        close_app(app)


@pytest.mark.parametrize('relative,token', [(True, TOKEN), (False, ''),
                                           (False, 'invalid'), (False, 'g' * 64)])
def test_startup_rejects_invalid_desktop_contract(relative, token, resources):
    from desktop.runtime import create_desktop_app
    data_dir = 'relative-path' if relative else resources.parent / 'user-data'
    with pytest.raises(ValueError):
        create_desktop_app(data_dir, token, resources)


def test_waitress_socket_is_only_ipv4_loopback(tmp_path, resources):
    from desktop.runtime import create_loopback_server, stop_server
    app = desktop_app(tmp_path / 'data', resources)
    server = create_loopback_server(app)
    try:
        host, port = server.socket.getsockname()
        assert host == '127.0.0.1' and port > 0
    finally:
        stop_server(server)
        close_app(app)


def test_backend_entry_handshake_eof_shutdown_and_environment_isolation(tmp_path):
    data_dir = tmp_path / 'desktop-data'
    forbidden = tmp_path / 'must-not-open.db'
    env = {**os.environ, 'CBOS_DESKTOP_DATA_DIR': str(data_dir), 'CBOS_DESKTOP_TOKEN': TOKEN,
           'DATABASE_URL': f'sqlite:///{forbidden}', 'HOST': '0.0.0.0', 'PORT': 'not-an-integer'}
    child = subprocess.Popen([sys.executable, str(ROOT / 'desktop' / 'backend_entry.py')],
                             cwd=tmp_path, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding='utf-8')
    lines = queue.Queue()
    threading.Thread(target=lambda: lines.put(child.stdout.readline()), daemon=True).start()
    try:
        line = lines.get(timeout=30)
        assert line, child.stderr.read()
        ready = json.loads(line)
        assert set(ready) == {'type', 'port'} and ready['type'] == 'ready'
        assert isinstance(ready['port'], int) and 0 < ready['port'] < 65536
        url = f'http://127.0.0.1:{ready["port"]}/health'
        with pytest.raises(HTTPError) as rejected:
            urlopen(url, timeout=3)
        assert rejected.value.code == 401
        with urlopen(Request(url, headers=HEADERS), timeout=3) as response:
            assert json.load(response)['status'] == 'ok'
        child.stdin.close()
        child.stdin = None
        remaining_stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0, stderr
        assert remaining_stdout == ''
        assert TOKEN not in stderr
        assert not forbidden.exists()
        with pytest.raises(OSError):
            urlopen(Request(url, headers=HEADERS), timeout=1)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
