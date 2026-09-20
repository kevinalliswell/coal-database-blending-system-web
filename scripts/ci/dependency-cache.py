"""Use optional, verified official download bundles on a slow build network."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile


def checked_archive(path: Path, expected: str) -> bool:
    if not path.exists():
        return False
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError(f'Cached archive checksum mismatch: {path.name}')
    return True


def prepare_wheels(archive: Path, output: Path, repo: Path, expected: str) -> bool:
    if not checked_archive(archive, expected):
        return False
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        for name, digest in manifest['requirements'].items():
            content = (repo / name).read_bytes().replace(b'\r\n', b'\n')
            if hashlib.sha256(content).hexdigest() != digest:
                print(f'Wheel bundle does not match {name}; use normal dependency resolution')
                return False
        # The archive digest pins the entire trusted PyPI manifest and file set.
        bundle.extractall(output)
        for wheel in manifest['wheels']:
            if not checked_archive(output / 'wheels' / wheel['filename'], wheel['sha256']):
                raise ValueError(f"Missing cached wheel: {wheel['filename']}")
    return True


def main() -> None:
    cache = Path(os.environ['CBOS_ARCHIVE_CACHE'])
    root = Path(os.environ['CI_TASK_ROOT'])
    wheelhouse = root / 'wheelhouse'
    updates = {}
    wheel_digest = 'e2e5bb266aeafe3d12f2221af1433216ab5773b8c02c5c131048cd83c37b09b5'
    if prepare_wheels(cache / 'cbos-win-cp311-wheelhouse-e2e5bb26.zip', wheelhouse, Path.cwd(), wheel_digest):
        updates.update(PIP_NO_INDEX='1', PIP_FIND_LINKS=str(wheelhouse / 'wheels'))
        print(f'Official Windows cp311 wheel bundle verified: {wheel_digest}')
    electron_name = 'electron-v44.4.0-win32-x64.zip'
    electron = cache / electron_name
    electron_version = json.loads(Path('desktop/package.json').read_text())['devDependencies']['electron']
    if electron_version == '44.4.0' and checked_archive(electron, '596d5f7a77fc4f494f24ff9b362577954e16df819a81915bdb3b91d25f8eddd2'):
        # @electron/get keys its cache by the official URL's parent directory.
        url = 'https://github.com/electron/electron/releases/download/v44.4.0'
        target = root / 'cache/electron' / hashlib.sha256(url.encode()).hexdigest()
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(electron, target / electron_name)
        updates['CBOS_ELECTRON_ZIP'] = str(target / electron_name)
        print('Official Electron Windows x64 archive verified; normal npm install still validates its checksum')
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as env:
        for name, value in updates.items():
            env.write(f'{name}={value}\n')


if __name__ == '__main__':
    main()
