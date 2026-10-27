"""Policy tests exercise immutable release and interrupted-publication boundaries."""
import importlib.util
import io
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('cbos_release', Path(__file__).parents[1] / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SHA = 'a' * 40
OCI_INDEX = 'application/vnd.oci.image.index.v1+json'
DOCKER_LIST = 'application/vnd.docker.distribution.manifest.list.v2+json'
CONFIG_DIGEST = 'sha256:' + 'c' * 64
DISTRIBUTION_DIGEST = 'sha256:' + 'd' * 64


@pytest.mark.parametrize('media_type', [OCI_INDEX, DOCKER_LIST])
def test_registry_reads_index_without_mistaking_content_negotiation_for_absence(monkeypatch, media_type):
    from urllib.error import HTTPError
    document = {'schemaVersion': 2, 'mediaType': media_type, 'manifests': [
        {'digest': 'sha256:' + 'e' * 64, 'platform': {'os': 'linux', 'architecture': 'amd64'}},
        {'digest': 'sha256:' + 'f' * 64, 'platform': {'os': 'unknown', 'architecture': 'unknown'}},
    ]}
    monkeypatch.setenv('GITHUB_ACTOR', 'test-actor')
    monkeypatch.setenv('GH_TOKEN', 'test-token')

    def urlopen(request, **kwargs):
        if request.full_url.startswith('https://ghcr.io/token?'):
            return io.BytesIO(b'{"token":"registry-token"}')
        assert request.full_url == 'https://ghcr.io/v2/o/r/manifests/2.0.2'
        assert request.get_header('Authorization') == 'Bearer registry-token'
        accepted = {value.strip().split(';', 1)[0] for value in request.get_header('Accept', '').split(',')}
        # GHCR returns 404 when the tag exists but its index media type is excluded.
        if media_type not in accepted:
            raise HTTPError(request.full_url, 404, 'Unsupported manifest representation', {}, None)
        response = io.BytesIO(json.dumps(document).encode())
        response.headers = {'Docker-Content-Digest': DISTRIBUTION_DIGEST}
        return response

    monkeypatch.setattr(release, 'urlopen', urlopen)
    assert release.registry_manifest('ghcr.io/o/r', '2.0.2') == (document, DISTRIBUTION_DIGEST)


@pytest.mark.parametrize('document,local_id', [
    pytest.param({'mediaType': OCI_INDEX, 'manifests': []}, DISTRIBUTION_DIGEST, id='containerd-index'),
    pytest.param({'config': {'digest': CONFIG_DIGEST}}, DISTRIBUTION_DIGEST, id='manifest-distribution-id'),
    pytest.param({'config': {'digest': CONFIG_DIGEST}}, CONFIG_DIGEST, id='legacy-config-id'),
])
@pytest.mark.parametrize('already_pushed', [False, True])
def test_fixed_image_accepts_exact_distribution_or_legacy_config_identity(monkeypatch, document, local_id, already_pushed):
    commands = []

    def run(*args, **kwargs):
        commands.append(args)
        return local_id if args[:3] == ('docker', 'image', 'inspect') else ''

    def registry(*args):
        pushed = ('docker', 'push', 'ghcr.io/o/r:2.0.2') in commands
        return (document, DISTRIBUTION_DIGEST) if already_pushed or pushed else None

    monkeypatch.setattr(release, 'run', run)
    monkeypatch.setattr(release, 'registry_manifest', registry)
    assert release.publish_fixed_image('ghcr.io/o/r', '2.0.2') == DISTRIBUTION_DIGEST
    assert commands.count(('docker', 'push', 'ghcr.io/o/r:2.0.2')) == (0 if already_pushed else 1)


@pytest.mark.parametrize('remote', [None,
    ({'config': {'digest': CONFIG_DIGEST}}, DISTRIBUTION_DIGEST),
    ({'mediaType': OCI_INDEX, 'manifests': [{'digest': 'sha256:' + 'b' * 64}]}, DISTRIBUTION_DIGEST),
])
def test_push_cannot_succeed_with_missing_or_different_registry_identity(monkeypatch, remote):
    commands = []

    def run(*args, **kwargs):
        commands.append(args)
        return 'sha256:' + 'b' * 64

    monkeypatch.setattr(release, 'run', run)
    monkeypatch.setattr(release, 'registry_manifest', lambda *args: remote if ('docker', 'push', 'ghcr.io/o/r:2.0.2') in commands else None)
    with pytest.raises(ValueError, match='differs from the tested Docker image'):
        release.publish_fixed_image('ghcr.io/o/r', '2.0.2')
    assert commands.count(('docker', 'push', 'ghcr.io/o/r:2.0.2')) == 1


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
    assert '发布不等于公开' in notes and '访问权限' in notes
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


@pytest.mark.parametrize('document', [
    {'config': {'digest': 'sha256:old'}},
    {'mediaType': OCI_INDEX, 'manifests': [{'digest': 'sha256:new'}]},
])
def test_fixed_image_different_bytes_are_never_pushed(monkeypatch, document):
    commands = []
    monkeypatch.setattr(release, 'run', lambda *args, **kw: commands.append(args) or 'sha256:new')
    monkeypatch.setattr(release, 'registry_manifest', lambda *args: (document, 'sha256:manifest'))
    with pytest.raises(ValueError, match='not be overwritten'):
        release.publish_fixed_image('ghcr.io/o/r', '2.0.0')
    assert not any('push' in command for command in commands)


def test_public_retry_never_uploads_replaces_or_retags(monkeypatch, tmp_path):
    operations = []
    commands = []
    class FakeGitHub:
        def __init__(self, _repo): pass
        def release(self, tag): return {'draft': False, 'id': 1}
        def api(self, path, **kwargs):
            assert not kwargs.get('method') and path in ('', '/users/o/packages/container/r')
            return VisibilityGitHub().api(path)
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r', 'delivery_visibility': 'private'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {'delivery_visibility': 'private', 'image': {'name': 'ghcr.io/o/r', 'digest': 'sha256:old'}})
    monkeypatch.setattr(release, 'registry_manifest', lambda *args, **kwargs: ({}, 'sha256:old'))
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs: commands.append(args) or 'sha256:old')
    monkeypatch.setattr(release, 'promote_latest', lambda *args: operations.append(args))
    monkeypatch.setattr(release, 'prepare_assets', lambda *args: pytest.fail('must not rebuild public assets'))
    release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)
    assert operations == [('ghcr.io/o/r', '2.0.0', 'sha256:old')]
    # A fresh daemon must restore all index children (including attestations)
    # from the original verified archive before it can promote the same index.
    assert commands[0][:3] == ('docker', 'load', '--input')
    assert commands[0][3].endswith('cbos-web-2.0.0-docker-image.tar.gz')


