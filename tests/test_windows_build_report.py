"""A build service cannot substitute reports from another source tree/version."""
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    'windows_build_report', Path(__file__).parents[1] / 'scripts/ci/windows-build-report.py')
reporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporter)


def test_matching_backend_identity():
    reporter.verify_backend({'status': 'passed', 'build_commit': 'a' * 40, 'version': '2.0.1'},
                            commit='a' * 40, version='2.0.1')


@pytest.mark.parametrize('report', [None, {'status': 'failed'},
    {'status': 'passed', 'build_commit': 'b' * 40, 'version': '2.0.1'},
    {'status': 'passed', 'build_commit': 'a' * 40, 'version': '2.0.0'}])
def test_rejects_missing_failed_or_different_backend(report):
    with pytest.raises(ValueError):
        reporter.verify_backend(report, commit='a' * 40, version='2.0.1')
