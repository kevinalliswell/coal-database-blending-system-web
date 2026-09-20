"""Real NSIS/ZIP acceptance, only on a disposable GitHub-hosted Windows worker.

The installation uses the product's actual default user data directory. No
database is copied into the application: both fixtures are created by Electron.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]
spec = importlib.util.spec_from_file_location('lifecycle_data', SCRIPTS / 'lifecycle-data.py')
data_checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(data_checks)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def require_disposable():
    if sys.platform != 'win32' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('Installation lifecycle requires disposable GitHub-hosted Windows')
    for key in ('LOCALAPPDATA', 'RUNNER_TEMP'):
        if not os.environ.get(key) or not Path(os.environ[key]).is_absolute():
            raise ValueError(f'Missing absolute {key}')
    data_dir = Path(os.environ['LOCALAPPDATA']) / 'CBOS'
    if data_dir.exists():
        raise ValueError('Existing CBOS user data must never be reused or deleted by acceptance')
    return data_dir


def checked_baseline(directory):
    expected = read_json(SCRIPTS / 'upgrade-baseline.json')
    proof = read_json(directory / 'baseline.json')
    if proof != {**expected, 'verified': True}:
        raise ValueError('Baseline proof differs from the fixed official release')
    installer = directory / expected['asset']['name']
    with installer.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != expected['asset']['sha256'] or installer.stat().st_size != expected['asset']['size']:
        raise ValueError('Baseline installer bytes differ from the pinned release')
    return expected, installer


def installer_process(executable, install_dir, *, uninstall=False):
    # Start-Process -Wait waits for the NSIS process tree, including the copied
    # uninstaller. /D is last and unquoted, as NSIS requires for paths with spaces.
    environment = {**os.environ, 'CBOS_TEST_INSTALLER': str(executable),
                   'CBOS_TEST_INSTALL_ARGS': '/S' if uninstall else f'/S /D={install_dir}'}
    script = "$ErrorActionPreference='Stop'; $p=Start-Process -FilePath $env:CBOS_TEST_INSTALLER -ArgumentList $env:CBOS_TEST_INSTALL_ARGS -Wait -PassThru; exit $p.ExitCode"
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                   env=environment, check=True, timeout=300)
    installed = install_dir / 'CBOS.exe'
    if uninstall:
        deadline = time.monotonic() + 30
        while installed.exists() and time.monotonic() < deadline:
            time.sleep(.5)
    if installed.exists() != (not uninstall):
        raise ValueError('Installer/uninstaller did not produce the expected application state')


def electron_stage(stage, executable, identity, output, fixture):
    folder = output / stage
    folder.mkdir()
    subprocess.run(['node', str(SCRIPTS / 'lifecycle-electron.cjs'), '--stage', stage,
                    '--executable', str(executable), '--version', identity['version'],
                    '--sha', identity['commit'], '--output', str(folder), '--fixture', str(fixture)],
                   cwd=ROOT, check=True, timeout=360)
    report = read_json(folder / 'lifecycle-electron.json')
    if (report.get('passed'), report.get('version'), report.get('build_commit')) != (
            True, identity['version'], identity['commit']):
        raise ValueError(f'{stage} Electron identity/status mismatch')
    return report


def extract_zip(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('ZIP contains a path outside its extraction directory')
        bundle.extractall(destination)
    executable = destination / 'CBOS.exe'
    if not executable.is_file():
        raise ValueError('Portable ZIP does not contain CBOS.exe')
    return executable


def run(args):
    data_dir = require_disposable()
    baseline, old_installer = checked_baseline(args.baseline)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ('installation.json', 'lifecycle.json', 'electron')):
        raise ValueError('Lifecycle evidence directory must be fresh')
    identity = {'version': args.version, 'commit': args.sha}
    work = Path(tempfile.mkdtemp(prefix='CBOS 生命周期 ', dir=os.environ['RUNNER_TEMP']))
    install_dir = work / '安装目录 with spaces'
    fixture = work / 'fixture-private.json'
    installed = install_dir / 'CBOS.exe'
    checks = {}
    try:
        # Preserve the original full GUI acceptance, now using the real default
        # database that the subsequent NSIS uninstaller must leave intact.
        installer_process(args.installer, install_dir)
        subprocess.run(['node', str(SCRIPTS / 'smoke-electron.cjs')], cwd=ROOT, check=True, timeout=600,
                       env={**os.environ, 'CBOS_ELECTRON_EXECUTABLE': str(installed),
                            'CBOS_SMOKE_OUTPUT': str(output / 'electron'), 'CBOS_SMOKE_USE_DEFAULT_DATA': '1'})
        fresh = read_json(output / 'electron/electron-smoke.json')
        if (fresh.get('passed'), fresh.get('version'), fresh.get('build_commit'), fresh.get('uses_default_data_directory')) != (
                True, args.version, args.sha, True):
            raise ValueError('Fresh installed GUI identity/default data mismatch')
        checks['fresh_install_gui'] = True
        before = data_checks.snapshot_data(data_dir)
        installer_process(install_dir / 'Uninstall CBOS.exe', install_dir, uninstall=True)
        after = data_checks.snapshot_data(data_dir)
        preservation = data_checks.compare_uninstall(before, after)
        write_json(output / 'fresh-uninstall-data.json', {'before': before, 'after': after, 'comparison': preservation})
        checks['fresh_uninstall_database'] = True
        write_json(output / 'installation.json', {'installed': True, 'uninstalled': True, 'data_preserved': True,
                   'version': args.version, 'build_commit': args.sha, 'default_data_directory': True})
        # This directory was absent on entry and was created only by this run.
        # Start a separate old-version fixture after proving fresh-uninstall preservation.
        shutil.rmtree(data_dir)
        installer_process(old_installer, install_dir)
        electron_stage('baseline', installed, baseline, output, fixture)
        checks['old_install_gui'] = True
        before_upgrade = data_checks.snapshot_data(data_dir)
        # Deliberately no uninstallation or data-directory replacement here.
        installer_process(args.installer, install_dir)
        checks['in_place_upgrade'] = True
        electron_stage('upgrade', installed, identity, output, fixture)
        checks['upgrade_login_restart'] = True
        after_upgrade = data_checks.snapshot_data(data_dir)
        preserved = data_checks.compare_upgrade(before_upgrade, after_upgrade)
        write_json(output / 'upgrade-data.json', {'before': before_upgrade, 'after': after_upgrade, 'comparison': preserved})
        checks['upgrade_data_preserved'] = True
        installer_process(install_dir / 'Uninstall CBOS.exe', install_dir, uninstall=True)
        after_uninstall = data_checks.snapshot_data(data_dir)
        preserved = data_checks.compare_uninstall(after_upgrade, after_uninstall)
        write_json(output / 'upgraded-uninstall-data.json', {'before': after_upgrade, 'after': after_uninstall, 'comparison': preserved})
        checks['upgraded_uninstall_database'] = True
        portable = extract_zip(args.zip, work / 'ZIP 免安装 with spaces')
        if installed.exists():
            raise ValueError('Installed application must be absent before the independent ZIP launch')
        electron_stage('zip', portable, identity, output, fixture)
        checks['zip_extracted_launch'] = checks['zip_login_restart'] = True
        after_zip = data_checks.snapshot_data(data_dir)
        preserved = data_checks.compare_upgrade(after_uninstall, after_zip)
        write_json(output / 'zip-data.json', {'before': after_uninstall, 'after': after_zip, 'comparison': preserved})
        checks['zip_data_preserved'] = True
        write_json(output / 'lifecycle.json', {'schema_version': 1, 'status': 'passed', 'version': args.version,
                   'build_commit': args.sha, 'baseline': baseline, 'checks': checks})
    except Exception:
        write_json(output / 'lifecycle-failure.json', {'status': 'failed', 'checks_completed': checks})
        raise
    finally:
        # No success is attested by this cleanup; failure reports remain failure.
        if installed.exists():
            installer_process(install_dir / 'Uninstall CBOS.exe', install_dir, uninstall=True)
    shutil.rmtree(data_dir)
    shutil.rmtree(work)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('installer', 'zip', 'baseline', 'output'):
        parser.add_argument('--' + name, type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--sha', required=True)
    run(parser.parse_args())