def test_published_retry_rejects_archive_that_does_not_match_fixed_image(monkeypatch, tmp_path):
    class FakeGitHub:
        def __init__(self, _repo): pass
        def release(self, _tag): return {'draft': False, 'id': 1}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {
        'delivery_visibility': 'public', 'image': {'name': 'ghcr.io/o/r', 'digest': DISTRIBUTION_DIGEST}})
    monkeypatch.setattr(release, 'verify_image_access', lambda *args: None)
    monkeypatch.setattr(release, 'registry_manifest', lambda *args: ({'mediaType': OCI_INDEX}, DISTRIBUTION_DIGEST))
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs: 'sha256:wrong-archive')
    monkeypatch.setattr(release, 'promote_latest', lambda *args: pytest.fail('wrong archive must never promote latest'))
    with pytest.raises(ValueError, match='archive does not match'):
        release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path, 'public')


@pytest.mark.parametrize('document,local_id', [
    ({'config': {'digest': 'sha256:old-config'}}, 'sha256:old-config'),
    ({'mediaType': OCI_INDEX, 'manifests': []}, 'sha256:old'),
])
def test_resume_after_fixed_image_push_reuses_original_draft_assets(monkeypatch, tmp_path, document, local_id):
    operations = []
    class FakeGitHub:
        def __init__(self, _repo): pass
        def release(self, tag): return {'draft': True, 'id': 1}
        def api(self, path, data=None, method=None, **kwargs):
            if path in ('', '/users/o/packages/container/r'):
                assert data is None and method is None
                return VisibilityGitHub().api(path)
            operations.append((path, data, method))
            return {'draft': False, 'id': 1}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r', 'delivery_visibility': 'private'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'release_notes', lambda *args: 'Finalized version notes')
    monkeypatch.setattr(release, 'registry_manifest', lambda *args, **kwargs: (document, 'sha256:old'))
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs: local_id)
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {'delivery_visibility': 'private', 'image': {'name': 'ghcr.io/o/r', 'digest': 'sha256:old'}})
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
            if path in ('', '/users/o/packages/container/r'):
                assert data is None and method is None
                return VisibilityGitHub().api(path)
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
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r', 'delivery_visibility': 'private'})
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


class VisibilityGitHub:
    def __init__(self, visibility='private', package='private', owner_type='User'):
        self.visibility, self.package, self.owner_type = visibility, package, owner_type
        self.calls = []
    def api(self, path, **kwargs):
        self.calls.append((path, kwargs))
        if path == '':
            return {'private': self.visibility == 'private', 'visibility': self.visibility,
                    'owner': {'login': 'o', 'type': self.owner_type}}
        if isinstance(self.package, Exception):
            raise self.package
        return None if self.package is None else {'visibility': self.package}


@pytest.mark.parametrize('owner_type,prefix', [('User', '/users/o/'), ('Organization', '/orgs/o/')])
def test_private_delivery_checks_exact_package_visibility(owner_type, prefix):
    github = VisibilityGitHub(owner_type=owner_type)
    release.verify_delivery_visibility(github, 'ghcr.io/o/r', 'private')
    assert github.calls[-1][0] == prefix + 'packages/container/r'
    assert github.calls[-1][1]['global_api'] is True


@pytest.mark.parametrize('repository,package', [('public', 'private'), ('private', 'public'), ('private', 'internal')])
def test_visibility_mismatch_fails_closed(repository, package):
    with pytest.raises(ValueError, match='visibility'):
        release.verify_delivery_visibility(VisibilityGitHub(repository, package), 'ghcr.io/o/r', 'private')


