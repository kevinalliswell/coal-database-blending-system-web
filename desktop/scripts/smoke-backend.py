"""Exercise a frozen backend, then restart it to verify SQLite persistence.

Only the Python standard library is used by the smoke driver. The child runs
from a temporary directory, with no Python/Node installation on its Windows
PATH, and must use the bundled frontend, migrations and scientific libraries.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import io
import json
import math
import os
from pathlib import Path
import queue
import secrets
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
from http.cookiejar import CookieJar
import zipfile


class Backend:
    def __init__(self, port: int, token: str):
        self.base_url = f"http://127.0.0.1:{port}"
        self.token = token
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        self.csrf_token = ''

    def request(self, path: str, data=None, *, method=None, authenticated=True):
        headers = {"X-CBOS-Token": self.token} if authenticated else {}
        body = None
        if self.csrf_token:
            headers['X-CSRF-Token'] = self.csrf_token
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=body, headers=headers, method=method)
        with self.opener.open(request, timeout=120) as response:
            return response.read()

    def login(self, setup=False):
        session = self.json('/api/auth/session')
        assert session['setup_required'] is setup
        self.csrf_token = session['csrf_token']
        logged_in = self.json('/api/auth/' + ('setup' if setup else 'login'),
                              {'username': 'desktopadmin', 'password': 'Smoke-password-2026!'})
        self.csrf_token = logged_in['csrf_token']
        assert logged_in['user']['role'] == 'admin'

    def json(self, path: str, data=None, **kwargs):
        return json.loads(self.request(path, data, **kwargs))


@contextmanager
def launch(executable: Path, data_dir: Path, output: Path, run_name: str):
    token = secrets.token_hex(32)
    environment = os.environ.copy()
    environment.pop('CBOS_BUILD_SHA', None)
    environment.pop('CBOS_BUILD_TIME', None)
    environment.update({"CBOS_DESKTOP_DATA_DIR": str(data_dir), "CBOS_DESKTOP_TOKEN": token})
    if os.name == "nt":
        # The executable must not accidentally load an installed Python/Node.
        environment["PATH"] = str(Path(os.environ["SYSTEMROOT"]) / "System32")
    lines = queue.Queue()
    with (output / f"backend-{run_name}.log").open("wb") as log:
        process = subprocess.Popen(
            [str(executable)], cwd=data_dir.parent, env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
        )

        def read_stdout():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        threading.Thread(target=read_stdout, daemon=True).start()
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    line = lines.get(timeout=min(1, max(0.01, deadline - time.monotonic())))
                except queue.Empty:
                    continue
                if line is None:
                    raise RuntimeError(f"Backend exited before ready; see backend-{run_name}.log")
                try:
                    ready = json.loads(line)
                except (ValueError, UnicodeDecodeError) as error:
                    raise RuntimeError("Backend stdout must contain only protocol JSON") from error
                if ready.get("type") == "ready":
                    assert "token" not in ready, "Ready message must not reveal its token"
                    port = ready["port"]
                    assert isinstance(port, int) and 0 < port < 65536
                    yield Backend(port, token)
                    break
            else:
                raise TimeoutError(f"Backend did not become ready; see backend-{run_name}.log")
        finally:
            # This is the production parent-lifetime protocol, not a force kill.
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError("Backend failed to stop after parent stdin closed")
            process.stdout.close()
        assert process.returncode == 0, f"Backend exit code: {process.returncode}"


def run_smoke(executable: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="CBOS smoke 测试 ") as temporary:
        data_dir = Path(temporary) / "user data"
        with launch(executable, data_dir, output, "first") as backend:
            recovery = subprocess.run([str(executable), '--reset-password', 'desktopadmin',
                '--data-dir', str(data_dir)], input=b'', capture_output=True, timeout=15)
            assert recovery.returncode != 0, 'Recovery must refuse a running backend'
            assert '关闭'.encode('utf-8') in recovery.stderr, recovery.stderr
            for path, transport in [('/health', False), ('/api/catalog', True)]:
                try:
                    backend.request(path, authenticated=transport)
                    raise AssertionError("Unauthenticated request was accepted")
                except HTTPError as error:
                    assert error.code in (401, 403), error.code
            backend.login(setup=True)
            build = backend.json('/api/system/info')['data']
            health = backend.json('/health')
            assert health['status'] == 'ok' and health['storage_mode'] == 'sqlite'
            html = backend.request('/').decode('utf-8')
            assert 'assets/' in html and '前端尚未构建' not in html
            legacy = backend.json('/api/assays')['data']
            assert len(legacy) == 8
            assert all(not assay['eligibility']['blending']['eligible'] for assay in legacy)
            settings = backend.json('/api/settings')['data']
            assays = []
            for index in range(6):
                anthracite = index < 3
                coal = backend.json('/api/catalog', {'name': f'离线验收煤-{index + 1}',
                    'type': '无烟煤' if anthracite else '烟煤'})['data']
                batch = backend.json(f'/api/catalog/{coal["id"]}/batches', {'code': '验收批次-001'})['data']
                values = {'ash_content': 10, 'volatile_matter': 10 if anthracite else 30,
                          'fixed_carbon': 78 if anthracite else 58, 'total_sulfur': .5,
                          'total_moisture': 2, 'price': 900 - index * 30,
                          'calorific_value': 7500 - index * 150}
                raw = {key: {'value': value, 'unit': 'CNY/t' if key == 'price' else 'kcal/kg' if key == 'calorific_value' else '%',
                             'basis': 'ar'} for key, value in values.items()}
                raw['calorific_value']['heat_type'] = 'net_v'
                assay = backend.json(f'/api/batches/{batch["id"]}/assays', {'raw': raw})['data']
                assert assay['eligibility']['blending']['eligible'], assay
                assays.append(assay)
            selected_ids = [assay['id'] for assay in assays]
            constraints = {'heat_min': 0, 'heat_max': 10000, 'ash_min': 0, 'ash_max': 100,
                'volatile_min': 0, 'volatile_max': 100, 'fixed_carbon_min': 0, 'fixed_carbon_max': 100,
                'sulfur_min': 0, 'sulfur_max': 10, 'price_min': 0, 'price_max': 5000}
            result = backend.json('/api/optimization', {
                'components': [{'assay_revision_id': item, 'min_ratio': 5, 'max_ratio': 60} for item in selected_ids],
                'settings_version': settings['version'], 'constraints': constraints,
                'ga_params': {'population_size': 24, 'max_generations': 8,
                              'early_stopping_patience': 4, 'random_seed': 42}})
            assert result['status'] == 'success' and result['history_saved'], result
            solution = result['result']; ratios = solution['optimal_ratios']
            assert solution['is_feasible'] and len(ratios) == 6
            assert solution['data_validation']['status'] == 'verified'
            assert result['input_snapshot']['schema_version'] == 2
            assert math.isclose(sum(ratios), 1, abs_tol=1e-8)
            assert all(.05 - 1e-8 <= ratio <= .60 + 1e-8 for ratio in ratios)
            for result_key, metric in [('total_price', 'price'), ('total_heat', 'calorific_value')]:
                expected = sum(ratio * assay['eligibility']['blending']['values'][metric] for assay, ratio in zip(assays, ratios))
                assert math.isclose(solution[result_key], expected, rel_tol=1e-8, abs_tol=1e-6)
            history = backend.json('/api/optimization/history')['data']
            assert len(history) == 1
            history_id = history[0]['id']
            report = backend.request(f'/api/optimization/export/{history_id}')
            with zipfile.ZipFile(io.BytesIO(report)) as workbook:
                assert 'xl/workbook.xml' in workbook.namelist()
            (output / 'optimization-report.xlsx').write_bytes(report)
            # Same batch creates a new immutable revision; the old result keeps its original input.
            revised_raw = {**assays[0]['raw'], 'price': {'value': 950, 'unit': 'CNY/t', 'basis': 'ar'}}
            updated = backend.json(f'/api/batches/{assays[0]["batch_id"]}/assays', {'raw': revised_raw})['data']
            assert updated['revision'] == 2
            saved_settings = backend.json('/api/settings', {**settings, 'organization': '离线验收组织'}, method='PUT')['data']

        with launch(executable, data_dir, output, 'restart') as backend:
            try:
                backend.request('/api/catalog')
                raise AssertionError('Restart must require login')
            except HTTPError as error:
                assert error.code == 401
            backend.login()
            restored = backend.json('/api/assays')['data']
            assert len(restored) == len(legacy) + 7
            assert next(item for item in restored if item['id'] == assays[0]['id'])['raw']['price']['value'] == 900
            assert next(item for item in restored if item['id'] == updated['id'])['raw']['price']['value'] == 950
            persisted = backend.json(f'/api/optimization/history/{history_id}')['data']
            assert persisted['result_payload']['input_snapshot'] == result['input_snapshot']
            assert persisted['result_payload']['result']['optimal_ratios'] == ratios
            assert backend.json('/api/settings')['data'] == saved_settings
        return {'status': 'passed', 'version': build['version'], 'build_commit': build['build_commit'],
                'executable': str(executable), 'assay_revision_ids': selected_ids,
                'anthracite_count': 3, 'bituminous_count': 3, 'optimal_ratios': ratios,
                'total_price': solution['total_price'], 'total_heat': solution['total_heat'],
                'history_id': history_id, 'restart_persistence': True, 'xlsx_export': True,
                'parent_eof_shutdown': True, 'unauthenticated_rejected': True,
                'initial_admin_setup': True, 'immutable_assay_revisions': True,
                'settings_persistence': True, 'legacy_unknown_ineligible': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("desktop/smoke-output/backend"))
    args = parser.parse_args()
    report = run_smoke(args.executable.resolve(strict=True), args.output.resolve())
    (args.output / "smoke-backend.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
