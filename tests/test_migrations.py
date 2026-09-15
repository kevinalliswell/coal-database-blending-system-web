import os
import sqlite3
import subprocess
import sys


def test_migrations_upgrade_empty_sqlite_database(tmp_path):
    database_path = tmp_path / "empty.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path}"
    env["FLASK_CONFIG"] = "development"

    result = subprocess.run(
        [sys.executable, "-m", "flask", "--app", "run.py", "db", "upgrade"],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }

    assert {"coal_data", "optimization_history", "upload_files", "alembic_version"} <= tables


def test_basis_migration_preserves_legacy_assays_without_guessing_basis(tmp_path):
    database_path = tmp_path / 'legacy.db'
    env = os.environ.copy()
    env['DATABASE_URL'] = f'sqlite:///{database_path}'
    command = [sys.executable, '-m', 'flask', '--app', 'run.py', 'db', 'upgrade']
    before = subprocess.run(command + ['b3f7b0d5f1a2'], env=env, capture_output=True, text=True)
    assert before.returncode == 0, before.stderr
    with sqlite3.connect(database_path) as connection:
        connection.execute('''insert into coal_data
            (id, name, type, price, calorific_value, ash_content, volatile_matter,
             fixed_carbon, total_sulfur, total_moisture, air_dry_moisture)
            values (1, '旧煤', '无烟煤', 998.46, 7419, 11.5877775, 9.6089175,
                    76.3035, 0.9, 9.82, 0.962588071846652)''')
        original = connection.execute('select * from coal_data').fetchone()
    after = subprocess.run(command, env=env, capture_output=True, text=True)
    assert after.returncode == 0, after.stderr
    with sqlite3.connect(database_path) as connection:
        preserved = connection.execute('select * from coal_data').fetchone()
        bases = connection.execute('select analysis_basis, calorific_basis, calorific_type, price_basis from coal_data').fetchone()
    assert preserved[:len(original)] == original
    assert bases == ('unknown', 'unknown', 'unknown', 'unknown')
