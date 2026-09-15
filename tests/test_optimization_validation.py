import pytest

from app import create_app
from app.config import Config
from app.extensions import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{tmp_path / "validation.db"}')
    app = create_app('production')
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
    with app.test_client() as client:
        client.get('/api/coals')
        yield client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def payload():
    return {'selected_coal_ids': [1, 6], 'constraints': {},
            'ga_params': {'population_size': 8, 'max_generations': 2}}


@pytest.mark.parametrize('ids', [[1, 1, 6], [1, '1'], [1.9, 6], [True, 6], [None, 6], '1,6', [0, 6], [-1, 6]])
def test_invalid_coal_identity_is_rejected_before_optimization(client, ids):
    request = payload()
    request['selected_coal_ids'] = ids
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'


@pytest.mark.parametrize('field,value', [
    ('constraints', None), ('constraints', []), ('ga_params', [1]),
    ('optimization_target', []), ('selected_coal_ids', {}),
])
def test_bad_request_shapes_return_client_error(client, field, value):
    request = payload()
    request[field] = value
    assert client.post('/api/optimization', json=request).status_code == 400


@pytest.mark.parametrize('bad', [None, [], 'nan', 'Infinity'])
def test_invalid_ratio_bounds_are_rejected(client, bad):
    request = payload()
    request['constraints']['ratio_constraints'] = {'1': {'min': bad, 'max': 80}}
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
    request['constraints']['ratio_constraints'] = {'1': {'min': 50, 'max': 50}, '6': {'min': 50, 'max': 50}}
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['is_feasible']
    assert result['optimal_ratios'] == pytest.approx([.5, .5])


def test_partial_ratio_bounds_use_defaults_for_other_selected_coals(client):
    request = payload()
    request['constraints']['ratio_constraints'] = {'1': {'min': 10, 'max': 40}}
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
    request['selected_coal_ids'] = ['01', '6']
    request['constraints']['ratio_constraints'] = {'1': {'min': '50', 'max': '50'}, '06': {'min': '50', 'max': '50'}}
    response = client.post('/api/optimization', json=request)
    assert response.status_code == 200
    assert response.get_json()['result']['optimal_ratios'] == pytest.approx([.5, .5])


def test_single_sided_nonfinite_quality_bound_is_rejected(client):
    request = payload()
    request['constraints']['sulfur_max'] = 'nan'
    assert client.post('/api/optimization', json=request).status_code == 400


def test_deprecated_heat_target_does_not_restrict_valid_heat_window():
    from backend.utils.optimization_validation import normalize_optimization_request
    request = payload()
    request['constraints'] = {'heat_target': 6800, 'heat_min': 7000, 'heat_max': 7500}
    assert normalize_optimization_request(request)['constraints']['heat_min'] == 7000
