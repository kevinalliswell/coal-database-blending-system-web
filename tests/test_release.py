"""Policy tests exercise immutable release and interrupted-publication boundaries."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('cbos_release', Path(__file__).parents[1] / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SHA = 'a' * 40


def test_draft_lookup_does_not_depend_on_published_by_tag_endpoint():
    class FakeGitHub(release.GitHub):
        def __init__(self): pass
        def api(self, path, **kwargs):
            if '/releases/tags/' in path: return None
            return [{'tag_name': 'v2.0.0', 'draft': True, 'id': 42}]
    assert FakeGitHub().release('v2.0.0')['id'] == 42


def test_notes_require_final_version_section_and_exclude_unreleased(tmp_path):
    path = tmp_path / 'CHANGELOG.md'
    path.write_text('# CHANGELOG\n\n## Unreleased\n\n- Not released\n')
    with pytest.raises(ValueError, match='CHANGELOG'):
        release.release_notes('2.0.0', SHA, 'o/r', changelog=path)
    path.write_text('# CHANGELOG\n\n## Unreleased\n\n- Future change\n\n## v2.0.0 (2026-09-20)\n\n- Batch assays\n\n## v1.0.0\n\n- Old item\n')
    notes = release.release_notes('2.0.0', SHA, 'o/r', changelog=path)
    assert 'Batch assays' in notes and 'Future change' not in notes and 'Old item' not in notes
    assert SHA in notes and '未签名' in notes and 'UPGRADE_2.0.md' in notes
    assert 'releases/download/v2.0.0/CBOS-2.0.0-windows-x64-setup.exe' in notes


@pytest.mark.parametrize('version,sha', [('2.0.0', 'main'), ('v2.0.0', SHA), ('2.0.0;echo bad', SHA), ('2.00.0', SHA)])
def test_release_requires_exact_identity(version, sha):
    with pytest.raises(ValueError):
        release.validate_identity(version, sha)


def test_existing_tag_is_never_moved_or_lightweight_replaced():
    class FakeGitHub:
        def __init__(self, kind, target): self.kind, self.target, self.writes = kind, target, []
        def api(self, path, data=None, **kwargs):
            assert data is None
            if '/git/ref/' in path: return {'object': {'type': self.kind, 'sha': 'tag-object'}}
            return {'object': {'type': 'commit', 'sha': self.target}}
    for kind, target in [('commit', SHA), ('tag', 'b' * 40)]:
        with pytest.raises(ValueError):
            release.require_tag(FakeGitHub(kind, target), 'v2.0.0', SHA, create=True)
    release.require_tag(FakeGitHub('tag', SHA), 'v2.0.0', SHA, create=True)


def test_linux_report_must_attest_exact_docker_sha(tmp_path):
    report = {'status': 'passed', 'version': '2.0.0', 'build_commit': 'b' * 40}
    (tmp_path / 'docker-validation.json').write_text(json.dumps(report))
    with pytest.raises(ValueError, match='Docker'):
        release.validation_report('linux', '2.0.0', SHA, tmp_path)


def test_windows_installer_exit_alone_does_not_count_as_validation(tmp_path):
    for folder in ('backend', 'electron'): (tmp_path / folder).mkdir()
    (tmp_path / 'backend/smoke-backend.json').write_text(json.dumps({'status': 'passed', 'version': '2.0.0', 'build_commit': SHA}))
    (tmp_path / 'electron/electron-smoke.json').write_text(json.dumps({'passed': True, 'version': '2.0.0', 'build_commit': SHA}))
    (tmp_path / 'installation.json').write_text('{"installed":true,"uninstalled":false,"data_preserved":true}')
    with pytest.raises(ValueError, match='uninstallation'):
        release.validation_report('windows', '2.0.0', SHA, tmp_path)


def test_fixed_image_different_bytes_are_never_pushed(monkeypatch):
    commands = []
    monkeypatch.setattr(release, 'run', lambda *args, **kw: commands.append(args) or 'sha256:new')
    monkeypatch.setattr(release, 'registry_manifest', lambda *args: ({'config': {'digest': 'sha256:old'}}, 'sha256:manifest'))
    with pytest.raises(ValueError, match='not be overwritten'):
        release.publish_fixed_image('ghcr.io/o/r', '2.0.0')
    assert not any('push' in command for command in commands)


def test_public_retry_never_uploads_replaces_or_retags(monkeypatch, tmp_path):
    operations = []
    class FakeGitHub:
        def __init__(self, _repo): pass
        def release(self, tag): return {'draft': False, 'id': 1}
        def api(self, *args, **kwargs): raise AssertionError('public release must be read-only')
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {'image': {'digest': 'sha256:old'}})
    monkeypatch.setattr(release, 'promote_latest', lambda *args: operations.append(args))
    monkeypatch.setattr(release, 'prepare_assets', lambda *args: pytest.fail('must not rebuild public assets'))
    release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)
    assert operations == [('ghcr.io/o/r', '2.0.0', 'sha256:old')]


def test_resume_after_fixed_image_push_reuses_original_draft_assets(monkeypatch, tmp_path):
    operations = []
    class FakeGitHub:
        def __init__(self, _repo): pass
        def release(self, tag): return {'draft': True, 'id': 1}
        def api(self, path, data=None, method=None, **kwargs):
            operations.append((path, data, method))
            return {'draft': False, 'id': 1}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'release_notes', lambda *args: 'Finalized version notes')
    monkeypatch.setattr(release, 'registry_manifest', lambda *args, **kwargs: ({'config': {'digest': 'sha256:old-config'}}, 'sha256:old'))
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs: 'sha256:old-config')
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {'image': {'name': 'ghcr.io/o/r', 'digest': 'sha256:old'}})
    monkeypatch.setattr(release, 'promote_latest', lambda *args: operations.append(('latest', *args)))
    monkeypatch.setattr(release, 'prepare_assets', lambda *args: pytest.fail('must reuse the draft matching the already-pushed fixed image'))
    release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)
    assert any(operation[2] == 'PATCH' for operation in operations if len(operation) == 3)
    assert operations[-1] == ('latest', 'ghcr.io/o/r', '2.0.0', 'sha256:old')


def _incomplete_upload_retry(monkeypatch, tmp_path, *, becomes_public=False, windows_order=False):
    operations = []
    # Keep the incomplete asset first under both POSIX and Windows ordering, so
    # the state transition exercises the second check immediately before DELETE.
    starter_name = '000-incomplete.zip'
    if windows_order:
        # Exercise Windows' case-insensitive Path ordering on every test host.
        monkeypatch.setattr(release, 'sorted', lambda paths: sorted(paths, key=lambda path: path.name.casefold()), raising=False)
    class FakeGitHub:
        def __init__(self, _repo): self.reads = 0
        def release(self, tag): return {'draft': True, 'id': 1, 'target_commitish': SHA}
        def api(self, path, data=None, method=None, **kwargs):
            if method == 'DELETE':
                operations.append(('delete', path))
                return None
            if method == 'PATCH': return None
            assert path == '/releases/1'
            self.reads += 1
            return {'draft': not (becomes_public and self.reads >= 2), 'id': 1,
                    'target_commitish': SHA, 'assets': [
                        {'id': 7, 'name': starter_name, 'state': 'starter', 'size': 0}]}
        def download(self, asset, destination):
            raise RuntimeError('starter asset has no downloadable object')
    def prepare(*args):
        (tmp_path / starter_name).write_bytes(b'completed upload')
        (tmp_path / 'cbos-web-2.0.0-docker-image.tar.gz').write_bytes(b'tested image')
        return {}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'release_notes', lambda *args: 'Finalized version notes')
    monkeypatch.setattr(release, 'registry_manifest', lambda *args, **kwargs: None)
    monkeypatch.setattr(release, 'prepare_assets', prepare)
    monkeypatch.setattr(release, 'require_tag', lambda *args, **kwargs: None)
    monkeypatch.setattr(release, 'publish_fixed_image', lambda *args: 'sha256:tested')
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {})
    monkeypatch.setattr(release, 'finish_release', lambda *args: operations.append(('finish',)))
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs: operations.append(args))
    return operations


@pytest.mark.parametrize('windows_order', [False, True])
def test_draft_retry_replaces_unavailable_starter_asset(monkeypatch, tmp_path, windows_order):
    operations = _incomplete_upload_retry(monkeypatch, tmp_path, windows_order=windows_order)
    release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)
    assert ('delete', '/releases/assets/7') in operations
    assert ('gh', 'release', 'upload', 'v2.0.0', str(tmp_path / '000-incomplete.zip'), '--repo', 'o/r') in operations
    assert operations[-1] == ('finish',)


@pytest.mark.parametrize('windows_order', [False, True])
def test_starter_asset_is_not_deleted_if_release_becomes_public(monkeypatch, tmp_path, windows_order):
    operations = _incomplete_upload_retry(monkeypatch, tmp_path, becomes_public=True, windows_order=windows_order)
    with pytest.raises(ValueError, match='public release asset'):
        release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)
    assert not any(operation[0] in ('delete', 'gh', 'finish') for operation in operations)
