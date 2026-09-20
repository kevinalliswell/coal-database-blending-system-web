"""V2 keeps incomplete raw reports and qualifies each calculation separately."""
from copy import deepcopy
import io

import pandas as pd
import pytest

from test_coal_data_integrity import client  # noqa: F401


def declared_raw(basis='d'):
    raw = {key: {'value': value, 'unit': '%', 'basis': basis} for key, value in
           [('ash_content', 10), ('volatile_matter', 20), ('fixed_carbon', 70), ('total_sulfur', .5)]}
    raw['price'] = {'value': 600, 'unit': 'CNY/t', 'basis': 'd'}
    raw['calorific_value'] = {'value': 6000, 'unit': 'kcal/kg', 'basis': basis, 'heat_type': 'net_v'}
    if basis == 'ad':
        raw['air_dry_moisture'] = {'value': 2, 'unit': '%', 'basis': 'ad'}
        raw['fixed_carbon']['value'] = 68
    elif basis == 'ar':
        raw['total_moisture'] = {'value': 20, 'unit': '%', 'basis': 'ar'}
        raw['fixed_carbon']['value'] = 50
    return raw


def use_dry_settings(client):
    settings = client.get('/api/settings').get_json()['data']
    if settings['ratio_basis'] != 'd':
        response = client.put('/api/settings', json={'version': settings['version'], 'ratio_basis': 'd',
            'constraints_confirmed': True, 'constraints': settings['constraints']})
        assert response.status_code == 200, response.get_json()
    return client.get('/api/settings').get_json()['data']


def add(client, name, raw):
    use_dry_settings(client)
    coal = client.post('/api/catalog', json={'name': name, 'type': '烟煤'}).get_json()['data']
    batch = client.post(f'/api/catalog/{coal["id"]}/batches', json={'code': 'B'}).get_json()['data']
    response = client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': raw})
    assert response.status_code == 201, response.get_json()
    return response.get_json()['data']


def optimize(client, ids, **changes):
    settings = client.get('/api/settings').get_json()['data']
    request = dict(components=[{'assay_revision_id': value, 'min_ratio': 0, 'max_ratio': 100} for value in ids],
                   settings_version=settings['version'], constraints={'heat_min': 1000, 'heat_max': 10000,
                       'fixed_carbon_min': 0, 'fixed_carbon_max': 100, 'ash_max': 100, 'volatile_min': 0, 'volatile_max': 100},
                   ga_params={'population_size': 8, 'max_generations': 1, 'tournament_size': 2})
    request.update(changes)
    return client.post('/api/optimization', json=request)


def test_new_partial_record_is_stored_with_unknown_basis(client):
    record = add(client, '未声明', {'fixed_carbon': {'value': 65}})
    assert record['raw']['fixed_carbon'] == {'value': 65, 'basis': 'unknown', 'unit': 'unknown'}
    assert not record['eligibility']['blending']['eligible']


@pytest.mark.parametrize('basis', ['d', 'ad', 'ar'])
def test_explicit_basis_checks_moisture_closure_for_calculation_not_storage(client, basis):
    raw = declared_raw(basis)
    record = add(client, '已闭合', raw)
    assert record['eligibility']['blending']['eligible']
    raw['fixed_carbon']['value'] -= 2
    response = client.post(f'/api/batches/{record["batch_id"]}/assays', json={'raw': raw})
    assert response.status_code == 201
    issues = response.get_json()['data']['eligibility']['blending']['issues']
    assert any('闭合' in issue['message'] for issue in issues)
    assert not response.get_json()['data']['eligibility']['blending']['eligible']


@pytest.mark.parametrize('basis,field', [('ad', 'air_dry_moisture'), ('ar', 'total_moisture')])
def test_declared_wet_basis_needs_water_for_calculation_but_can_be_saved(client, basis, field):
    raw = declared_raw(basis)
    raw.pop(field)
    record = add(client, '缺水分', raw)
    assert not record['eligibility']['blending']['eligible']
    assert any(issue['field'] == field for issue in record['eligibility']['blending']['issues'])


