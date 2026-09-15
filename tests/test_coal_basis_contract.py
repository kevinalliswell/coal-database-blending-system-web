import io

import pandas as pd
import pytest

from test_coal_data_integrity import client, coal_payload


def declared_coal(name='已声明基准煤', basis='d'):
    payload = coal_payload()
    payload.update(name=name, analysis_basis=basis, calorific_basis=basis,
                   calorific_type='gr', price_basis=basis, fixed_carbon=70)
    if basis == 'ad':
        payload.update(mad=2, fixed_carbon=68)
    elif basis == 'ar':
        payload.update(moisture=20, fixed_carbon=50)
    return payload


def optimize(client, ids, **changes):
    request = dict(selected_coal_ids=ids, ratio_basis='d',
                   ga_params={'population_size': 8, 'max_generations': 1, 'tournament_size': 2})
    request.update(changes)
    return client.post('/api/optimization', json=request)


def test_new_legacy_shaped_coal_is_stored_with_unknown_basis(client):
    result = client.post('/api/coals', json=coal_payload()).get_json()['data']
    for field in ('analysis_basis', 'calorific_basis', 'calorific_type', 'price_basis'):
        assert result[field] == 'unknown'
    assert result['fixed_carbon'] == 65


@pytest.mark.parametrize('basis', ['d', 'ad', 'ar'])
def test_explicit_basis_requires_its_own_moisture_closure(client, basis):
    payload = declared_coal(basis=basis)
    assert client.post('/api/coals', json=payload).status_code == 200
    payload.update(name='不闭合', fixed_carbon=payload['fixed_carbon'] - 2)
    response = client.post('/api/coals', json=payload)
    assert response.status_code == 400
    assert '闭合' in response.get_json()['message']


@pytest.mark.parametrize('basis,field', [('ad', 'mad'), ('ar', 'moisture')])
def test_declared_wet_basis_requires_relevant_water_measurement(client, basis, field):
    payload = declared_coal(basis=basis)
    payload.pop(field)
    assert client.post('/api/coals', json=payload).status_code == 400


@pytest.mark.parametrize('field', ['analysis_basis', 'calorific_basis', 'price_basis', 'calorific_type'])
def test_unsupported_basis_or_heat_definition_is_rejected(client, field):
    payload = declared_coal()
    payload[field] = 'daf'
    assert client.post('/api/coals', json=payload).status_code == 400


def test_basis_survives_edit_export_and_reimport(client):
    payload = declared_coal()
    coal = client.post('/api/coals', json=payload).get_json()['data']
    payload['calorific_type'] = 'net'
    assert client.put(f'/api/coals/{coal["id"]}', json=payload).get_json()['data']['calorific_type'] == 'net'
    exported = client.post('/api/coals/export', json={'export_all': True})
    frame = pd.read_excel(io.BytesIO(exported.data))
    assert frame['工业分析基准'].tolist() == ['d']
    assert frame['热值类型'].tolist() == ['net']
    imported = client.post('/api/coals/upload', data={'file': (io.BytesIO(exported.data), 'declared.xlsx')})
    assert imported.get_json()['updated_count'] == 1
    assert client.get(f'/api/coals/{coal["id"]}').get_json()['data']['price_basis'] == 'd'


def test_default_calculation_blocks_unknown_but_explicit_screening_warns(client):
    ids = []
    for name in ('未确认甲', '未确认乙'):
        payload = coal_payload()
        payload['name'] = name
        ids.append(client.post('/api/coals', json=payload).get_json()['coal_id'])
    assert optimize(client, ids).status_code == 400
    result = optimize(client, ids, calculation_mode='screening', ratio_basis='unknown')
    assert result.status_code == 200
    validation = result.get_json()['result']['data_validation']
    assert validation['status'] == 'unverified'
    assert validation['warnings']
    assert validation['ratio_basis'] == 'unknown'
    history = client.get('/api/optimization/history').get_json()['data']
    detail = client.get(f'/api/optimization/history/{history[0]["id"]}').get_json()['data']
    assert detail['result_payload']['result']['data_validation'] == validation


@pytest.mark.parametrize('basis', ['d', 'ad', 'ar'])
def test_matching_declared_basis_is_checked_and_returned(client, basis):
    ids = [client.post('/api/coals', json=declared_coal(name, basis)).get_json()['coal_id'] for name in ('甲', '乙')]
    result = optimize(client, ids, ratio_basis=basis)
    assert result.status_code == 200
    assert result.get_json()['result']['data_validation']['status'] == 'verified'
    assert result.get_json()['result']['data_validation']['ratio_basis'] == basis


@pytest.mark.parametrize('field,value', [('analysis_basis', 'ad'), ('calorific_basis', 'ar'),
                                        ('price_basis', 'ar'), ('calorific_type', 'net')])
def test_incompatible_declared_inputs_are_rejected_without_conversion(client, field, value):
    first = client.post('/api/coals', json=declared_coal('甲')).get_json()['coal_id']
    second = declared_coal('乙', 'ad' if field == 'analysis_basis' else 'd')
    second[field] = value
    second_id = client.post('/api/coals', json=second).get_json()['coal_id']
    result = optimize(client, [first, second_id])
    assert result.status_code == 400
    assert '基准' in result.get_json()['message'] or '热值类型' in result.get_json()['message']


@pytest.mark.parametrize('changes', [{'calculation_mode': 'auto'}, {'ratio_basis': 'daf'}, {'ratio_basis': None}])
def test_invalid_mode_or_ratio_basis_is_rejected(client, changes):
    ids = [client.post('/api/coals', json=declared_coal(name)).get_json()['coal_id'] for name in ('甲', '乙')]
    assert optimize(client, ids, **changes).status_code == 400
