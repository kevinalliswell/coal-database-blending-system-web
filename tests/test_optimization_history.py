import csv

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db
from app.models import OptimizationHistory, ReplacementRatioHistory


CSV_HEADERS = [
    '序号',
    '煤种名称',
    '煤种类型',
    '供应商/产地',
    '价格(元/吨)',
    '热值(kcal/kg)',
    '灰分(%)',
    '挥发分(%)',
    '水分（%）',
    '固定碳(%)',
    '全硫(%)',
    '全水分(%)',
    '可磨性HGI',
    '燃尽率(%)',
    '含碳量C(%)',
    '含氢量H(%)',
    '含氮量N(%)',
    '空干基水分%)',
]

CSV_ROWS = [
    [1, '经济煤', '烟煤', '测试', 500.0, 6000.0, 10.0, 20.0, 2.5, 65.0, 0.5, 8.0, 60.0, 100.0, 70.0, 4.0, 1.0, 1.0],
    [2, '高热值煤', '烟煤', '测试', 700.0, 6400.0, 9.0, 19.0, 2.5, 68.0, 0.4, 8.0, 60.0, 100.0, 71.0, 4.1, 1.1, 1.0],
    [3, '高硫低价煤', '烟煤', '测试', 450.0, 6100.0, 10.5, 21.0, 2.5, 64.0, 1.1, 8.0, 60.0, 100.0, 69.0, 4.2, 1.2, 1.0],
]


@pytest.fixture
def app_client(tmp_path):
    db_path = tmp_path / 'test_history.db'
    csv_path = tmp_path / 'test_coals.csv'

    with csv_path.open('w', encoding='utf-8', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADERS)
        writer.writerows(CSV_ROWS)

    app = create_app(config_overrides={
        'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f"sqlite:///{db_path.as_posix()}",
        'COAL_DATA_PATH': str(csv_path), 'DATA_DIR': str(tmp_path),
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
    })

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app, app.test_client()

    with app.app_context():
        db.session.remove()
        db.drop_all()


def build_optimization_payload():
    return {
        'optimization_target': '喷煤性价比最优',
        # Legacy-shaped fixtures intentionally exercise screening history, not assay certification.
        'calculation_mode': 'screening',
        'ratio_basis': 'unknown',
        'selected_coal_ids': [1, 2, 3],
        'constraints': {
            'heat_target': 6100,
            'heat_min': 5900,
            'heat_max': 6200,
            'ash_min': 8.0,
            'ash_max': 12.0,
            'volatile_min': 18.0,
            'volatile_max': 28.0,
            'fixed_carbon_min': 60.0,
            'fixed_carbon_max': 72.0,
            'sulfur_min': 0.4,
            'sulfur_max': 0.8,
            'price_min': 400.0,
            'price_max': 800.0,
            'ratio_constraints': {
                '1': {'min': 0, 'max': 100},
                '2': {'min': 0, 'max': 100},
                '3': {'min': 0, 'max': 100},
            },
        },
        'ga_params': {
            'population_size': 40,
            'max_generations': 80,
            'mutation_rate': 0.15,
            'crossover_rate': 0.85,
            'tournament_size': 4,
            'elite_ratio': 0.1,
            'early_stopping_patience': 20,
            'constraint_penalty_factor': 1000,
            'parallel_workers': 1,
            'parallel_computing': False,
            'adaptive_mutation': False,
            'diversity_factor': 0.05,
        },
    }


def build_theory_payload():
    return {
        'coal_params': {
            'carbon_content': 0.78,
            'hydrogen_content': 0.035,
            'ash_content': 0.12,
            'sio2_content': 0.48,
            'decomposition_heat': 220.0,
            'physical_heat': 450.0,
        },
        'coke_params': {
            'carbon_content': 0.86,
            'ash_content': 0.11,
            'sio2_content': 0.52,
        },
        'blast_furnace_params': {
            'eta_co': 0.4444,
            'slag_basicity': 1.15,
            'slag_enthalpy': 1800.0,
            'wind_temperature': 1180.0,
            'hot_blast_enthalpy': 1.5,
        },
    }


