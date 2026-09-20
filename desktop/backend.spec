# -*- mode: python ; coding: utf-8 -*-
"""One-directory backend; resources are read from sys._MEIPASS at runtime."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
data_files = [
    (str(root / "build-info.json"), "."),
    (str(root / "frontend" / "dist"), "frontend/dist"),
    (str(root / "migrations"), "migrations"),
]
# Alembic loads migration templates and dialect implementations dynamically.
data_files += collect_data_files("alembic")

analysis = Analysis(
    [str(root / "desktop" / "backend_entry.py")],
    pathex=[str(root)],
    binaries=[],
    datas=data_files,
    hiddenimports=(
        collect_submodules("app")
        + collect_submodules("backend")
        + ["sqlalchemy.dialects.sqlite", "logging.config", "openpyxl", "xlrd", "waitress"]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["gunicorn", "tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [("u", None, "OPTION"), ("X utf8", None, "OPTION")],
    exclude_binaries=True,
    name="cbos-backend",
    debug=False,
    strip=False,
    upx=False,
    # Keep pipes available for the ready message and parent-lifetime protocol.
    # Electron spawns this process with windowsHide=true.
    console=True,
)
COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="cbos-backend",
)
