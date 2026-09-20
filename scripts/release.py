"""Explicit same-commit release gates. Never creates commits or moves a tag.

Run preflight before builds; publish only after both platform artifacts arrive.
A published release is read-only on retry: its files are downloaded and verified
before resuming the final latest promotion. Secrets are read from the environment.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'^[0-9a-f]{40}$')
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout.strip()


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_identity(version, commit):
    if not VERSION.fullmatch(version) or not SHA.fullmatch(commit):
        raise ValueError('Require explicit X.Y.Z version and full lowercase 40-character commit SHA')


def verify_tree(version, commit, *, root=ROOT):
    validate_identity(version, commit)
    actual = run('git', '-C', str(root), 'rev-parse', 'HEAD')
    if actual != commit:
        raise ValueError('Checked-out commit differs from requested build SHA')
    run('git', '-C', str(root), 'diff-index', '--quiet', 'HEAD', '--')
    module = ast.parse((root / 'app/__version__.py').read_text())
    source = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets))
    versions = [source, read_json(root / 'desktop/package.json')['version'],
                read_json(root / 'desktop/package-lock.json')['version'],
                read_json(root / 'desktop/package-lock.json')['packages']['']['version']]
    if int(version.split('.')[0]) >= 2:
        versions.extend([read_json(root / 'frontend/package.json')['version'],
                         read_json(root / 'frontend/package-lock.json')['version'],
                         read_json(root / 'frontend/package-lock.json')['packages']['']['version']])
    if any(item != version for item in versions):
        raise ValueError(f'Version manifests must already equal {version}; release never edits them')


def release_notes(version, commit, repository, *, changelog=ROOT / 'CHANGELOG.md'):
    validate_identity(version, commit)
    text = Path(changelog).read_text(encoding='utf-8')
    pattern = re.compile(r'^##[ \t]+v?' + re.escape(version) + r'(?=[ \t(]|$).*$', re.MULTILINE)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError('CHANGELOG must contain exactly one finalized section for the requested version')
    following = re.search(r'^##[ \t]+', text[matches[0].end():], re.MULTILINE)
    end = matches[0].end() + following.start() if following else len(text)
    section = text[matches[0].start():end].strip()
    if not re.search(r'^-\s+\S', section, re.MULTILINE):
        raise ValueError('Finalized CHANGELOG section has no release entries')
    base = f'https://github.com/{repository}/releases/download/v{version}'
    return '\n'.join([section, '', f'构建提交：[`{commit}`](https://github.com/{repository}/commit/{commit})', '',
        '### 安装与升级', '',
        f'- [Windows x64 安装包]({base}/CBOS-{version}-windows-x64-setup.exe)',
        f'- [Windows x64 免安装 ZIP]({base}/CBOS-{version}-windows-x64.zip)',
        f'- [Linux amd64 Docker 离线镜像]({base}/cbos-web-{version}-docker-image.tar.gz)',
        f'- [升级、备份与账号恢复说明]({base}/UPGRADE_2.0.md)',
        f'- [SHA-256 校验清单]({base}/SHA256SUMS.txt) · [构建清单]({base}/build-manifest.json) · [验收摘要]({base}/validation-summary.md)', '',
        'Windows 安装包与 ZIP 未签名，系统可能显示未知发布者。安装前核对本仓库来源、完整 SHA 和文件散列；升级前备份现有数据。',
        '', 'Release 下载权限继承仓库访问权限；发布不等于公开，私有仓库需获授权并登录后下载，私有镜像需认证拉取。',
        '', '标签、Linux 镜像与 Windows 资产均对应上述提交；固定版本资产不会在发布后被替换。', ''])


class GitHub:
    def __init__(self, repository):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Invalid GitHub repository')
        self.repository = repository
        self.base = f'https://api.github.com/repos/{repository}'
        self.token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not self.token:
            raise ValueError('GH_TOKEN is required')

    def api(self, path, data=None, method=None, missing=False, global_api=False):
        base = 'https://api.github.com' if global_api else self.base
        request = Request(base + path, data=json.dumps(data).encode() if data is not None else None,
            method=method or ('POST' if data is not None else 'GET'), headers={
                'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=120) as response:
                body = response.read()
                return json.loads(body) if body else None
        except HTTPError as error:
            if missing and error.code == 404:
                return None
            raise RuntimeError(f'GitHub {method or "GET"} {path}: HTTP {error.code}') from None

    def release(self, tag):
        published = self.api(f'/releases/tags/{tag}', missing=True)
        if published:
            return published
        # The by-tag endpoint is documented for published releases. Explicitly
        # paginate drafts for interrupted staging, rather than creating duplicates.
        page = 1
        matches = []
        while True:
            rows = self.api(f'/releases?per_page=100&page={page}')
            matches.extend(row for row in rows if row['tag_name'] == tag)
            if len(rows) < 100:
                break
            page += 1
        if len(matches) > 1:
            raise ValueError('Multiple releases use this tag; resolve duplicate drafts before retrying')
        return matches[0] if matches else None

    def download(self, asset, destination):
        # gh handles authenticated API redirects without forwarding credentials to object storage.
        with Path(destination).open('wb') as stream:
            subprocess.run(['gh', 'api', '-H', 'Accept: application/octet-stream',
                f'/repos/{self.repository}/releases/assets/{asset["id"]}'], stdout=stream, check=True)
        if Path(destination).stat().st_size != asset['size']:
            raise ValueError(f'Incomplete asset download: {asset["name"]}')
        digest = asset.get('digest')
        if digest and digest != 'sha256:' + sha256(destination):
            raise ValueError(f'GitHub asset digest mismatch: {asset["name"]}')


def require_tag(github, tag, commit, *, create=False):
    ref = github.api(f'/git/ref/tags/{tag}', missing=True)
    if ref is None:
        if not create:
            return
        annotation = github.api('/git/tags', {'tag': tag, 'message': f'CBOS {tag}\n\nBuild commit: {commit}',
                                               'object': commit, 'type': 'commit'})
        github.api('/git/refs', {'ref': f'refs/tags/{tag}', 'sha': annotation['sha']})
        return
    if ref['object']['type'] != 'tag':
        raise ValueError('Release requires an annotated tag; an existing lightweight tag will not be replaced')
    annotation = github.api('/git/tags/' + ref['object']['sha'])
    if annotation['object']['type'] != 'commit' or annotation['object']['sha'] != commit:
        raise ValueError('Existing tag targets a different commit; tags are never moved')


def verify_delivery_visibility(github, image, expected, *, allow_missing_package=False):
    """Read-only checks: never turn a repository or package public/private."""
    if expected not in ('private', 'public'):
        raise ValueError('Delivery visibility must be private or public')
    metadata = github.api('')
    if metadata.get('private') is not (expected == 'private') or metadata.get('visibility') != expected:
        raise ValueError('Repository visibility differs from the requested delivery visibility')
    owner = metadata['owner']
    namespace = {'User': 'users', 'Organization': 'orgs'}.get(owner['type'])
    image_owner, separator, package_name = image.removeprefix('ghcr.io/').partition('/')
    if not namespace or not image.startswith('ghcr.io/') or not separator or image_owner.lower() != owner['login'].lower():
        raise ValueError('Image owner must match the repository owner')
    package = github.api(f'/{namespace}/{quote(owner["login"], safe="")}/packages/container/{quote(package_name, safe="")}',
                         global_api=True, missing=True)
    if package is None:
        if allow_missing_package and expected == 'private':
            return  # GitHub creates new packages private by default; check again after staging.
        raise ValueError('Expected package is missing; an owner must configure a public package before public delivery')
    if package.get('visibility') != expected:
        raise ValueError('Package visibility differs from the requested delivery visibility')


def verify_image_access(github, image, version, digest, delivery_visibility):
    verify_delivery_visibility(github, image, delivery_visibility)
    remote = registry_manifest(image, version, anonymous=delivery_visibility == 'public')
    if not remote or remote[1] != digest:
        raise ValueError('Fixed GHCR image must be downloadable with the expected visibility and digest')


def verify_manifest_delivery(manifest, image, delivery_visibility):
    if manifest.get('delivery_visibility') != delivery_visibility or manifest.get('image', {}).get('name') != image:
        raise ValueError('Saved manifest image or delivery visibility differs from this release request')


def preflight(version, commit, repository, delivery_visibility='private'):
    verify_tree(version, commit)
    release_notes(version, commit, repository)
    run('git', 'fetch', '--no-tags', 'origin', 'main', cwd=ROOT)
    run('git', 'merge-base', '--is-ancestor', commit, 'origin/main', cwd=ROOT)
    github = GitHub(repository)
    image = 'ghcr.io/' + repository.lower()
    verify_delivery_visibility(github, image, delivery_visibility, allow_missing_package=True)
    require_tag(github, 'v' + version, commit)
    latest = github.api('/releases/latest', missing=True)
    if latest and VERSION.fullmatch(latest['tag_name'].removeprefix('v')):
        if tuple(map(int, latest['tag_name'].removeprefix('v').split('.'))) > tuple(map(int, version.split('.'))):
            raise ValueError('Refusing to publish/promote an older version over the latest release')
    release = github.release('v' + version)
    if release and release['target_commitish'] != commit:
        raise ValueError('Existing release target_commitish must equal the exact build SHA')
    return {'version': version, 'commit': commit, 'image': image, 'delivery_visibility': delivery_visibility}


def validation_report(platform, version, commit, directory):
    validate_identity(version, commit)
    directory = Path(directory)
    if platform == 'windows':
        backend = read_json(directory / 'backend/smoke-backend.json')
        electron = read_json(directory / 'electron/electron-smoke.json')
        install = read_json(directory / 'installation.json')
        if backend.get('status') != 'passed' or electron.get('passed') is not True:
            raise ValueError('Windows backend and actual installed Electron smoke must both pass')
        if any((report.get('version'), report.get('build_commit')) != (version, commit) for report in (backend, electron)):
            raise ValueError('Both frozen and installed Windows artifacts must report the exact baked-in version/SHA')
        if any(install.get(key) is not True for key in ('installed', 'uninstalled', 'data_preserved')):
            raise ValueError('Actual installation, uninstallation and data preservation must pass')
        checks = ['python', 'frontend', 'desktop-shell', 'frozen-backend', 'installed-electron', 'uninstall-data-preservation']
    else:
        docker = read_json(directory / 'docker-validation.json')
        if docker.get('status') != 'passed' or docker.get('version') != version or docker.get('build_commit') != commit:
            raise ValueError('Docker validation must pass and report this exact version and commit')
        checks = ['python', 'frontend', 'desktop-shell', 'web-build', 'docker-fresh-and-upgrade']
    return {'status': 'passed', 'platform': platform, 'version': version, 'commit': commit,
            'run_id': os.environ.get('GITHUB_RUN_ID'), 'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'), 'checks': checks}


def prepare_assets(version, commit, repository, inputs, destination):
    """Only successful, matching platform evidence is allowed into a release."""
    validate_identity(version, commit)
    inputs, destination = Path(inputs), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    reports = {}
    for platform in ('linux', 'windows'):
        report = read_json(inputs / platform / f'{platform}-validation.json')
        if any(report.get(key) != value for key, value in [('status', 'passed'), ('version', version), ('commit', commit), ('platform', platform)]):
            raise ValueError(f'{platform} validation identity/status mismatch')
        reports[platform] = report
    files = [inputs / 'linux' / f'cbos-web-{version}-docker-image.tar.gz',
             inputs / 'windows' / f'CBOS-{version}-windows-x64-setup.exe',
             inputs / 'windows' / f'CBOS-{version}-windows-x64.zip']
    for file in files:
        if not file.is_file() or not file.stat().st_size:
            raise ValueError(f'Missing release asset {file.name}')
        shutil.copyfile(file, destination / file.name)
    shutil.copyfile(ROOT / 'docs/UPGRADE_2.0.md', destination / 'UPGRADE_2.0.md')
    for platform, report in reports.items():
        write_json(destination / f'{platform}-validation.json', report)
    lines = [f'# CBOS {version} validation', '', f'Build commit: `{commit}`', '',
             f'Run: https://github.com/{repository}/actions/runs/{os.environ.get("GITHUB_RUN_ID", "local")}', '',
             'Both platforms were built from the same commit. All required checks passed.', '']
    for platform, report in reports.items():
        lines += [f'## {platform}', '', *[f'- {check}: passed' for check in report['checks']], '']
    (destination / 'validation-summary.md').write_text('\n'.join(lines), encoding='utf-8')
    return reports


def registry_manifest(image, tag, *, anonymous=False):
    """Return an authenticated manifest and immutable distribution digest, or 404."""
    import base64
    from urllib.parse import urlencode
    repository = image.removeprefix('ghcr.io/')
    headers = {}
    if not anonymous:
        credentials = base64.b64encode((os.environ['GITHUB_ACTOR'] + ':' + (os.environ.get('GH_TOKEN') or os.environ['GITHUB_TOKEN'])).encode()).decode()
        headers['Authorization'] = 'Basic ' + credentials
    query = urlencode({'service': 'ghcr.io', 'scope': f'repository:{repository}:' + ('pull' if anonymous else 'pull,push')})
    with urlopen(Request('https://ghcr.io/token?' + query, headers=headers), timeout=60) as response:
        token = json.load(response)['token']
    request = Request(f'https://ghcr.io/v2/{repository}/manifests/{tag}', headers={'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
    try:
        with urlopen(request, timeout=120) as response:
            return json.load(response), response.headers['Docker-Content-Digest']
    except HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(f'Registry check failed: HTTP {error.code}') from None


def publish_fixed_image(image, version):
    local_id = run('docker', 'image', 'inspect', f'{image}:{version}', '--format', '{{.Id}}')
    existing = registry_manifest(image, version)
    if existing and existing[0].get('config', {}).get('digest') != local_id:
        raise ValueError('Fixed version image already exists with different bytes; it will not be overwritten')
    if not existing:
        run('docker', 'push', f'{image}:{version}')
        existing = registry_manifest(image, version)
    if not existing or existing[0].get('config', {}).get('digest') != local_id:
        raise ValueError('Registry image differs from the tested Docker image')
    return existing[1]


def verify_downloads(github, release, directory, expected_identity):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    assets = {asset['name']: asset for asset in release['assets']}
    if not {'build-manifest.json', 'SHA256SUMS.txt'} <= assets.keys():
        raise ValueError('Release is missing its manifest/checksums')
    for name, asset in assets.items():
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Unsafe release asset name')
        github.download(asset, directory / name)
    manifest = read_json(directory / 'build-manifest.json')
    if (manifest.get('version'), manifest.get('commit')) != expected_identity:
        raise ValueError('Downloaded release identity mismatch')
    sums = {}
    for line in (directory / 'SHA256SUMS.txt').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or name in sums:
            raise ValueError('Invalid checksum list')
        sums[name] = digest
    if set(sums) != set(assets) - {'SHA256SUMS.txt'}:
        raise ValueError('Checksum list and release assets differ')
    for name, digest in sums.items():
        if sha256(directory / name) != digest:
            raise ValueError('Downloaded checksum mismatch: ' + name)
    for name, digest in manifest['assets'].items():
        if sums.get(name) != digest:
            raise ValueError('Manifest asset digest mismatch: ' + name)
    required = {f'CBOS-{manifest["version"]}-windows-x64-setup.exe', f'CBOS-{manifest["version"]}-windows-x64.zip',
                f'cbos-web-{manifest["version"]}-docker-image.tar.gz', 'UPGRADE_2.0.md', 'validation-summary.md',
                'linux-validation.json', 'windows-validation.json'}
    if set(manifest['assets']) != required:
        raise ValueError('Manifest must contain the complete verified asset set')
    if set(assets) != required | {'build-manifest.json', 'SHA256SUMS.txt'}:
        raise ValueError('Unexpected or missing release assets')
    for platform in ('linux', 'windows'):
        report = read_json(directory / f'{platform}-validation.json')
        if report.get('status') != 'passed' or (report.get('version'), report.get('commit')) != expected_identity:
            raise ValueError('Downloaded validation evidence mismatch')
    return manifest


def promote_latest(image, version, digest):
    fixed = registry_manifest(image, version)
    if not fixed or fixed[1] != digest:
        raise ValueError('Fixed image digest changed; latest will not move')
    run('docker', 'pull', f'{image}@{digest}')
    run('docker', 'tag', f'{image}@{digest}', f'{image}:latest')
    run('docker', 'push', f'{image}:latest')
    latest = registry_manifest(image, 'latest')
    if not latest or latest[1] != digest:
        raise ValueError('latest does not resolve to the verified fixed image')


def finish_release(github, release, version, commit, image, digest, delivery_visibility):
    verify_image_access(github, image, version, digest, delivery_visibility)
    if release['draft']:
        github.api(f'/releases/{release["id"]}', {'draft': False, 'make_latest': 'true'}, method='PATCH')
    published = github.api(f'/releases/{release["id"]}')
    if published['draft']:
        raise ValueError('Release is still a draft')
    with tempfile.TemporaryDirectory() as temporary:
        manifest = verify_downloads(github, published, temporary, (version, commit))
    verify_manifest_delivery(manifest, image, delivery_visibility)
    verify_image_access(github, image, version, digest, delivery_visibility)
    promote_latest(image, version, digest)


def publish(version, commit, repository, inputs, destination, delivery_visibility='private'):
    identity = preflight(version, commit, repository, delivery_visibility)
    github = GitHub(repository); tag = 'v' + version; image = identity['image']
    release = github.release(tag)
    if release and not release['draft']:
        # Retry after publication only verifies existing immutable content and finishes promotion.
        with tempfile.TemporaryDirectory() as temporary:
            manifest = verify_downloads(github, release, temporary, (version, commit))
        verify_manifest_delivery(manifest, image, delivery_visibility)
        verify_image_access(github, image, version, manifest['image']['digest'], delivery_visibility)
        promote_latest(image, version, manifest['image']['digest'])
        return
    verify_delivery_visibility(github, image, delivery_visibility, allow_missing_package=True)
    existing_image = registry_manifest(image, version)
    if existing_image:
        # A previous attempt may have pushed the fixed image before publication
        # failed. Rebuilding this SHA need not reproduce byte-identical binaries.
        # Resume the original complete draft, never pair it with new artifacts.
        if release is None:
            raise ValueError('Fixed image exists without its verified draft; refusing to replace it')
        with tempfile.TemporaryDirectory() as temporary:
            manifest = verify_downloads(github, release, temporary, (version, commit))
            verify_manifest_delivery(manifest, image, delivery_visibility)
            if manifest['image']['name'] != image or manifest['image']['digest'] != existing_image[1]:
                raise ValueError('Existing fixed image does not match the saved draft manifest')
            run('docker', 'load', '--input', str(Path(temporary) / f'cbos-web-{version}-docker-image.tar.gz'))
            loaded = run('docker', 'image', 'inspect', f'{image}:{version}', '--format', '{{.Id}}')
            if loaded != existing_image[0].get('config', {}).get('digest'):
                raise ValueError('Draft offline Docker archive does not match the fixed registry image')
        github.api(f'/releases/{release["id"]}', {'body': release_notes(version, commit, repository)}, method='PATCH')
        finish_release(github, release, version, commit, image, existing_image[1], delivery_visibility)
        return
    reports = prepare_assets(version, commit, repository, inputs, destination)
    destination = Path(destination)
    archive = destination / f'cbos-web-{version}-docker-image.tar.gz'
    run('docker', 'load', '--input', str(archive))
    require_tag(github, tag, commit, create=True)
    if not release:
        release = github.api('/releases', {'tag_name': tag, 'target_commitish': commit, 'name': f'CBOS {version}',
            'body': release_notes(version, commit, repository),
            'draft': True, 'prerelease': False, 'make_latest': 'false'})
    else:
        github.api(f'/releases/{release["id"]}', {'body': release_notes(version, commit, repository)}, method='PATCH')
    # A per-run staging tag determines the distribution digest without assigning
    # the immutable version tag until the complete draft is downloaded/verified.
    staging = f'staging-{commit}-{os.environ.get("GITHUB_RUN_ID", "local")}-{os.environ.get("GITHUB_RUN_ATTEMPT", "1")}'
    verify_delivery_visibility(github, image, delivery_visibility, allow_missing_package=True)
    run('docker', 'tag', f'{image}:{version}', f'{image}:{staging}')
    digest = publish_fixed_image(image, staging)
    manifest = {**identity, 'image': {'name': image, 'tag': version, 'digest': digest},
        'run': {'id': os.environ.get('GITHUB_RUN_ID'), 'attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
                'url': f'https://github.com/{repository}/actions/runs/{os.environ.get("GITHUB_RUN_ID", "local")}'},
        'validation': reports, 'assets': {file.name: sha256(file) for file in sorted(destination.iterdir()) if file.is_file()
                                        and file.name not in ('build-manifest.json', 'SHA256SUMS.txt')}}
    write_json(destination / 'build-manifest.json', manifest)
    checksums = ''.join(f'{sha256(file)}  {file.name}\n' for file in sorted(destination.iterdir()) if file.is_file() and file.name != 'SHA256SUMS.txt')
    (destination / 'SHA256SUMS.txt').write_text(checksums, encoding='ascii')
    for file in sorted(destination.iterdir()):
        if not file.is_file():
            continue
        current = github.api(f'/releases/{release["id"]}')
        if not current['draft'] or current['target_commitish'] != commit:
            raise ValueError('Release changed during staging; no assets will be overwritten')
        previous = next((asset for asset in current['assets'] if asset['name'] == file.name), None)
        if previous:
            # A failed GitHub upload can leave a zero-byte `starter` asset
            # without a downloadable object. Only completed uploads can be
            # reused by checksum; incomplete draft uploads need replacement.
            if previous.get('state') == 'uploaded':
                with tempfile.TemporaryDirectory() as temporary:
                    downloaded = Path(temporary) / file.name
                    github.download(previous, downloaded)
                    if sha256(downloaded) == sha256(file):
                        continue
            # Only a still-private draft at this exact commit may replace a partial/rebuilt asset.
            current = github.api(f'/releases/{release["id"]}')
            if not current['draft'] or current['target_commitish'] != commit:
                raise ValueError('Refusing to replace a public release asset')
            github.api(f'/releases/assets/{previous["id"]}', method='DELETE')
        run('gh', 'release', 'upload', tag, str(file), '--repo', repository)
    staged = github.api(f'/releases/{release["id"]}')
    with tempfile.TemporaryDirectory() as temporary:
        verify_downloads(github, staged, temporary, (version, commit))
    verify_delivery_visibility(github, image, delivery_visibility)
    if publish_fixed_image(image, version) != digest:
        raise ValueError('Fixed image and verified draft digest differ')
    finish_release(github, staged, version, commit, image, digest, delivery_visibility)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify-tree', 'preflight', 'stamp-validation', 'publish'])
    parser.add_argument('--version', required=True); parser.add_argument('--sha', required=True)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--delivery-visibility', choices=['private', 'public'], default='private')
    parser.add_argument('--platform', choices=['linux', 'windows']); parser.add_argument('--reports', type=Path)
    parser.add_argument('--inputs', type=Path); parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'verify-tree': verify_tree(args.version, args.sha)
    elif args.command == 'preflight': print(json.dumps(preflight(args.version, args.sha, args.repo, args.delivery_visibility)))
    elif args.command == 'stamp-validation':
        verify_tree(args.version, args.sha)
        write_json(args.output, validation_report(args.platform, args.version, args.sha, args.reports))
    else: publish(args.version, args.sha, args.repo, args.inputs, args.output, args.delivery_visibility)


if __name__ == '__main__':
    main()