def build_actual_payload(enable_advanced=False):
    return {
        'production_data': {
            'initial_coke_ratio': 400.0,
            'final_coke_ratio': 370.0,
            'initial_coal_ratio': 150.0,
            'final_coal_ratio': 180.0,
            'adjustment_factor': 2.5,
            'iron_output_change': 50.0,
            'slag_ratio_change': -10.0,
            'carbon_efficiency_change': 2.0,
        },
        'enable_advanced': enable_advanced,
    }


def test_optimization_history_is_persisted_and_queryable(app_client):
    app, client = app_client

    response = client.post('/api/optimization', json=build_optimization_payload())
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['status'] == 'success'

    with app.app_context():
        assert OptimizationHistory.query.count() == 1

    history_response = client.get('/api/optimization/history')
    history_payload = history_response.get_json()

    assert history_response.status_code == 200
    assert history_payload['status'] == 'success'
    assert len(history_payload['data']) == 1
    assert history_payload['data'][0]['coal_names'] == ['经济煤', '高热值煤', '高硫低价煤']

    detail_id = history_payload['data'][0]['id']
    detail_response = client.get(f'/api/optimization/history/{detail_id}')
    detail_payload = detail_response.get_json()

    assert detail_response.status_code == 200
    assert detail_payload['status'] == 'success'
    assert detail_payload['data']['request_payload']['selected_coal_ids'] == [1, 2, 3]
    assert detail_payload['data']['result_payload']['status'] == 'success'


def test_optimization_result_is_returned_when_history_save_fails(app_client, monkeypatch):
    from backend.routes import optimization as optimization_routes

    _, client = app_client

    def fail_history_save(*_args, **_kwargs):
        raise SQLAlchemyError('missing optimization_history table')

    monkeypatch.setattr(optimization_routes, '_save_optimization_history', fail_history_save)

    response = client.post('/api/optimization', json=build_optimization_payload())
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['status'] == 'success'
    assert payload['history_saved'] is False
    assert '历史记录保存失败' in payload['warning']
    assert payload['result']['is_feasible'] is True


def test_replacement_ratio_theory_history_is_persisted_and_queryable(app_client):
    app, client = app_client

    response = client.post('/api/calculate_theory_ratio', json=build_theory_payload())
    payload = response.get_json()

    assert response.status_code == 200
    assert payload['status'] == 'success'

    with app.app_context():
        assert ReplacementRatioHistory.query.count() == 1

    history_response = client.get('/api/replacement_ratio/history')
    history_payload = history_response.get_json()

    assert history_response.status_code == 200
    assert history_payload['status'] == 'success'
    assert len(history_payload['data']) == 1
    assert history_payload['data'][0]['calculation_type'] == 'theory'
    assert history_payload['data'][0]['calculation_mode'] == 'theory'

    detail_id = history_payload['data'][0]['id']
    detail_response = client.get(f'/api/replacement_ratio/history/{detail_id}')
    detail_payload = detail_response.get_json()

    assert detail_response.status_code == 200
    assert detail_payload['data']['request_payload']['coal_params']['carbon_content'] == 0.78
    assert detail_payload['data']['result_payload']['status'] == 'success'


def test_replacement_ratio_actual_history_tracks_basic_and_advanced_modes(app_client):
    app, client = app_client

    basic_response = client.post('/api/calculate_actual_ratio', json=build_actual_payload(enable_advanced=False))
    advanced_response = client.post('/api/calculate_actual_ratio', json=build_actual_payload(enable_advanced=True))

    assert basic_response.status_code == 200
    assert advanced_response.status_code == 200
    assert basic_response.get_json()['status'] == 'success'
    assert advanced_response.get_json()['status'] == 'success'

    with app.app_context():
        assert ReplacementRatioHistory.query.count() == 2

    history_response = client.get('/api/replacement_ratio/history')
    history_payload = history_response.get_json()

    assert len(history_payload['data']) == 2
    assert {item['calculation_mode'] for item in history_payload['data']} == {'basic', 'advanced'}
    assert all(item['calculation_type'] == 'actual' for item in history_payload['data'])


def test_history_pages_are_available(app_client):
    _, client = app_client

    blending_page = client.get('/optimization_history/blending')
    replacement_ratio_page = client.get('/optimization_history/replacement_ratio')

    assert blending_page.status_code == 200
    assert replacement_ratio_page.status_code == 200
