"""Release acceptance must reject missing stages, wrong builds and changed data."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load('release_lifecycle_tests', 'scripts/release.py')
lifecycle = load('windows_lifecycle_tests', 'desktop/scripts/windows-lifecycle.py')
SHA = 'a' * 40
VERSION = '2.0.1'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def reports(tmp_path):
    directory = tmp_path / 'reports'
    identity = {'version': VERSION, 'build_commit': SHA}
    write(directory / 'backend/smoke-backend.json', {**identity, 'status': 'passed'})
    write(directory / 'electron/electron-smoke.json', {**identity, 'passed': True,
          'uses_default_data_directory': True, 'packaged': True, 'platform': 'win32', 'arch': 'x64'})
    write(directory / 'installation.json', {**identity, 'installed': True, 'uninstalled': True,
          'data_preserved': True, 'default_data_directory': True})
    baseline = lifecycle.read_json(ROOT / 'desktop/scripts/upgrade-baseline.json')
    write(directory / 'lifecycle.json', {**identity, 'schema_version': 1, 'status': 'passed',
          'baseline': baseline, 'checks': dict.fromkeys(release.WINDOWS_LIFECYCLE_CHECKS, True)})
    for stage in ('baseline', 'upgrade', 'zip'):
        expected = {'version': baseline['version'], 'build_commit': baseline['commit']} if stage == 'baseline' else identity
        write(directory / stage / 'lifecycle-electron.json', {**expected, 'stage': stage,
              'passed': True, 'packaged': True, 'platform': 'win32', 'arch': 'x64', 'login': True,
              'restart_login': True, 'fixture_preserved': True, 'history_export': True, 'renderer_errors': []})
    data = tmp_path / 'data'; data.mkdir()
    (data / '.app-secret').write_text('fixture-private-secret')
    with sqlite3.connect(data / 'coal_system.db') as connection:
        for table in ('app_user', 'coal_data', 'coal_batches', 'assay_revisions', 'optimization_history', 'system_settings'):
            connection.execute(f'CREATE TABLE {table}(id INTEGER PRIMARY KEY, value TEXT)')
            connection.execute(f'INSERT INTO {table} VALUES(1, ?)', ('retained business value',))
    snapshot = lifecycle.data_checks.snapshot_data(data)
    for name, compare in [('fresh-uninstall-data', lifecycle.data_checks.compare_uninstall),
                          ('upgrade-data', lifecycle.data_checks.compare_upgrade),
                          ('upgraded-uninstall-data', lifecycle.data_checks.compare_uninstall),
                          ('zip-data', lifecycle.data_checks.compare_upgrade)]:
        write(directory / (name + '.json'), {'before': snapshot, 'after': snapshot,
              'comparison': compare(snapshot, snapshot)})
    return directory


def test_complete_lifecycle_is_required_in_release_attestation(reports):
    result = release.validation_report('windows', VERSION, SHA, reports)
    assert {'v2.0.0-in-place-upgrade', 'portable-zip-electron',
            'uninstall-full-database-preservation'} <= set(result['checks'])
    (reports / 'lifecycle.json').unlink()
    with pytest.raises(FileNotFoundError):
        release.validation_report('windows', VERSION, SHA, reports)


@pytest.mark.parametrize('check', release.WINDOWS_LIFECYCLE_CHECKS)
def test_incomplete_stage_cannot_be_stamped_passed(reports, check):
    file = reports / 'lifecycle.json'; report = lifecycle.read_json(file)
    report['checks'][check] = False; write(file, report)
    with pytest.raises(ValueError, match='checks must pass'):
        release.validation_report('windows', VERSION, SHA, reports)


@pytest.mark.parametrize('stage', ['baseline', 'upgrade', 'zip'])
def test_each_executed_app_must_have_the_correct_embedded_sha(reports, stage):
    file = reports / stage / 'lifecycle-electron.json'; report = lifecycle.read_json(file)
    report['build_commit'] = 'b' * 40; write(file, report)
    with pytest.raises(ValueError, match='identity mismatch'):
        release.validation_report('windows', VERSION, SHA, reports)


def test_release_recomputes_data_comparison_instead_of_trusting_passed(reports):
    file = reports / 'upgraded-uninstall-data.json'; report = lifecycle.read_json(file)
    report['after']['tables']['optimization_history']['sha256'] = 'b' * 64
    write(file, report)
    with pytest.raises(ValueError, match='Persistent table evidence changed'):
        release.validation_report('windows', VERSION, SHA, reports)


def test_empty_database_is_not_an_upgrade_fixture(reports):
    file = reports / 'upgrade-data.json'; report = lifecycle.read_json(file)
    for side in ('before', 'after'):
        report[side]['tables']['app_user']['row_count'] = 0
    write(file, report)
    with pytest.raises(ValueError, match='real app_user'):
        release.validation_report('windows', VERSION, SHA, reports)


def test_custom_temporary_database_does_not_prove_default_data_uninstall(reports):
    file = reports / 'electron/electron-smoke.json'; report = lifecycle.read_json(file)
    report['uses_default_data_directory'] = False; write(file, report)
    with pytest.raises(ValueError, match='default database'):
        release.validation_report('windows', VERSION, SHA, reports)


def test_lifecycle_rejects_self_hosted_even_on_windows(monkeypatch):
    monkeypatch.setattr(lifecycle.sys, 'platform', 'win32')
    monkeypatch.setenv('RUNNER_ENVIRONMENT', 'self-hosted')
    with pytest.raises(ValueError, match='disposable GitHub-hosted Windows'):
        lifecycle.require_disposable()


def test_lifecycle_refuses_existing_user_data_before_any_install(monkeypatch, tmp_path):
    monkeypatch.setattr(lifecycle.sys, 'platform', 'win32')
    monkeypatch.setenv('RUNNER_ENVIRONMENT', 'github-hosted')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    (tmp_path / 'CBOS').mkdir()
    with pytest.raises(ValueError, match='Existing CBOS user data'):
        lifecycle.require_disposable()
