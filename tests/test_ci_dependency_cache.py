import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location('dependency_cache',
    Path(__file__).parents[1] / 'scripts/ci/dependency-cache.py')
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


def test_absent_optional_archive_uses_normal_install(tmp_path):
    assert not cache.prepare_wheels(tmp_path / 'absent.zip', tmp_path / 'out', tmp_path, 'a' * 64)


def test_corrupted_archive_is_rejected(tmp_path):
    archive = tmp_path / 'bad.zip'
    archive.write_bytes(b'untrusted replacement')
    with pytest.raises(ValueError, match='checksum mismatch'):
        cache.prepare_wheels(archive, tmp_path / 'out', tmp_path, 'a' * 64)


def test_requirements_match_across_windows_newlines_but_not_version_changes(tmp_path):
    requirements = b'example==1\n'
    wheel = b'test wheel bytes'
    manifest = {'requirements': {'requirements.txt': hashlib.sha256(requirements).hexdigest()},
                'wheels': [{'filename': 'example.whl', 'sha256': hashlib.sha256(wheel).hexdigest()}]}
    archive = tmp_path / 'bundle.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('manifest.json', json.dumps(manifest))
        bundle.writestr('wheels/example.whl', wheel)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    source = tmp_path / 'requirements.txt'
    source.write_bytes(requirements.replace(b'\n', b'\r\n'))
    assert cache.prepare_wheels(archive, tmp_path / 'out', tmp_path, digest)
    assert (tmp_path / 'out/wheels/example.whl').read_bytes() == wheel
    source.write_bytes(b'example==2\n')
    assert not cache.prepare_wheels(archive, tmp_path / 'changed', tmp_path, digest)
    assert not (tmp_path / 'changed').exists()
