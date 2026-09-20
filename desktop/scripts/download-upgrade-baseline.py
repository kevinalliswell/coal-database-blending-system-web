"""Download the pinned formal Windows upgrade baseline; never execute it.

Only this download step needs GH_TOKEN with contents:read for the private
repository. Installer and application steps must not inherit that credential.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


class GitHub:
    def api(self, path):
        result = subprocess.run(
            ['gh', 'api', '--hostname', 'github.com', path], check=True,
            capture_output=True, text=True, encoding='utf-8', timeout=60)
        return json.loads(result.stdout)

    def download(self, path, destination):
        # Write bytes directly: PowerShell 5.1 text redirection corrupts EXEs.
        with destination.open('xb') as stream:
            subprocess.run(
                ['gh', 'api', '--hostname', 'github.com', '--header',
                 'Accept: application/octet-stream', path], check=True,
                stdout=stream, stderr=subprocess.PIPE, timeout=900)


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ValueError('Unsupported upgrade baseline schema')
    version = manifest.get('version', '')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Baseline must specify a fixed version')
    if manifest.get('tag') != 'v' + version:
        raise ValueError('Baseline tag must match its fixed version')
    for key, pattern in [('commit', r'[0-9a-f]{40}'),
                         ('repository', r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')]:
        if not isinstance(manifest.get(key), str) or not re.fullmatch(pattern, manifest[key]):
            raise ValueError(f'Invalid baseline {key}')
    asset = manifest.get('asset')
    if not isinstance(asset, dict):
        raise ValueError('Missing pinned baseline asset')
    for value in (manifest.get('release_id'), asset.get('id'), asset.get('size')):
        if type(value) is not int or value <= 0:
            raise ValueError('Baseline IDs and asset size must be positive integers')
    if asset.get('name') != f'CBOS-{version}-windows-x64-setup.exe':
        raise ValueError('Unexpected baseline installer filename')
    if not isinstance(asset.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', asset['sha256']):
        raise ValueError('Invalid baseline asset SHA256')


def load_manifest():
    manifest = json.loads(Path(__file__).with_name('upgrade-baseline.json').read_text(encoding='utf-8'))
    validate_manifest(manifest)
    return manifest


def verify_metadata(manifest, gh):
    """Check both the release listing and asset endpoint before accepting bytes."""
    prefix = f'repos/{manifest["repository"]}'
    release = gh.api(f'{prefix}/releases/tags/{manifest["tag"]}')
    if (not isinstance(release, dict) or release.get('id') != manifest['release_id']
            or release.get('tag_name') != manifest['tag']
            or release.get('draft') is not False or release.get('prerelease') is not False):
        raise ValueError('Formal baseline release identity/status does not match the pin')

    ref = gh.api(f'{prefix}/git/ref/tags/{manifest["tag"]}')
    target = ref.get('object', {})
    if target.get('type') == 'tag':
        tag_sha = target.get('sha', '')
        if not isinstance(tag_sha, str) or not re.fullmatch(r'[0-9a-f]{40}', tag_sha):
            raise ValueError('Invalid annotated baseline tag object')
        tag = gh.api(f'{prefix}/git/tags/{tag_sha}')
        if tag.get('tag') != manifest['tag']:
            raise ValueError('Annotated baseline tag name does not match')
        target = tag.get('object', {})
    if target.get('type') != 'commit' or target.get('sha') != manifest['commit']:
        raise ValueError('Baseline tag no longer resolves to the pinned commit')

    asset = manifest['asset']
    matches = [item for item in release.get('assets', [])
               if item.get('id') == asset['id'] or item.get('name') == asset['name']]
    if len(matches) != 1:
        raise ValueError('Pinned installer is missing or ambiguous in the baseline release')
    asset_path = f'{prefix}/releases/assets/{asset["id"]}'
    for observed in (matches[0], gh.api(asset_path)):
        if (not isinstance(observed, dict) or observed.get('state') != 'uploaded'
                or any(observed.get(key) != asset[key] for key in ('id', 'name', 'size'))
                or observed.get('digest') != 'sha256:' + asset['sha256']):
            raise ValueError('Baseline installer metadata/digest does not match the pin')
    return asset_path


def download_baseline(manifest, output_dir, *, gh=None):
    validate_manifest(manifest)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    installer = output_dir / manifest['asset']['name']
    proof_path = output_dir / 'baseline.json'
    if installer.exists() or proof_path.exists():
        raise FileExistsError('Use a fresh output directory; existing baseline evidence will not be overwritten')
    gh = gh or GitHub()
    asset_path = verify_metadata(manifest, gh)
    proof = {**deepcopy(manifest), 'verified': True}
    # All incomplete or rejected downloads remain inside this owned directory.
    with tempfile.TemporaryDirectory(prefix='.baseline-', dir=output_dir) as temporary:
        candidate = Path(temporary) / installer.name
        gh.download(asset_path, candidate)
        if candidate.stat().st_size != manifest['asset']['size']:
            raise ValueError('Downloaded baseline installer size does not match the pin')
        with candidate.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != manifest['asset']['sha256']:
            raise ValueError('Downloaded baseline installer SHA256 does not match the pin')
        pending_proof = Path(temporary) / 'baseline.json'
        with pending_proof.open('x', encoding='utf-8') as stream:
            json.dump(proof, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        candidate.rename(installer)
        try:
            pending_proof.rename(proof_path)
        except Exception:
            installer.unlink(missing_ok=True)
            raise
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    proof = download_baseline(load_manifest(), args.output_dir.resolve())
    print(json.dumps(proof, ensure_ascii=False))


if __name__ == '__main__':
    main()
