"""Run a real Docker image against disposable fresh and 1.x databases."""
import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import http.cookiejar
import json
import math
from pathlib import Path
import secrets
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPCookieProcessor, Request
import uuid


def docker(*args, source=None):
    return subprocess.check_output(['docker', *args], input=source, text=True).strip()


class API:
    def __init__(self, url):
        self.url = url
        self.csrf = ''
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, body=None, method=None, expected=200, binary=False, timeout=180):
        method = method or ('POST' if body is not None else 'GET')
        headers = {'X-CSRF-Token': self.csrf, 'Content-Type': 'application/json'}
        request = Request(self.url + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        raw = response.read()
        assert response.status == expected, (path, response.status, raw[:400])
        if binary:
            assert raw
            return raw
        value = json.loads(raw)
        if value.get('csrf_token'):
            self.csrf = value['csrf_token']
        return value

    def login(self, username, password):
        self.call('/api/auth/session')
        return self.call('/api/auth/login', {'username': username, 'password': password})


def raw_assay(index):
    values = {
        'total_moisture': (8 + index, '%', 'ar'), 'ash_content': (10 + index, '%', 'd'),
        'volatile_matter': (9 + index if index < 3 else 32 + index, '%', 'daf'),
        'total_sulfur': (.5 + .03 * index, '%', 'd'), 'calorific_value': (29 - .4 * index, 'MJ/kg', 'ar'),
        'price': (950 - 50 * index, 'CNY/t', 'ar'), 'carbon_content': (78, '%', 'd'),
        'hydrogen_content': (3.5, '%', 'd'), 'sio2_content': (48, '%', 'ash'),
    }
    raw = {key: dict(value=value, unit=unit, basis=basis) for key, (value, unit, basis) in values.items()}
    raw['calorific_value']['heat_type'] = 'net_v'
    raw['hydrogen_content']['hydrogen_includes_moisture'] = False
    return raw


def verify_blend(payload):
    assert payload['status'] == 'success' and payload['history_saved']
    assert payload['input_snapshot']['schema_version'] == 2
    front = payload['result']['pareto_solutions']
    assert isinstance(front, list) and front, 'Expected a nonempty six-coal Pareto front'
    recommendation = payload['result']['recommended_solution']
    assert isinstance(recommendation, dict) and recommendation, 'Missing recommendation'
    for candidate in [*front, recommendation]:
        ratios = candidate['optimal_ratios']
        assert len(ratios) == 6 and all(math.isfinite(value) for value in ratios), 'Expected six finite ratios'
        assert math.isclose(sum(ratios), 1, abs_tol=1e-8)
        assert all(.05 - 1e-8 <= value <= .6 + 1e-8 for value in ratios)
        expected = dict(total_price=0., total_heat=0., total_ash=0., total_volatile=0., total_fixed_carbon=0., total_sulfur=0.)
        for i, ratio in enumerate(ratios):
            dry = 1 - (8 + i) / 100
            ash = 10 + i
            volatile = (9 + i if i < 3 else 32 + i) * (100 - ash) / 100
            for key, value in dict(total_price=950-50*i, total_heat=(29-.4*i)/.0041868,
                    total_ash=ash*dry, total_volatile=volatile*dry,
                    total_fixed_carbon=(100-ash-volatile)*dry, total_sulfur=(.5+.03*i)*dry).items():
                expected[key] += ratio * value
        for key, value in expected.items():
            assert math.isclose(candidate[key], value, abs_tol=1e-5), key


def verify_system(info, expected_commit, expected_version):
    assert expected_commit and expected_commit != 'unknown'
    assert info['build_commit'] == expected_commit, ('build_commit', info, expected_commit)
    assert info['version'] == expected_version, ('version', info, expected_version)
    assert info['mode'] == 'web'


def wait_ready(url, timeout=90):
    deadline = time.monotonic() + timeout
    last_error = None
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            health = API(url).call('/health', timeout=min(5, remaining))
            assert health.get('status') == 'ok', health
            return
        except (URLError, ConnectionError, TimeoutError, HTTPException, json.JSONDecodeError, AssertionError) as error:
            # Docker may accept the port before Gunicorn can serve a response.
            # Only readiness probes retry; business API calls remain strict.
            last_error = error
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise RuntimeError('Container did not become healthy') from last_error


def scenario(image, output, expected_commit, expected_version, legacy=False):
    suffix = uuid.uuid4().hex[:12]
    name, volume = 'cbos-qa-' + suffix, 'cbos-qa-data-' + suffix
    docker('volume', 'create', volume)
    try:
        if legacy:
            docker('run', '--rm', '-i', '--entrypoint', 'python', '-v', volume + ':/app/data', image, '-', source='''
from app import create_app
from flask_migrate import upgrade
import sqlite3
app=create_app()
with app.app_context(): upgrade(revision='c8a1d24f5e67')
with sqlite3.connect('/app/data/coal_system.db') as c:
    c.execute("insert into coal_data (id,name,type,price,calorific_value,ash_content,volatile_matter,fixed_carbon,total_sulfur) values (1,'旧库原值','无烟煤',998.46,7419,11.5877775,9.6089175,76.3035,.9)")
''')
        docker('run', '-d', '--name', name, '-p', '127.0.0.1::5000', '-v', volume + ':/app/data', image)
        port = docker('port', name, '5000/tcp').split(':')[-1]
        url = 'http://127.0.0.1:' + port
        wait_ready(url)
        # A healthy API alone does not prove the compiled UI/help were packaged.
        assets = json.loads(docker('exec', name, 'python', '-c', '''
import json
from pathlib import Path
root=Path('/app')
index=(root/'frontend/dist/index.html').read_text()
assert '<script' in index and '/assets/' in index
assert '前端尚未构建' not in index
scripts=list((root/'frontend/dist/assets').glob('*.js'))
assert scripts and any('CBOS 2.0 用户手册' in script.read_text() for script in scripts)
for name in ('USER_GUIDE.md','API_REFERENCE.md','ASSAY_CONVERSION.md'):
    assert (root/'docs'/name).is_file()
assert (root/'CHANGELOG.md').is_file()
print(json.dumps({'frontend_assets':len(scripts),'docs_packaged':True}))
'''))
        api = API(url)
        assert b'<script' in api.call('/help', binary=True)
        api.call('/api/catalog', expected=401)
        password = secrets.token_urlsafe(24)
        docker('exec', '-i', name, 'python', '-', source='''
from app import create_app
from app.services.access_service import create_initial_admin
app=create_app()
with app.app_context(): create_initial_admin('qaadmin', %r, 'Container QA')
''' % password)
        api.login('qaadmin', password)
        csrf = api.csrf
        api.csrf = ''
        assert api.call('/api/catalog', {'name':'csrf-rejected','type':'烟煤'}, expected=403)['code'] == 'csrf_failed'
        api.csrf = csrf
        info = api.call('/api/system/info')['data']
        verify_system(info, expected_commit, expected_version)
        if legacy:
            catalog = api.call('/api/catalog')['data']
            assert len(catalog) == 1 and catalog[0]['name'] == '旧库原值'
            assay = catalog[0]['batches'][0]['latest_assay']
            for field, value in {'price':998.46,'calorific_value':7419,'ash_content':11.5877775,
                                 'volatile_matter':9.6089175,'fixed_carbon':76.3035,'total_sulfur':.9}.items():
                assert assay['raw'][field]['value'] == value
                assert assay['raw'][field]['basis'] == 'unknown'
            assert assay['sampled_at'] is None and catalog[0]['batches'][0]['received_at'] is None
            assert assay['raw']['calorific_value']['heat_type'] == 'unknown'
            assert not assay['eligibility']['blending']['eligible']
            backup_count = docker('exec', name, 'python', '-c', "from pathlib import Path;print(len(list(Path('/app/data/backups').glob('*.db'))))")
            assert backup_count == '1'
            docker('exec', name, 'python', '-c', '''
from pathlib import Path
import sqlite3
backup=list(Path('/app/data/backups').glob('*.db'))[0]
with sqlite3.connect(backup) as db:
    assert db.execute('select version_num from alembic_version').fetchone()[0]=='c8a1d24f5e67'
    assert db.execute('select fixed_carbon from coal_data where id=1').fetchone()[0]==76.3035
''')
            docker('restart', name); wait_ready(url)
            assert len(api.call('/api/catalog')['data']) == 1
            verify_system(api.call('/api/system/info')['data'], expected_commit, expected_version)
            assert docker('exec', name, 'python', '-c', "from pathlib import Path;print(len(list(Path('/app/data/backups').glob('*.db'))))") == '1'
            return {'scenario': 'upgrade-from-1.x', 'passed': True, 'backup_count': 1, 'backup_content_verified':True,
                    'raw_values_preserved': True, 'system': info, **assets}

        seeded = api.call('/api/catalog')['data']
        assert len(seeded) == 8, 'Fresh install must seed the eight historical examples exactly once'
        assert all(not coal['batches'][0]['latest_assay']['eligibility']['blending']['eligible'] for coal in seeded)
        assays = []
        for i in range(6):
            coal = api.call('/api/catalog', {'name': f'容器验收煤{i+1}', 'type': '无烟煤' if i < 3 else '烟煤'}, expected=201)['data']
            batch = api.call(f'/api/catalog/{coal["id"]}/batches', {'code': 'B001'}, expected=201)['data']
            assay = api.call(f'/api/batches/{batch["id"]}/assays', {'raw': raw_assay(i)}, expected=201)['data']
            assert assay['eligibility']['blending']['eligible']
            assays.append(assay)
        request = {'settings_version': 1, 'components': [dict(assay_revision_id=a['id'], min_ratio=5, max_ratio=60) for a in assays],
                   'constraints': {'heat_min': 5800, 'heat_max': 7800, 'volatile_min': 0, 'fixed_carbon_min': 0},
                   'ga_params': {'population_size': 24, 'max_generations': 8, 'tournament_size': 3, 'random_seed': 37}}
        result = api.call('/api/optimization', request)
        verify_blend(result)
        assert [record['id'] for record in result['input_snapshot']['assays']] == [record['id'] for record in assays]
        assert result['input_snapshot']['operator']['username'] == 'qaadmin'
        history = api.call('/api/optimization/history')['data'][0]
        api.call(f'/api/optimization/export/{history["id"]}', binary=True)
        partial = api.call(f'/api/batches/{assays[0]["batch_id"]}/assays', {'raw': {}}, expected=201)['data']
        assert not partial['eligibility']['blending']['eligible']
        snapshot = api.call(f'/api/optimization/history/{history["id"]}')['data']['result_payload']['input_snapshot']
        assert snapshot == result['input_snapshot']
        invalid = {**request, 'components': [dict(assay_revision_id=a['id'], min_ratio=0, max_ratio=100) for a in (assays[0], partial)]}
        assert api.call('/api/optimization', invalid, expected=422)['code'] == 'data_conflict'
        second_batch = api.call(f'/api/catalog/{assays[0]["coal_id"]}/batches', {'code': 'B002'}, expected=201)['data']
        second = api.call(f'/api/batches/{second_batch["id"]}/assays', {'raw': raw_assay(1)}, expected=201)['data']
        same_coal = {**request, 'components': [dict(assay_revision_id=a['id'], min_ratio=40, max_ratio=60) for a in (assays[0], second)]}
        assert api.call('/api/optimization', same_coal)['status'] == 'success'
        api.call('/api/catalog/template?format=xlsx', binary=True)
        api.call('/api/catalog/export?format=csv', binary=True)
        preview = api.call('/api/catalog/import/preview', {'text':'coal_name,type,batch_code\n容器导入煤,烟煤,进口批次\n'})['data']
        assert preview['can_commit']
        api.call('/api/catalog/import/commit', {'preview_token': preview['preview_token']}, expected=201)
        api.call('/api/calculate_theory_ratio', {'settings_version': 1, 'assay_revision_id': assays[0]['id'],
            'coal_params': {'heat_unit':'kJ/kg','decomposition_heat':920,'physical_heat':1884},
            'coke_params': {'analysis_basis':'d','carbon_content':.86,'ash_content':.11,'sio2_content':.52},
            'blast_furnace_params': {'eta_co':.4444,'slag_basicity':1.15,'slag_enthalpy':1800,'hot_blast_enthalpy':1.5}})
        # Actual role enforcement is observed through separate cookie jars.
        for role in ('data_manager', 'calculator', 'viewer'):
            api.call('/api/users', {'username': role, 'password': password, 'role': role}, expected=201)
            user_api = API(url); user_api.login(role, password)
            user_api.call('/api/catalog')
            user_api.call('/api/catalog/export?format=csv', binary=True)
            user_api.call('/api/users', expected=403)
            user_api.call('/api/settings', {'version':1, 'system_name':'forbidden'}, method='PUT', expected=403)
            if role != 'data_manager':
                user_api.call('/api/catalog', {'name':'forbidden','type':'烟煤'}, expected=403)
            else:
                user_api.call('/api/catalog', {'name':'维护员正常录入','type':'烟煤'}, expected=201)
            if role != 'calculator':
                user_api.call('/api/optimization', request, expected=403)
            else:
                calculated = user_api.call('/api/optimization', request)
                verify_blend(calculated)
                assert calculated['input_snapshot']['operator']['username'] == 'calculator'
        api.call('/api/auth/logout', {})
        api.call('/api/catalog', expected=401)
        docker('restart', name); wait_ready(url)
        api.login('qaadmin', password)
        verify_system(api.call('/api/system/info')['data'], expected_commit, expected_version)
        persisted = api.call(f'/api/optimization/history/{history["id"]}')['data']['result_payload']['input_snapshot']
        assert persisted == snapshot
        return {'scenario':'fresh-install', 'passed':True, 'system':info, 'coal_mix':'3 anthracite + 3 bituminous',
                'pareto_candidates_recomputed':len(result['result']['pareto_solutions']),
                'recommendation_recomputed':True,
                'same_coal_multiple_batches':True, 'partial_storage':True, 'import_export':True,
                'four_role_permissions':True, 'positive_data_manager_write':True, 'positive_calculator_compute':True,
                'logout_and_restart':True, 'immutable_snapshot':True, **assets}
    except Exception:
        try:
            (output / f'{"upgrade" if legacy else "fresh"}-container.log').write_text(docker('logs', name), encoding='utf-8')
        except subprocess.CalledProcessError:
            pass
        raise
    finally:
        subprocess.run(['docker','rm','-f',name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker','volume','rm',volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--expected-platform', default='linux/amd64')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    image_info = json.loads(docker('image', 'inspect', args.image))[0]
    image_id = image_info['Id']
    platform = image_info['Os'] + '/' + image_info['Architecture']
    assert platform == args.expected_platform, (platform, args.expected_platform)
    assert image_info.get('Config', {}).get('Labels', {}).get('org.opencontainers.image.revision') == args.expected_commit
    # Resolve a mutable local tag once: both scenarios exercise exactly one image.
    cases = [scenario(image_id, args.output, args.expected_commit, args.expected_version),
             scenario(image_id, args.output, args.expected_commit, args.expected_version, legacy=True)]
    assert cases[0]['system']['version'] == cases[1]['system']['version']
    assert cases[0]['system']['build_commit'] == cases[1]['system']['build_commit']
    report = {'status':'passed', 'passed':True, 'version':cases[0]['system']['version'], 'build_commit':cases[0]['system']['build_commit'],
              'checks':['fresh_initialize','legacy_upgrade_and_backup','login_csrf','six_coal_independent_recomputation','same_coal_multiple_batches','partial_data_gate','import_export','theory_ratio','four_roles','logout_restart_snapshot','docs_and_compiled_help','expected_sha_and_version'],
              'image':args.image,'image_id':image_id,'platform':platform,'tested_at':datetime.now(timezone.utc).isoformat(),'cases':cases}
    (args.output / 'docker-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Docker fresh/upgrade, authentication, six-coal recomputation, import/export and persistence: PASS')


if __name__ == '__main__':
    main()
