"""Read-only SQLite evidence for a stopped application's lifecycle checks.

Only structure, counts and hashes leave this module. A private temporary copy
includes WAL data and prevents SQLite readers from modifying original SHM files.
Callers must stop the application first; detected concurrent writes fail closed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile


DATABASE = 'coal_system.db'
SECRET = '.app-secret'
FILE_NAMES = (DATABASE, SECRET, DATABASE + '-wal', DATABASE + '-shm')
# These are the only runtime tables in the access models that login may change.
# Their schemas are still checked during upgrades; all rows count on uninstall.
RUNTIME_TABLES = frozenset({'auth_session', 'login_attempt'})


def _file_evidence(directory: Path) -> dict:
    evidence = {}
    for name in FILE_NAMES:
        path = directory / name
        if not path.is_file():
            if name in (DATABASE, SECRET) or path.exists():
                raise ValueError(f'Missing or invalid lifecycle file: {name}')
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        evidence[name] = {'sha256': digest, 'bytes': path.stat().st_size}
    return evidence


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                      sort_keys=True, allow_nan=False).encode('utf-8')


def _cell(value):
    # Type tags distinguish a BLOB b'1', TEXT '1', INTEGER 1 and REAL 1.0.
    if value is None:
        return ['null']
    if isinstance(value, bytes):
        return ['blob', value.hex()]
    if isinstance(value, str):
        return ['text', value]
    if isinstance(value, int):
        return ['integer', str(value)]
    if isinstance(value, float):
        return ['real', value.hex()]
    raise ValueError('Unsupported SQLite value type')


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_evidence(connection: sqlite3.Connection) -> dict:
    tables = {}
    names = connection.execute(
        "SELECT name, sql FROM sqlite_schema WHERE type='table' "
        "AND substr(name,1,7) != 'sqlite_' ORDER BY name"
    ).fetchall()
    if not names:
        raise ValueError('SQLite database has no application tables')
    for name, schema in names:
        columns = [dict(zip(('cid', 'name', 'type', 'notnull', 'dflt_value', 'pk', 'hidden'), row))
                   for row in connection.execute(f'PRAGMA table_xinfo({_quoted(name)})')]
        # Include explicitly created indexes/triggers as part of the table schema.
        objects = [dict(zip(('type', 'name', 'sql'), row)) for row in connection.execute(
            "SELECT type,name,sql FROM sqlite_schema WHERE tbl_name=? "
            "AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name", (name,))]
        structure = {'schema_sql': schema, 'columns': columns, 'schema_objects': objects}
        rows = sorted(_json_bytes([_cell(value) for value in row])
                      for row in connection.execute(f'SELECT * FROM {_quoted(name)}'))
        digest = hashlib.sha256(_json_bytes(structure))
        for row in rows:
            digest.update(len(row).to_bytes(8, 'big'))
            digest.update(row)
        tables[name] = {**structure, 'row_count': len(rows), 'sha256': digest.hexdigest()}
    return tables


def snapshot_data(data_dir: str | Path) -> dict:
    """Return hashes for existing SQLite data without opening it for writes.

    Raw values, hashes stored in user records, and the application secret are
    never included in the report. File hashes include existing WAL/SHM sidecars.
    """
    directory = Path(data_dir)
    try:
        files = _file_evidence(directory)
        with tempfile.TemporaryDirectory(prefix='cbos-lifecycle-snapshot-') as temporary:
            copied = Path(temporary)
            for name in files:
                shutil.copyfile(directory / name, copied / name)
            if _file_evidence(copied) != files or _file_evidence(directory) != files:
                raise ValueError('Lifecycle files changed while copying; stop the application')
            database = copied / DATABASE
            with database.open('rb') as stream:
                if stream.read(16) != b'SQLite format 3\0':
                    raise ValueError('Invalid SQLite database header')
            connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
            try:
                connection.execute('PRAGMA query_only=ON')
                connection.execute('BEGIN')
                if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('SQLite integrity check failed')
                if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise ValueError('SQLite foreign key check failed')
                tables = _table_evidence(connection)
            finally:
                connection.close()
        if _file_evidence(directory) != files:
            raise ValueError('Lifecycle files changed during snapshot; stop the application')
    except (OSError, sqlite3.Error):
        # SQLite errors may include application content; do not copy them to logs.
        raise ValueError('Unable to read valid SQLite lifecycle data') from None
    return {'schema_version': 1, 'integrity_check': 'ok', 'foreign_key_check': 'ok',
            'tables': tables, 'files': files}


def _validate_snapshot(snapshot: dict) -> None:
    if (not isinstance(snapshot, dict) or snapshot.get('schema_version') != 1
            or snapshot.get('integrity_check') != 'ok' or snapshot.get('foreign_key_check') != 'ok'
            or not isinstance(snapshot.get('tables'), dict) or not snapshot['tables']
            or not isinstance(snapshot.get('files'), dict)
            or not {DATABASE, SECRET} <= snapshot['files'].keys()):
        raise ValueError('Missing or invalid lifecycle snapshot evidence')
    for evidence in [*snapshot['tables'].values(), *snapshot['files'].values()]:
        digest = evidence.get('sha256') if isinstance(evidence, dict) else None
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in '0123456789abcdef' for char in digest)):
            raise ValueError('Invalid lifecycle snapshot digest')


def _compare_tables(before: dict, after: dict, *, allow_runtime: bool) -> None:
    _validate_snapshot(before)
    _validate_snapshot(after)
    if before['tables'].keys() != after['tables'].keys():
        raise ValueError('Lifecycle table set changed')
    for name, original in before['tables'].items():
        current = after['tables'][name]
        if allow_runtime and name in RUNTIME_TABLES:
            fields = ('schema_sql', 'columns', 'schema_objects')
            if any(original.get(field) != current.get(field) for field in fields):
                raise ValueError(f'Runtime table schema changed: {name}')
        elif original != current:
            raise ValueError(f'Persistent table evidence changed: {name}')


def compare_upgrade(before: dict, after: dict) -> dict:
    """Require identical persistent schema/rows and secret; permit login changes."""
    _compare_tables(before, after, allow_runtime=True)
    if before['files'][SECRET] != after['files'][SECRET]:
        raise ValueError('Application secret changed during upgrade')
    return {'status': 'passed', 'kind': 'upgrade', 'secret_preserved': True,
            'persistent_tables': sorted(before['tables'].keys() - RUNTIME_TABLES),
            'runtime_tables_ignored': sorted(before['tables'].keys() & RUNTIME_TABLES)}


def compare_uninstall(before: dict, after: dict) -> dict:
    """Require byte-identical DB/secret/sidecars and identical tables after uninstall."""
    _compare_tables(before, after, allow_runtime=False)
    for name in sorted(before['files'].keys() | after['files'].keys()):
        if before['files'].get(name) != after['files'].get(name):
            raise ValueError(f'Lifecycle file changed during uninstall: {name}')
    return {'status': 'passed', 'kind': 'uninstall', 'secret_preserved': True,
            'tables_preserved': sorted(before['tables']), 'files_preserved': sorted(before['files'])}
