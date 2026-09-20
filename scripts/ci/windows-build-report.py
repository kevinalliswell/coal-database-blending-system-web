"""Record build-only evidence. This is never a Windows installation attestation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET


def verify_backend(report: dict | None, *, commit: str, version: str) -> None:
    if not report or report.get('status') != 'passed':
        raise ValueError('Frozen backend report is missing or failed')
    if report.get('build_commit') != commit or report.get('version') != version:
        raise ValueError('Frozen backend report does not match the tested commit/version')


def main() -> None:
    task_root = Path(os.environ['CI_TASK_ROOT'])
    identity = json.loads((task_root / 'runner.json').read_text(encoding='utf-8-sig'))
    identity.update(commit=os.environ['EXPECTED_SHA'], version=os.environ.get('EXPECTED_VERSION'),
                    python=platform.python_version(),
                    node=subprocess.check_output(['node.exe', '--version'], text=True).strip(),
                    git=subprocess.check_output(['git.exe', '--version'], text=True).strip())
    checks = json.loads(os.environ['CHECK_RESULTS'])
    backend_path = Path('outputs/ci/backend/smoke-backend.json')
    backend = json.loads(backend_path.read_text(encoding='utf-8')) if backend_path.exists() else None
    junit = Path('outputs/ci/pytest.xml')
    suites = list(ET.parse(junit).getroot().iter('testsuite')) if junit.exists() else None
    counts = {key: sum(int(s.get(key, '0')) for s in suites)
              for key in ('tests', 'failures', 'errors', 'skipped')} if suites is not None else None
    packages = sorted(p for p in Path('desktop/dist').glob('*') if p.suffix in ('.exe', '.zip'))
    hashes = []
    for package in packages:
        with package.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        hashes.append({'name': package.name, 'sha256': digest, 'bytes': package.stat().st_size})
    errors = []
    if checks.get('backend_smoke') == 'success':
        try:
            verify_backend(backend, commit=identity['commit'], version=identity['version'])
        except ValueError as error:
            errors.append(str(error))
    if checks.get('package') == 'success':
        expected = {f"CBOS-{identity['version']}-windows-x64-setup.exe",
                    f"CBOS-{identity['version']}-windows-x64.zip"}
        if {p.name for p in packages} != expected or any(p.stat().st_size == 0 for p in packages):
            errors.append('Expected exactly the prepared-version NSIS and ZIP outputs')
    evidence = {'scope': 'noninteractive-build', 'full_windows_acceptance': False,
                'identity': identity, 'checks': checks, 'python_tests': counts,
                'backend_report': backend, 'packages': hashes, 'identity_errors': errors}
    print('CI_WINDOWS_BUILD_JSON=' + json.dumps(evidence, ensure_ascii=False))
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
        summary.write('## Windows noninteractive build evidence\n\n')
        summary.write('Installer execution, upgrade, uninstall, and GUI acceptance require a separate disposable environment.\n\n')
        summary.write('```json\n' + json.dumps(evidence, ensure_ascii=False, indent=2) + '\n```\n')
    if errors:
        raise ValueError('; '.join(errors))


if __name__ == '__main__':
    main()