@pytest.mark.parametrize('metric,part', [('ash_content', 'basis'), ('calorific_value', 'basis'),
                                       ('price', 'basis'), ('calorific_value', 'heat_type')])
def test_unsupported_basis_or_heat_definition_is_rejected(client, metric, part):
    raw = declared_raw()
    raw[metric][part] = 'unsupported'
    assert client.post('/api/assays/preview', json={'raw': raw}).status_code == 400


def test_basis_survives_revision_export_and_reimport(client):
    record = add(client, '保留原始基准', declared_raw())
    raw = deepcopy(record['raw'])
    raw['calorific_value']['heat_type'] = 'net_p'
    updated = client.post(f'/api/batches/{record["batch_id"]}/assays', json={'raw': raw})
    assert updated.get_json()['data']['raw']['calorific_value']['heat_type'] == 'net_p'
    exported = client.get('/api/catalog/export')
    frame = pd.read_excel(io.BytesIO(exported.data))
    assert frame['ash_content.basis'].tolist() == ['d', 'd']
    assert frame['calorific_value.heat_type'].tolist() == ['net_v', 'net_p']
    preview = client.post('/api/catalog/import/preview', data={'file': (io.BytesIO(exported.data), 'declared.xlsx')}).get_json()['data']
    assert preview['can_commit']
    imported = client.post('/api/catalog/import/commit', json={'preview_token': preview['preview_token']})
    assert imported.get_json()['data']['created_revisions'] == 2
    results = client.get(f'/api/batches/{record["batch_id"]}/assays').get_json()['data']
    assert len(results) == 4
    assert results[0]['raw']['price']['basis'] == 'd'
    assert results[-1]['raw']['calorific_value']['heat_type'] == 'net_v'


def test_unknown_records_cannot_be_calculated_and_screening_bypass_is_removed(client):
    ids = [add(client, name, {'ash_content': {'value': 10}})['id'] for name in ('未确认甲', '未确认乙')]
    response = optimize(client, ids)
    assert response.status_code == 422
    assert response.get_json()['code'] == 'assay_not_eligible'
    assert response.get_json()['issues']
    assert optimize(client, ids, calculation_mode='screening').status_code == 400
    assert client.get('/api/optimization/history').get_json()['data'] == []


@pytest.mark.parametrize('basis', ['d', 'ad', 'ar'])
def test_matching_declared_basis_is_normalized_and_snapshotted(client, basis):
    records = [add(client, name, declared_raw(basis)) for name in ('甲', '乙')]
    result = optimize(client, [record['id'] for record in records])
    assert result.status_code == 200, result.get_json()
    assert result.get_json()['result']['data_validation']['status'] == 'verified'
    assert result.get_json()['result']['data_validation']['ratio_basis'] == 'd'
    assert result.get_json()['input_snapshot']['schema_version'] == 2
    assert records[0]['raw']['ash_content']['basis'] == basis


@pytest.mark.parametrize('metric,part,value', [('ash_content', 'basis', 'ad'), ('calorific_value', 'basis', 'ar'),
                                             ('price', 'basis', 'ar'), ('calorific_value', 'heat_type', 'gr_v')])
def test_conversion_dependencies_are_required_instead_of_assumed(client, metric, part, value):
    first = add(client, '甲', declared_raw())
    raw = declared_raw()
    raw[metric][part] = value
    second = add(client, '乙', raw)
    result = optimize(client, [first['id'], second['id']])
    assert result.status_code == 422
    assert result.get_json()['code'] == 'assay_not_eligible'
    assert result.get_json()['issues']


@pytest.mark.parametrize('changes', [{'calculation_mode': 'auto'}, {'ratio_basis': 'daf'}, {'ratio_basis': None}])
def test_per_request_removed_mode_or_ratio_basis_is_rejected(client, changes):
    ids = [add(client, name, declared_raw())['id'] for name in ('甲', '乙')]
    assert optimize(client, ids, **changes).status_code == 400
