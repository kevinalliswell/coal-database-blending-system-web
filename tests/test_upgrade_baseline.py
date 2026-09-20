"""The old installer is trusted only after pinned metadata and byte verification."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location(
    'upgrade_baseline', ROOT / 'desktop/scripts/download-upgrade-baseline.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
PAYLOAD = b'MZ\x00\xff\x80\r\nfixture installer bytes, never executed'


@pytest.fixture
def manifest():
    value = json.loads((ROOT / 'desktop/scripts/upgrade-baseline.json').read_text())
    value['asset']['size'] = len(PAYLOAD)
    value['asset']['sha256'] = hashlib.sha256(PAYLOAD).hexdigest()
    return value


class FakeGitHub:
    def __init__(self, manifest):
        self.asset = {**manifest['asset'], 'state': 'uploaded',
                      'digest': 'sha256:' + manifest['asset']['sha256']}
        self.release = {'id': manifest['release_id'], 'tag_name': manifest['tag'],
                        'draft': False, 'prerelease': False, 'assets': [deepcopy(self.asset)]}
        self.ref = {'object': {'type': 'tag', 'sha': 'a' * 40}}
        self.tag = {'tag': manifest['tag'],
                    'object': {'type': 'commit', 'sha': manifest['commit']}}
        self.payload = PAYLOAD
        self.downloads = 0
        self.failure = None

    def api(self, path):
        assert 'latest' not in path
        if '/releases/tags/' in path:
            return self.release
        if '/git/ref/tags/' in path:
            return self.ref
        if '/git/tags/' in path:
            return self.tag
        if '/releases/assets/' in path:
            return self.asset
        raise AssertionError(path)

    def download(self, path, destination):
        assert '/releases/assets/' in path
        self.downloads += 1
        destination.write_bytes(self.payload)
        if self.failure:
            raise self.failure


def test_committed_baseline_matches_the_verified_formal_release():
    value = baseline.load_manifest()
    assert value['version'] == '2.0.0'
    assert value['commit'] == '1a19ff0638bb67dd4ac210efa3926ee6b9878225'
    assert value['release_id'] == 392321864
    assert value['asset'] == {
        'id': 576184875, 'name': 'CBOS-2.0.0-windows-x64-setup.exe', 'size': 171707049,
        'sha256': '91b788d8ffdb67a33a57ae8833a347aec04010cf4900a2f1f86c748bbef9f086'}


@pytest.mark.parametrize('annotated', [False, True])
def test_download_verifies_pinned_bytes_and_writes_proof(tmp_path, manifest, annotated):
    gh = FakeGitHub(manifest)
    if not annotated:
        gh.ref = deepcopy(gh.tag)
    proof = baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert proof == {**manifest, 'verified': True}
    assert json.loads((tmp_path / 'baseline.json').read_text()) == proof
    assert (tmp_path / manifest['asset']['name']).read_bytes() == PAYLOAD
    assert {path.name for path in tmp_path.iterdir()} == {'baseline.json', manifest['asset']['name']}


@pytest.mark.parametrize('change', [
    lambda gh: gh.release.update(draft=True),
    lambda gh: gh.release.update(prerelease=True),
    lambda gh: gh.release.update(id=42),
    lambda gh: gh.release.update(tag_name='v9.0.0'),
    lambda gh: gh.tag['object'].update(sha='b' * 40),
    lambda gh: gh.tag['object'].update(type='tree'),
    lambda gh: gh.asset.update(id=42),
    lambda gh: gh.asset.update(name='replaced.exe'),
    lambda gh: gh.asset.update(state='starter'),
    lambda gh: gh.asset.update(size=1),
    lambda gh: gh.asset.update(digest='sha256:' + '0' * 64),
    lambda gh: gh.asset.pop('digest'),
    lambda gh: gh.release.update(assets=[]),
    lambda gh: gh.release['assets'].append(deepcopy(gh.asset)),
])
def test_metadata_mismatch_blocks_download(tmp_path, manifest, change):
    gh = FakeGitHub(manifest)
    change(gh)
    with pytest.raises(ValueError):
        baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert gh.downloads == 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('payload', [b'', PAYLOAD + b'extra', b'X' * len(PAYLOAD)])
def test_wrong_download_size_or_sha_leaves_no_installer_or_proof(tmp_path, manifest, payload):
    gh = FakeGitHub(manifest)
    gh.payload = payload
    with pytest.raises(ValueError):
        baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert gh.downloads == 1
    assert not list(tmp_path.iterdir())


def test_partial_download_failure_removes_bytes_and_does_not_fallback(tmp_path, manifest):
    gh = FakeGitHub(manifest)
    gh.failure = subprocess.CalledProcessError(1, ['gh', 'api'])
    with pytest.raises(subprocess.CalledProcessError):
        baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert gh.downloads == 1
    assert not list(tmp_path.iterdir())


def test_proof_write_failure_leaves_no_partial_success_evidence(tmp_path, manifest, monkeypatch):
    def fail_write(value, stream, **kwargs):
        stream.write('{"verified": true')
        raise OSError('simulated full disk')
    monkeypatch.setattr(baseline.json, 'dump', fail_write)
    with pytest.raises(OSError, match='simulated full disk'):
        baseline.download_baseline(manifest, tmp_path, gh=FakeGitHub(manifest))
    assert not list(tmp_path.iterdir())


def test_github_permission_failure_never_downloads_or_falls_back(tmp_path, manifest):
    gh = FakeGitHub(manifest)
    def denied(path):
        raise subprocess.CalledProcessError(1, ['gh', 'api'], stderr=b'HTTP 403')
    gh.api = denied
    with pytest.raises(subprocess.CalledProcessError):
        baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert gh.downloads == 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('field,value', [
    ('name', '../outside.exe'), ('sha256', 'latest'), ('id', True), ('size', 0),
])
def test_invalid_asset_pin_is_rejected_before_api_or_download(tmp_path, manifest, field, value):
    manifest['asset'][field] = value
    gh = FakeGitHub(manifest)
    with pytest.raises(ValueError):
        baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert gh.downloads == 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('existing', ['baseline.json', 'CBOS-2.0.0-windows-x64-setup.exe'])
def test_existing_evidence_is_not_overwritten(tmp_path, manifest, existing):
    path = tmp_path / existing
    path.write_bytes(b'prior run')
    gh = FakeGitHub(manifest)
    with pytest.raises(FileExistsError):
        baseline.download_baseline(manifest, tmp_path, gh=gh)
    assert path.read_bytes() == b'prior run'
    assert gh.downloads == 0


def test_gh_download_uses_binary_stdout_and_fixed_github_host(monkeypatch, tmp_path):
    def fake_run(command, **kwargs):
        assert command[:4] == ['gh', 'api', '--hostname', 'github.com']
        assert 'Accept: application/octet-stream' in command
        assert command[-1].endswith('/releases/assets/576184875')
        assert not kwargs.get('text') and not kwargs.get('encoding')
        kwargs['stdout'].write(PAYLOAD)
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(baseline.subprocess, 'run', fake_run)
    destination = tmp_path / 'old.exe'
    baseline.GitHub().download('repos/owner/repository/releases/assets/576184875', destination)
    assert destination.read_bytes() == PAYLOAD
