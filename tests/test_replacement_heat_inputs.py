from dataclasses import replace

import pytest

from app import create_app
from app.config import Config
from app.extensions import db
from backend.service.replacement_ratio_service import (
    BlastFurnaceParameters, CoalParameters, CokeParameters, ReplacementRatioCalculator,
)


def calculator(enthalpy=None, temperature=1180):
    return ReplacementRatioCalculator(
        CoalParameters(.78, .035, .12, .48, 220, 450),
        CokeParameters(.86, .11, .52),
        BlastFurnaceParameters(.4444, 1.15, 1800, wind_temperature=temperature,
                               hot_blast_enthalpy=enthalpy),
    )


def test_measured_enthalpy_overrides_temperature_estimate():
    low, high = calculator(1000), calculator(2000)
    assert high.calculate_carbon_burning_heat() - low.calculate_carbon_burning_heat() == pytest.approx(1200)
    assert high.calculate_displacement_ratio()[0] != pytest.approx(low.calculate_displacement_ratio()[0])
    assert calculator(2000, 500).calculate_carbon_burning_heat() == high.calculate_carbon_burning_heat()


def test_omitted_enthalpy_keeps_temperature_estimate_and_mass_energy_balance():
    calc = calculator()
    heat = 1.2 * 1.3 * 1180 + 9794 - 2758
    assert calc.calculate_carbon_burning_heat() == pytest.approx(heat)
    assert calc.calculate_carbon_consumed_by_decomposition() * heat == pytest.approx((220 + 450) * 4.184)
    calc.blast_furnace = replace(calc.blast_furnace, wind_temperature=1280)
    assert calc.calculate_carbon_burning_heat() == pytest.approx(heat + 156)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{tmp_path / "heat.db"}')
    app = create_app('production')
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
    yield app.test_client()
    with app.app_context():
        db.session.remove()
        db.drop_all()


def request_payload():
    return {'coal_params': {'carbon_content': .78, 'hydrogen_content': .035, 'ash_content': .12,
                            'decomposition_heat': 220, 'physical_heat': 450},
            'coke_params': {'carbon_content': .86, 'ash_content': .11},
            'blast_furnace_params': {'hot_blast_enthalpy': 1534}}


def test_api_reports_separate_heat_terms_and_effective_enthalpy(client):
    response = client.post('/api/calculate_theory_ratio', json=request_payload())
    assert response.status_code == 200
    result = response.get_json()
    assert result['decomposition_heat_consumption'] == 220
    assert result['physical_heat_consumption'] == 450
    assert result['total_heat_consumption'] == 670
    assert result['carbon_burning_heat'] == pytest.approx(1.2 * 1534 + 9794 - 2758)
    assert result['hot_blast_enthalpy_source'] == 'provided'
    assert result['effective_hot_blast_enthalpy'] == 1534


@pytest.mark.parametrize('value', [None, 'omit'])
def test_api_missing_enthalpy_uses_estimate(client, value):
    request = request_payload()
    if value == 'omit':
        del request['blast_furnace_params']['hot_blast_enthalpy']
    else:
        request['blast_furnace_params']['hot_blast_enthalpy'] = value
    result = client.post('/api/calculate_theory_ratio', json=request).get_json()
    assert result['effective_hot_blast_enthalpy'] == pytest.approx(1534)
    assert result['hot_blast_enthalpy_source'] == 'temperature_estimate'


@pytest.mark.parametrize('field,value', [('hot_blast_enthalpy', 'nan'), ('hot_blast_enthalpy', float('inf')),
                                        ('hot_blast_enthalpy', -1), ('hot_blast_enthalpy', True),
                                        ('hot_blast_enthalpy', []), ('wind_temperature', 'nan')])
def test_invalid_heat_inputs_return_400(client, field, value):
    request = request_payload()
    request['blast_furnace_params'][field] = value
    assert client.post('/api/calculate_theory_ratio', json=request).status_code == 400


@pytest.mark.parametrize('payload', [[], {'coal_params': None}, {'coal_params': [], 'coke_params': {}}])
def test_invalid_theory_shapes_return_400(client, payload):
    assert client.post('/api/calculate_theory_ratio', json=payload).status_code == 400


def test_nonpositive_effective_coke_carbon_is_rejected(client):
    payload = request_payload()
    payload['coke_params'] = {'carbon_content': .01, 'ash_content': .99, 'sio2_content': .52}
    assert client.post('/api/calculate_theory_ratio', json=payload).status_code == 400