def test_package_metadata_permission_error_is_not_absence():
    with pytest.raises(RuntimeError, match='403'):
        release.verify_delivery_visibility(VisibilityGitHub(package=RuntimeError('HTTP 403')), 'ghcr.io/o/r', 'private', allow_missing_package=True)


def test_only_private_delivery_can_create_a_missing_package():
    release.verify_delivery_visibility(VisibilityGitHub(package=None), 'ghcr.io/o/r', 'private', allow_missing_package=True)
    with pytest.raises(ValueError, match='package'):
        release.verify_delivery_visibility(VisibilityGitHub('public', None), 'ghcr.io/o/r', 'public', allow_missing_package=True)
    with pytest.raises(ValueError, match='package'):
        release.verify_delivery_visibility(VisibilityGitHub(package=None), 'ghcr.io/o/r', 'private')


@pytest.mark.parametrize('visibility,anonymous', [('private', False), ('public', True)])
def test_image_access_uses_expected_visibility(monkeypatch, visibility, anonymous):
    calls = []
    def manifest(*args, **kwargs):
        calls.append(kwargs['anonymous'])
        return {}, 'sha256:tested'
    monkeypatch.setattr(release, 'registry_manifest', manifest)
    release.verify_image_access(VisibilityGitHub(visibility, visibility), 'ghcr.io/o/r', '2.0.0', 'sha256:tested', visibility)
    assert calls == [anonymous]


def test_public_delivery_requires_anonymous_image_access(monkeypatch):
    def unavailable(*args, **kwargs):
        assert kwargs['anonymous'] is True
        raise RuntimeError('HTTP 401')
    monkeypatch.setattr(release, 'registry_manifest', unavailable)
    with pytest.raises(RuntimeError, match='401'):
        release.verify_image_access(VisibilityGitHub('public', 'public'), 'ghcr.io/o/r', '2.0.0', 'sha256:tested', 'public')


def test_published_retry_rejects_changed_manifest_visibility(monkeypatch, tmp_path):
    class FakeGitHub:
        def __init__(self, _repo): pass
        def release(self, _tag): return {'draft': False, 'id': 1}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r', 'delivery_visibility': 'private'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'verify_delivery_visibility', lambda *args, **kwargs: None)
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {'delivery_visibility': 'public', 'image': {'name': 'ghcr.io/o/r', 'digest': 'sha256:tested'}})
    monkeypatch.setattr(release, 'promote_latest', lambda *args: pytest.fail('must not promote changed delivery visibility'))
    with pytest.raises(ValueError, match='visibility'):
        release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)


def test_private_publish_refuses_public_package_before_any_write(monkeypatch, tmp_path):
    class FakeGitHub(VisibilityGitHub):
        def __init__(self, _repo): super().__init__('private', 'public')
        def release(self, _tag): return {'draft': True, 'id': 1}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r', 'delivery_visibility': 'private'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'run', lambda *args, **kwargs: pytest.fail('no Docker/asset write before visibility check'))
    monkeypatch.setattr(release, 'prepare_assets', lambda *args: pytest.fail('no asset preparation on mismatched visibility'))
    with pytest.raises(ValueError, match='Package visibility'):
        release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)


def test_published_retry_rechecks_current_repository_visibility(monkeypatch, tmp_path):
    class FakeGitHub(VisibilityGitHub):
        def __init__(self, _repo): super().__init__('public', 'public')
        def release(self, _tag): return {'draft': False, 'id': 1}
    monkeypatch.setattr(release, 'preflight', lambda *args: {'image': 'ghcr.io/o/r', 'delivery_visibility': 'private'})
    monkeypatch.setattr(release, 'GitHub', FakeGitHub)
    monkeypatch.setattr(release, 'verify_downloads', lambda *args: {'delivery_visibility': 'private', 'image': {'name': 'ghcr.io/o/r', 'digest': 'sha256:tested'}})
    monkeypatch.setattr(release, 'promote_latest', lambda *args: pytest.fail('must not promote changed repository visibility'))
    with pytest.raises(ValueError, match='Repository visibility'):
        release.publish('2.0.0', SHA, 'o/r', tmp_path, tmp_path)


@pytest.mark.parametrize('status', [403, 404])
def test_package_api_only_treats_http_404_as_missing(monkeypatch, status):
    from urllib.error import HTTPError
    monkeypatch.setenv('GH_TOKEN', 'test-token')
    def unavailable(request, **kwargs):
        assert request.full_url == 'https://api.github.com/users/o/packages/container/r'
        raise HTTPError(request.full_url, status, 'Unavailable', None, None)
    monkeypatch.setattr(release, 'urlopen', unavailable)
    github = release.GitHub('o/r')
    if status == 404:
        assert github.api('/users/o/packages/container/r', global_api=True, missing=True) is None
    else:
        with pytest.raises(RuntimeError, match='HTTP 403'):
            github.api('/users/o/packages/container/r', global_api=True, missing=True)
