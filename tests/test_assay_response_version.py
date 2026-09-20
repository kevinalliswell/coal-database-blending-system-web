from unittest.mock import Mock

import pytest

from test_catalog_api import client
from app.routes import catalog as routes


def test_assay_values_and_version_come_from_one_settings_snapshot(client, monkeypatch):
    coal = client.post('/api/catalog', json={'name': '版本测试', 'type': '烟煤'}).get_json()['data']
    batch = client.post(f'/api/catalog/{coal["id"]}/batches', json={'code': 'V1'}).get_json()['data']
    raw = {name: {'value': value, 'unit': '%', 'basis': 'd'} for name, value in
           {'ash_content': 10, 'volatile_matter': 20, 'fixed_carbon': 70, 'total_sulfur': .5}.items()}
    raw.update(total_moisture={'value': 8, 'unit': '%', 'basis': 'ar'},
               calorific_value={'value': 28, 'unit': 'MJ/kg', 'basis': 'ar', 'heat_type': 'net_v'},
               price={'value': 800, 'unit': 'CNY/t', 'basis': 'ar'})
    assert client.post(f'/api/batches/{batch["id"]}/assays', json={'raw': raw}).status_code == 201
    current = client.get('/api/settings').get_json()['data']
    current.update(version=77, ratio_basis='ar', heat_type='net_v')
    get_once = Mock(side_effect=[current, {**current, 'version': 78, 'ratio_basis': 'd'}])
    monkeypatch.setattr(routes, 'settings', get_once)
    response = client.get('/api/assays?page_size=0').get_json()
    assert response['settings_version'] == 77
    assert response['data'][0]['eligibility']['blending']['values']['ash_content'] == pytest.approx(9.2)
    get_once.assert_called_once()
