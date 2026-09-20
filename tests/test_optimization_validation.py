import pytest

from app import create_app
from app.config import Config
from app.extensions import db


from test_v2_optimization import v2_client, add_assay, request_for


@pytest.fixture
def client(v2_client):
    add_assay(v2_client, '验证煤1', 0)
    add_assay(v2_client, '验证煤2', 3)
    return v2_client


def payload():
    return request_for([{'id': 1}, {'id': 2}])


@pytest.mark.parametrize('ids', [[1, 1, 6], [1, '1'], [1.9, 6], [True, 6], [None, 6], '1,6', [0, 6], [-1, 6]])
def test_invalid_coal_identity_is_rejected_before_optimization(client, ids):
    request = payload()
    request['components'] = [{'assay_revision_id': value, 'min_ratio': 0, 'max_ratio': 100} for value in ids] if isinstance(ids, list) else ids
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'


@pytest.mark.parametrize('field,value', [
    ('constraints', None), ('constraints', []), ('ga_params', [1]),
    ('optimization_target', []), ('components', {}),
])
def test_bad_request_shapes_return_client_error(client, field, value):
    request = payload()
    request[field] = value
    assert client.post('/api/optimization', json=request).status_code == 400


@pytest.mark.parametrize('bad', [None, [], 'nan', 'Infinity'])
def test_invalid_ratio_bounds_are_rejected(client, bad):
    request = payload()
    request['components'][0]['min_ratio'] = bad
    assert client.post('/api/optimization', json=request).status_code == 400


@pytest.mark.parametrize('config', [{'population_size': 2.5}, {'population_size': 'nan'},
                                  {'max_generations': float('inf')}, {'mutation_rate': 'nan'},
                                  {'parallel_workers': True}, {'adaptive_mutation': []}])
def test_invalid_optimizer_values_are_rejected(client, config):
    request = payload()
    request['ga_params'].update(config)
    assert client.post('/api/optimization', json=request).status_code == 400


def test_non_object_and_malformed_json_return_client_error(client):
    assert client.post('/api/optimization', json=[1, 6]).status_code == 400
    assert client.post('/api/optimization', data='{', content_type='application/json').status_code == 400


def test_fixed_ratio_is_supported(client):
    request = payload()
    request['components'] = [{'assay_revision_id': i, 'min_ratio': 50, 'max_ratio': 50} for i in (1, 2)]
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['is_feasible']
    assert result['optimal_ratios'] == pytest.approx([.5, .5])


def test_independent_ratio_bounds_are_applied_to_selected_batches(client):
    request = payload()
    request['components'][0].update(min_ratio=10, max_ratio=40)
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['is_feasible']
    assert .1 <= result['optimal_ratios'][0] <= .4
    assert sum(result['optimal_ratios']) == pytest.approx(1)


def test_unselected_ratio_keys_are_rejected(client):
    request = payload()
    request['constraints']['ratio_constraints'] = {'999': {'min': 0, 'max': 100}}
    assert client.post('/api/optimization', json=request).status_code == 400


def test_numeric_strings_are_normalized_consistently(client):
    request = payload()
    request['components'] = [{'assay_revision_id': i, 'min_ratio': '50', 'max_ratio': '50'} for i in ('01', '02')]
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 200
    assert response.get_json()['result']['optimal_ratios'] == pytest.approx([.5, .5])


def test_single_sided_nonfinite_quality_bound_is_rejected(client):
    request = payload()
    request['constraints']['sulfur_max'] = 'nan'
    assert client.post('/api/optimization', json=request).status_code == 400


def test_deprecated_heat_target_does_not_restrict_valid_heat_window():
    from backend.utils.optimization_validation import normalize_assay_request
    request = payload()
    request['constraints'] = {'heat_target': 6800, 'heat_min': 7000, 'heat_max': 7500}
    assert normalize_assay_request(request, {'version': 1, 'constraints': {}, 'ga_params': {}})['constraints']['heat_min'] == 7000
