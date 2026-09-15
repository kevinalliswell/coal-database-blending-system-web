"""Result provenance and printed constraints must match the submitted run."""
from io import BytesIO
import json

import pytest
from openpyxl import load_workbook

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Coal, OptimizationHistory


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{tmp_path / "snapshots.db"}')
    monkeypatch.setattr(Config, 'COAL_DATA_PATH', str(tmp_path / 'no-seed.csv'))
    app = create_app('production')
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        db.session.add_all([
            Coal(id=1, name='无烟煤A', type='无烟煤', price=900, calorific_value=7000,
                 ash_content=10, volatile_matter=10, fixed_carbon=78, total_sulfur=0.6,
                 total_moisture=8, air_dry_moisture=2, hgi=60,
                 analysis_basis='ad', calorific_basis='ad', price_basis='ad', calorific_type='net'),
            Coal(id=2, name='烟煤B', type='烟煤', price=600, calorific_value=6200,
                 ash_content=8, volatile_matter=30, fixed_carbon=60, total_sulfur=0.4,
                 total_moisture=18, air_dry_moisture=2, hgi=55,
                 analysis_basis='ad', calorific_basis='ad', price_basis='ad', calorific_type='net'),
        ])
        db.session.commit()
    yield app.test_client()
    with app.app_context():
        db.session.remove()


def solve(client, calculation_mode='verified', ratio_basis='ad'):
    response = client.post('/api/optimization', json={
        'calculation_mode': calculation_mode,
        'ratio_basis': ratio_basis,
        'selected_coal_ids': [1, 2],
        'constraints': {'heat_min': 6000, 'heat_max': 7200, 'heat_target': 6800,
                        'sulfur_min': 0, 'sulfur_max': 0.7},
        'ga_params': {'population_size': 12, 'max_generations': 2,
                      'tournament_size': 2, 'parallel_computing': False, 'parallel_workers': 9},
    })
    assert response.status_code == 200
    result = response.get_json()
    assert result['status'] == 'success'
    return result


def performance_row(response, label):
    assert response.status_code == 200
    ws = load_workbook(BytesIO(response.data)).active
    return next([cell.value for cell in row] for row in ws.iter_rows()
                if row[0].value == label and row[3].value is not None)


def test_response_and_history_preserve_coal_properties_and_effective_configuration(client):
    payload = solve(client)
    snapshot = payload['input_snapshot']
    assert snapshot['schema_version'] == 1
    assert snapshot['calculation_mode'] == 'verified'
    assert snapshot['ratio_basis'] == 'ad'
    assert snapshot['data_validation'] == payload['result']['data_validation']
    assert snapshot['data_validation']['status'] == 'verified'
    assert snapshot['coals'][0]['price'] == 900
    assert snapshot['coals'][0]['total_moisture'] == 8
    assert snapshot['coals'][0]['analysis_basis'] == 'ad'
    assert snapshot['coals'][0]['calorific_type'] == 'net'
    assert snapshot['algorithm_coals'][0]['price'] == 900
    assert snapshot['ga_config']['parallel_workers'] == 1
    assert snapshot['ga_config']['population_size'] == 12
    assert snapshot['constraints']['ash_max'] == 20
    assert payload['constraints'] == snapshot['constraints']

    with client.application.app_context():
        db.session.get(Coal, 1).price = 1234
        db.session.commit()
    history = client.get('/api/optimization/history').get_json()['data'][0]
    detail = client.get(f'/api/optimization/history/{history["id"]}').get_json()['data']
    assert detail['result_payload']['input_snapshot'] == snapshot
    assert detail['constraints'] == snapshot['constraints']


def test_screening_snapshot_preserves_explicit_mode_and_validation_for_replay(client):
    payload = solve(client, calculation_mode='screening')
    snapshot = payload['input_snapshot']
    assert snapshot['calculation_mode'] == 'screening'
    assert snapshot['ratio_basis'] == 'ad'
    assert snapshot['data_validation'] == payload['result']['data_validation']
    assert snapshot['data_validation']['status'] == 'unverified'
    assert snapshot['data_validation']['scope'] == 'screening_only'
    history = client.get('/api/optimization/history').get_json()['data'][0]
    detail = client.get(f'/api/optimization/history/{history["id"]}').get_json()['data']
    assert detail['result_payload']['input_snapshot'] == snapshot
    assert detail['request_payload']['calculation_mode'] == 'screening'


def test_current_export_uses_constraints_from_the_completed_response(client):
    payload = solve(client)
    row = performance_row(client.post('/api/optimization/export/current', json=payload), '综合热值')
    assert [float(bound) for bound in row[3].split(' ~ ')] == [6000, 7200]
    assert row[4] == '达标'


def test_report_prefers_completed_snapshot_over_later_edited_constraints(client):
    payload = solve(client)
    payload['constraints'] = {'heat_min': 6000, 'heat_max': 6100}
    row = performance_row(client.post('/api/optimization/export/current', json=payload), '综合热值')
    assert [float(bound) for bound in row[3].split(' ~ ')] == [6000, 7200]
    assert row[4] == '达标'


def test_report_marks_a_missing_window_unchecked(client):
    payload = solve(client)
    payload.pop('constraints', None)
    payload.pop('input_snapshot', None)
    row = performance_row(client.post('/api/optimization/export/current', json=payload), '综合热值')
    assert row[3] == '--'
    assert row[4] == '未校验'


def test_historical_export_keeps_legacy_constraints_without_new_snapshot(client):
    payload = solve(client)
    payload.pop('constraints', None)
    payload.pop('input_snapshot', None)
    with client.application.app_context():
        history = OptimizationHistory.query.first()
        history.result_payload = json.dumps(payload)
        history.constraints = json.dumps({'heat_min': 6100, 'heat_max': 7100})
        db.session.commit()
        history_id = history.id
    row = performance_row(client.get(f'/api/optimization/export/{history_id}'), '综合热值')
    assert row[3] == '6100 ~ 7100'
