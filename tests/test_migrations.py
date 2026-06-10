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
