"""Lifecycle evidence must detect changed values, not merely unchanged counts."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


SCRIPT = Path(__file__).parents[1] / 'desktop/scripts/lifecycle-data.py'
spec = importlib.util.spec_from_file_location('lifecycle_data', SCRIPT)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


@pytest.fixture
def data_dir(tmp_path):
    directory = tmp_path / '用户资料 100% #1'
    directory.mkdir()
    (directory / '.app-secret').write_text('private-secret-never-print', encoding='utf-8')
    with sqlite3.connect(directory / 'coal_system.db') as db:
        db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE app_user (id INTEGER PRIMARY KEY, password_hash TEXT NOT NULL);
            CREATE TABLE assay_revisions (id INTEGER PRIMARY KEY, raw TEXT, sample BLOB);
            CREATE TABLE optimization_history (id INTEGER PRIMARY KEY, payload TEXT);
            CREATE TABLE auth_session (token_hash TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES app_user(id), csrf_token TEXT, expires_at INTEGER);
            CREATE TABLE login_attempt (key TEXT PRIMARY KEY, failures INTEGER, window_start INTEGER);
            INSERT INTO app_user VALUES (1, 'scrypt:private-password-hash');
            INSERT INTO assay_revisions VALUES (1, '{"price":800,"source":"private-assay-source"}', X'00FF');
            INSERT INTO optimization_history VALUES (1, '{"ratios":[0.4,0.6]}');
            INSERT INTO auth_session VALUES ('private-session',1,'private-csrf',10);
            INSERT INTO login_attempt VALUES ('private-login-key',1,10);
        ''')
    return directory


def execute(data_dir, sql, parameters=()):
    with sqlite3.connect(data_dir / 'coal_system.db') as db:
        db.execute(sql, parameters)


def test_snapshot_is_deterministic_read_only_and_does_not_expose_values(data_dir):
    original = {p.name: p.read_bytes() for p in data_dir.iterdir()}
    first = lifecycle.snapshot_data(data_dir)
    assert first == lifecycle.snapshot_data(data_dir)
    assert first['integrity_check'] == first['foreign_key_check'] == 'ok'
    assert first['tables']['assay_revisions']['row_count'] == 1
    assert len(first['tables']['assay_revisions']['sha256']) == 64
    assert {p.name: p.read_bytes() for p in data_dir.iterdir()} == original
    encoded = json.dumps(first)
    for private in ('private-secret-never-print', 'scrypt:private-password-hash',
                    'private-session', 'private-csrf', 'private-login-key', 'ratios', 'private-assay-source'):
        assert private not in encoded


@pytest.mark.parametrize('table,column,value', [
    ('app_user', 'password_hash', 'different-password-hash'),
    ('assay_revisions', 'raw', '{"price":900}'),
    ('optimization_history', 'payload', '{"ratios":[0.5,0.5]}'),
])
def test_upgrade_rejects_changed_values_with_identical_row_counts(data_dir, table, column, value):
    before = lifecycle.snapshot_data(data_dir)
    execute(data_dir, f'UPDATE {table} SET {column}=?', (value,))
    after = lifecycle.snapshot_data(data_dir)
    assert before['tables'][table]['row_count'] == after['tables'][table]['row_count']
    with pytest.raises(ValueError, match=table):
        lifecycle.compare_upgrade(before, after)


def test_upgrade_allows_only_runtime_rows_to_change(data_dir):
    before = lifecycle.snapshot_data(data_dir)
    execute(data_dir, 'DELETE FROM auth_session')
    execute(data_dir, 'UPDATE login_attempt SET failures=failures+1')
    after = lifecycle.snapshot_data(data_dir)
    assert lifecycle.compare_upgrade(before, after)['status'] == 'passed'
    with pytest.raises(ValueError, match='auth_session|login_attempt'):
        lifecycle.compare_uninstall(before, after)


@pytest.mark.parametrize('sql', [
    'ALTER TABLE auth_session ADD COLUMN extra TEXT',
    'DROP TABLE login_attempt',
    'CREATE TABLE unexpected (value TEXT)',
    'CREATE INDEX runtime_expiry ON auth_session (expires_at)',
])
def test_upgrade_does_not_ignore_runtime_schema_or_table_set_changes(data_dir, sql):
    before = lifecycle.snapshot_data(data_dir)
    execute(data_dir, sql)
    with pytest.raises(ValueError):
        lifecycle.compare_upgrade(before, lifecycle.snapshot_data(data_dir))


@pytest.mark.parametrize('compare', ['compare_upgrade', 'compare_uninstall'])
def test_lifecycle_rejects_changed_secret(data_dir, compare):
    before = lifecycle.snapshot_data(data_dir)
    (data_dir / '.app-secret').write_text('replacement-secret', encoding='utf-8')
    with pytest.raises(ValueError, match='secret'):
        getattr(lifecycle, compare)(before, lifecycle.snapshot_data(data_dir))


def test_uninstall_requires_exact_files_even_if_sql_rows_are_unchanged(data_dir):
    before = lifecycle.snapshot_data(data_dir)
    assert lifecycle.compare_uninstall(before, lifecycle.snapshot_data(data_dir))['status'] == 'passed'
    execute(data_dir, 'PRAGMA user_version=17')
    after = lifecycle.snapshot_data(data_dir)
    assert before['tables'] == after['tables']
    assert lifecycle.compare_upgrade(before, after)['status'] == 'passed'
    with pytest.raises(ValueError, match='coal_system.db'):
        lifecycle.compare_uninstall(before, after)


@pytest.mark.parametrize('filename', ['coal_system.db', '.app-secret'])
def test_missing_database_or_secret_is_rejected_without_creating_files(data_dir, filename):
    (data_dir / filename).unlink()
    with pytest.raises(ValueError, match=filename):
        lifecycle.snapshot_data(data_dir)
    assert not (data_dir / filename).exists()


@pytest.mark.parametrize('content', [b'', b'not a SQLite database', b'SQLite format 3\0' + b'\0' * 200])
def test_corrupt_database_is_rejected(data_dir, content):
    (data_dir / 'coal_system.db').write_bytes(content)
    with pytest.raises(ValueError, match='SQLite|database'):
        lifecycle.snapshot_data(data_dir)


def test_foreign_key_violation_is_rejected(data_dir):
    execute(data_dir, 'UPDATE auth_session SET user_id=999')
    with pytest.raises(ValueError, match='foreign key'):
        lifecycle.snapshot_data(data_dir)


def test_row_hash_is_order_independent_and_preserves_sqlite_value_types(data_dir):
    execute(data_dir, 'CREATE TABLE "odd "" name" (value)')
    with sqlite3.connect(data_dir / 'coal_system.db') as db:
        db.executemany('INSERT INTO "odd "" name" VALUES (?)', [(None,), (1,), (1.25,), ('1',), (b'1',)])
    before = lifecycle.snapshot_data(data_dir)
    with sqlite3.connect(data_dir / 'coal_system.db') as db:
        db.execute('DELETE FROM "odd "" name"')
        db.executemany('INSERT INTO "odd "" name" VALUES (?)', [(b'1',), ('1',), (1.25,), (1,), (None,)])
    after = lifecycle.snapshot_data(data_dir)
    assert before['tables']['odd " name'] == after['tables']['odd " name']
    execute(data_dir, 'UPDATE "odd "" name" SET value=? WHERE typeof(value)=?', ('1', 'blob'))
    with pytest.raises(ValueError, match='odd'):
        lifecycle.compare_upgrade(after, lifecycle.snapshot_data(data_dir))


def test_wal_data_is_included_without_touching_original_sidecars(data_dir):
    db = sqlite3.connect(data_dir / 'coal_system.db')
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA wal_autocheckpoint=0')
        db.execute('INSERT INTO optimization_history VALUES (?,?)', (2, '{"wal":"committed"}'))
        db.commit()
        original = {p.name: p.read_bytes() for p in data_dir.iterdir()}
        snapshot = lifecycle.snapshot_data(data_dir)
        assert snapshot['tables']['optimization_history']['row_count'] == 2
        assert {'coal_system.db-wal', 'coal_system.db-shm'} <= snapshot['files'].keys()
        assert {p.name: p.read_bytes() for p in data_dir.iterdir()} == original
        assert lifecycle.compare_uninstall(snapshot, lifecycle.snapshot_data(data_dir))['status'] == 'passed'
    finally:
        db.close()
    with pytest.raises(ValueError, match='coal_system.db'):
        lifecycle.compare_uninstall(snapshot, lifecycle.snapshot_data(data_dir))


def test_uninstall_rejects_added_sidecar_with_unchanged_logical_data(data_dir):
    before = lifecycle.snapshot_data(data_dir)
    # A SHM file without WAL is ignored by this rollback-journal database.
    (data_dir / 'coal_system.db-shm').write_bytes(b'leftover shared-memory file')
    after = lifecycle.snapshot_data(data_dir)
    assert before['tables'] == after['tables']
    with pytest.raises(ValueError, match='coal_system.db-shm'):
        lifecycle.compare_uninstall(before, after)


def test_concurrent_database_change_during_copy_is_rejected(data_dir, monkeypatch):
    copy_file = lifecycle.shutil.copyfile

    def copy_and_change(source, destination):
        result = copy_file(source, destination)
        if source.name == 'coal_system.db':
            execute(data_dir, 'UPDATE app_user SET password_hash=?', ('changed-during-copy',))
        return result

    monkeypatch.setattr(lifecycle.shutil, 'copyfile', copy_and_change)
    with pytest.raises(ValueError, match='changed while copying'):
        lifecycle.snapshot_data(data_dir)


@pytest.mark.parametrize('compare', ['compare_upgrade', 'compare_uninstall'])
def test_missing_snapshot_evidence_cannot_pass(compare):
    with pytest.raises(ValueError):
        getattr(lifecycle, compare)({}, {})
