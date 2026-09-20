"""Immutable batch input and independent mass/quality balance acceptance."""
from copy import deepcopy
import pytest
from backend.utils.optimization_validation import normalize_assay_request

SETTINGS = {'version': 1, 'constraints': {}, 'ga_params': {}}


def test_v2_rejects_ambiguous_coal_ids_and_removed_screening_mode():
    with pytest.raises(ValueError, match='接口已升级'):
        normalize_assay_request({'selected_coal_ids': [1, 2]}, SETTINGS)
    with pytest.raises(ValueError, match='不再接受'):
        normalize_assay_request({'components': [], 'calculation_mode': 'screening'}, SETTINGS)


def test_v2_requires_current_settings_and_unambiguous_ratio_bounds():
    body = {'settings_version': 1, 'components': [
        {'assay_revision_id': 1, 'min_ratio': 0, 'max_ratio': 100},
        {'assay_revision_id': 2, 'min_ratio': 0, 'max_ratio': 100}]}
    assert normalize_assay_request(body, SETTINGS)['components'] == body['components']
    with pytest.raises(ValueError, match='设置已改变'):
        normalize_assay_request({**body, 'settings_version': 2}, SETTINGS)
    duplicate = deepcopy(body); duplicate['components'][1]['assay_revision_id'] = 1
    with pytest.raises(ValueError, match='不能重复'):
        normalize_assay_request(duplicate, SETTINGS)


@pytest.fixture
def v2_client(tmp_path):
    from app import create_app
    from app.extensions import db
    from access_helpers import authenticated_client
    app = create_app('production', {'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "v2.db"}',
                                   'DATA_DIR': str(tmp_path), 'UPLOAD_FOLDER': str(tmp_path / 'uploads')})
    with app.app_context():
        db.create_all()
    client = authenticated_client(app)
    yield client
    with app.app_context():
        db.session.remove(); db.drop_all()


def raw_fixture(index=0):
    # Deliberately mix common Chinese report fields: Mt, Ad, Vdaf, St,d, Qnet,v,ar.
    return {
        'total_moisture': {'value': 8 + index, 'basis': 'ar', 'unit': '%'},
        'ash_content': {'value': 10 + index, 'basis': 'd', 'unit': '%'},
        'volatile_matter': {'value': 9 + index if index < 3 else 32 + index, 'basis': 'daf', 'unit': '%'},
        'total_sulfur': {'value': .5 + .03 * index, 'basis': 'd', 'unit': '%'},
        'calorific_value': {'value': 29 - .4 * index, 'basis': 'ar', 'unit': 'MJ/kg', 'heat_type': 'net_v'},
        'price': {'value': 950 - 50 * index, 'basis': 'ar', 'unit': 'CNY/t'},
    }


def add_assay(client, name, index=0, coal_id=None, batch_code='B1'):
    if coal_id is None:
        response = client.post('/api/catalog', json={'name': name, 'type': '无烟煤' if index < 3 else '烟煤'})
        assert response.status_code == 201, response.get_json()
        coal_id = response.get_json()['data']['id']
    batch = client.post(f'/api/catalog/{coal_id}/batches', json={'code': batch_code}).get_json()['data']
    response = client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': raw_fixture(index)})
    assert response.status_code == 201, response.get_json()
    return response.get_json()['data']


def request_for(assays):
    return {'settings_version': 1, 'components': [{'assay_revision_id': a['id'], 'min_ratio': 5, 'max_ratio': 60} for a in assays],
            'constraints': {'heat_min': 5800, 'heat_max': 7800, 'volatile_min': 0, 'fixed_carbon_min': 0},
            'ga_params': {'population_size': 24, 'max_generations': 8, 'tournament_size': 3, 'random_seed': 37}}


def test_three_anthracite_three_bituminous_are_independently_recomputed(v2_client):
    assays = [add_assay(v2_client, f'验收煤{i+1}', i) for i in range(6)]
    response = v2_client.post('/api/optimization', json=request_for(assays))
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload['status'] == 'success', payload
    assert payload['history_saved'] is True
    assert payload['input_snapshot']['schema_version'] == 2
    assert payload['input_snapshot']['operator']['username'] == 'testadmin'
    for candidate in payload['result']['pareto_solutions']:
        ratios = candidate['optimal_ratios']
        assert sum(ratios) == pytest.approx(1)
        assert all(.05 - 1e-8 <= ratio <= .6 + 1e-8 for ratio in ratios)
        expected = dict(total_price=0., total_heat=0., total_ash=0., total_volatile=0., total_fixed_carbon=0., total_sulfur=0.)
        for i, ratio in enumerate(ratios):
            water, ash_d = 8 + i, 10 + i
            volatile_d = (9 + i if i < 3 else 32 + i) * (100 - ash_d) / 100
            dry_fraction = 1 - water / 100
            expected['total_ash'] += ratio * ash_d * dry_fraction
            expected['total_volatile'] += ratio * volatile_d * dry_fraction
            expected['total_fixed_carbon'] += ratio * (100 - ash_d - volatile_d) * dry_fraction
            expected['total_sulfur'] += ratio * (.5 + .03 * i) * dry_fraction
            expected['total_price'] += ratio * (950 - 50 * i)
            expected['total_heat'] += ratio * (29 - .4 * i) / .0041868
        for key, value in expected.items():
            assert candidate[key] == pytest.approx(value, abs=1e-5)


def test_same_coal_different_batches_work_but_same_batch_two_revisions_do_not(v2_client):
    first = add_assay(v2_client, '同煤种', 1)
    other = add_assay(v2_client, '同煤种', 2, coal_id=first['coal_id'], batch_code='B2')
    response = v2_client.post('/api/optimization', json=request_for([first, other]))
    assert response.status_code == 200, response.get_json()
    assert len(response.get_json()['result']['blending_ratio']) == 2
    revised = v2_client.post(f'/api/batches/{first["batch_id"]}/assays', json={'raw': raw_fixture(2)}).get_json()['data']
    response = v2_client.post('/api/optimization', json=request_for([first, revised]))
    assert response.status_code == 422
    assert response.get_json()['code'] == 'data_conflict'


def test_partial_record_cannot_bypass_server_eligibility(v2_client):
    first = add_assay(v2_client, '完整煤', 1)
    other = add_assay(v2_client, '部分煤', 2)
    partial = v2_client.post(f'/api/batches/{other["batch_id"]}/assays', json={'raw': {'ash_content': raw_fixture()['ash_content']}}).get_json()['data']
    response = v2_client.post('/api/optimization', json=request_for([first, partial]))
    assert response.status_code == 422
    assert response.get_json()['code'] == 'assay_not_eligible'
    assert response.get_json()['issues']
