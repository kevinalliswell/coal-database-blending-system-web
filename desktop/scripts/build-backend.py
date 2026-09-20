"""Build the native backend on its target OS and sync the desktop version."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "desktop"


def sync_version() -> str:
    """Use the existing application version without importing its dependencies."""
    module = ast.parse((ROOT / "app" / "__version__.py").read_text(encoding="utf-8"))
    version = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
    )
    if not isinstance(version, str):
        raise ValueError("app.__version__ must be a string")
    for filename in ("package.json", "package-lock.json"):
        path = DESKTOP / filename
        if not path.exists():
            if filename == "package-lock.json":
                continue
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["version"] = version
        if filename == "package-lock.json":
            payload["packages"][""]["version"] = version
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync-version-only", action="store_true")
    args = parser.parse_args()
    version = sync_version()
    print(f"CBOS desktop version: {version}", flush=True)
    if args.sync_version_only:
        return
    required = [
        DESKTOP / "backend_entry.py",
        ROOT / "frontend" / "dist" / "index.html",
        ROOT / "data" / "test_coal_datas.csv",
        ROOT / "migrations" / "alembic.ini",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Missing build input: {path}. Build the desktop frontend first.")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(DESKTOP / "backend-dist"),
         "--workpath", str(DESKTOP / "backend-build"), str(DESKTOP / "backend.spec")],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
