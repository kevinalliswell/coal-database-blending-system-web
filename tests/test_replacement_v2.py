"""Versioned assay input, explicit process data and historical reproduction."""
import copy

import pytest

from app import create_app
from app.extensions import db
from app.models.catalog import AssayRevision, CoalBatch
from app.models.coal import Coal
from app.models.replacement_ratio_history import ReplacementRatioHistory
from app.routes.access import init_access
from app.services.access_service import create_initial_admin, create_user
from test_assay_conversion import assay


@pytest.fixture
def replacement_client(tmp_path):
    app = create_app('production', config_overrides={
        'TESTING': True, 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "replacement.db"}',
        'DATA_DIR': str(tmp_path), 'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'COAL_DATA_PATH': str(tmp_path / 'absent.csv'), 'AUTO_INITIALIZE_COAL_DATA': False,
        'SESSION_COOKIE_SECURE': False,
    })
    init_access(app)
    with app.app_context():
        db.create_all()
        create_initial_admin('replacement_admin', 'ReplacementPassword123!')
        coal = Coal(name='无烟煤批次测试', type='无烟煤')
        batch = CoalBatch(coal=coal, code='2026-09-A')
        record = AssayRevision(batch=batch, revision=1, raw=assay())
        db.session.add(record)
        db.session.commit()
        assay_id = record.id
    client = app.test_client()
    csrf = client.get('/api/auth/session').get_json()['csrf_token']
    response = client.post('/api/auth/login', json={'username': 'replacement_admin', 'password': 'ReplacementPassword123!'},
                           headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200, response.get_json()
    headers = {'X-CSRF-Token': response.get_json()['csrf_token']}
    yield app, client, headers, assay_id
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def theory_payload(assay_id):
    return {'assay_revision_id': assay_id, 'settings_version': 1,
            'coal_params': {'decomposition_heat': 921.096, 'physical_heat': 1884.06, 'heat_unit': 'kJ/kg'},
            'coke_params': {'analysis_basis': 'd', 'carbon_content': .86, 'ash_content': .11, 'sio2_content': .52},
            'blast_furnace_params': {'eta_co': .4444, 'slag_basicity': 1.15, 'slag_enthalpy': 1800,
                                     'hot_blast_enthalpy': 1534},
            'parameter_source': '厂内焦炭化验及炉况记录'}


def actual_payload():
    return {'settings_version': 1, 'mass_basis': 'd', 'furnace_id': 'BF-1',
            'period_before': '2026-09-01/2026-09-07', 'period_after': '2026-09-08/2026-09-14',
            'correction_mode': 'none', 'production_data': {
                'initial_coke_ratio': 400, 'final_coke_ratio': 370,
                'initial_coal_ratio': 150, 'final_coal_ratio': 180}}


def post(fixture, kind, payload):
    _, client, headers, _ = fixture
    return client.post(f'/api/calculate_{kind}_ratio', json=payload, headers=headers)


def test_theory_uses_immutable_assay_and_persists_raw_normalized_settings_actor(replacement_client):
    _, client, _, assay_id = replacement_client
    response = post(replacement_client, 'theory', theory_payload(assay_id))
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    snapshot = result['input_snapshot']
    assert snapshot['schema_version'] == 2
    assert snapshot['assay']['id'] == assay_id
    assert snapshot['raw']['carbon_content']['value'] == 78
    assert snapshot['normalized']['coal_params']['carbon_content'] == .78
    assert snapshot['normalized']['coal_params']['hydrogen_content'] == .04
    assert snapshot['settings']['ratio_basis'] == 'ar'
    assert snapshot['actor']['username'] == 'replacement_admin'
    assert result['hot_blast_enthalpy_source'] == 'provided'
    assert result['total_heat_consumption'] == pytest.approx(2805.156)
    assert result['heat_consumption_unit'] == 'kJ/kg'
    history = client.get('/api/replacement_ratio/history').get_json()['data'][0]
    saved = client.get(f'/api/replacement_ratio/history/{history["id"]}').get_json()['data']
    assert saved['result_payload']['input_snapshot'] == snapshot
    assert saved['request_payload'] == theory_payload(assay_id)


@pytest.mark.parametrize('path', [
    ('assay_revision_id',), ('coal_params', 'decomposition_heat'),
    ('coal_params', 'physical_heat'), ('coal_params', 'heat_unit'), ('coke_params', 'sio2_content'),
    ('coke_params', 'analysis_basis'), ('blast_furnace_params', 'eta_co'),
    ('blast_furnace_params', 'hot_blast_enthalpy'),
])
def test_missing_theory_fields_never_use_example_defaults(replacement_client, path):
    payload = theory_payload(replacement_client[3])
    parent = payload if len(path) == 1 else payload[path[0]]
    parent.pop(path[-1])
    response = post(replacement_client, 'theory', payload)
    assert response.status_code == 400, response.get_json()
    with replacement_client[0].app_context():
        assert ReplacementRatioHistory.query.count() == 0


def test_hot_blast_estimate_needs_explicit_opt_in_and_is_saved(replacement_client):
    payload = theory_payload(replacement_client[3])
    payload['blast_furnace_params'].pop('hot_blast_enthalpy')
    payload['blast_furnace_params']['wind_temperature'] = 1180
    assert post(replacement_client, 'theory', payload).status_code == 400
    payload['allow_hot_blast_estimate'] = True
    response = post(replacement_client, 'theory', payload)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['effective_hot_blast_enthalpy'] == pytest.approx(1534)
    assert result['hot_blast_enthalpy_source'] == 'temperature_estimate'
    assert result['input_snapshot']['request']['allow_hot_blast_estimate'] is True


def test_coal_composition_cannot_override_assay_snapshot(replacement_client):
    payload = theory_payload(replacement_client[3])
    payload['coal_params']['carbon_content'] = .99
    assert post(replacement_client, 'theory', payload).status_code == 400


@pytest.mark.parametrize('which', ['settings', 'archived', 'missing_revision', 'partial_revision'])
def test_stale_or_ineligible_theory_inputs_are_rejected(replacement_client, which):
    app, _, _, assay_id = replacement_client
    payload = theory_payload(assay_id)
    if which == 'settings':
        payload['settings_version'] = 0
    elif which == 'missing_revision':
        payload['assay_revision_id'] = 999
    else:
        with app.app_context():
            existing = db.session.get(AssayRevision, assay_id)
            if which == 'archived':
                existing.batch.archived = True
            else:
                partial = AssayRevision(batch=existing.batch, revision=2, raw={})
                db.session.add(partial)
                db.session.flush()
                payload['assay_revision_id'] = partial.id
            db.session.commit()
    assert post(replacement_client, 'theory', payload).status_code in (400, 404, 409)


def test_actual_basic_uses_observed_changes_without_implicit_correction(replacement_client):
    response = post(replacement_client, 'actual', actual_payload())
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    assert result['ratio'] == pytest.approx(1)
    assert result['correction_mode'] == 'none'
    assert result['input_snapshot']['normalized']['production_data']['adjustment_factor'] == 0
    assert result['input_snapshot']['request']['mass_basis'] == 'd'


@pytest.mark.parametrize('field', ['initial_coke_ratio', 'final_coke_ratio', 'initial_coal_ratio', 'final_coal_ratio'])
def test_missing_actual_observation_never_uses_example(replacement_client, field):
    payload = actual_payload()
    payload['production_data'].pop(field)
    assert post(replacement_client, 'actual', payload).status_code == 400


def test_actual_correction_requires_explicit_value_and_source(replacement_client):
    payload = actual_payload()
    payload['correction_mode'] = 'provided'
    assert post(replacement_client, 'actual', payload).status_code == 400
    payload['production_data']['adjustment_factor'] = 3
    assert post(replacement_client, 'actual', payload).status_code == 400
    payload['correction_source'] = '厂内修正记录2026-09-20'
    response = post(replacement_client, 'actual', payload)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['ratio'] == pytest.approx(1.1)


@pytest.mark.parametrize('change', [
    {'enable_advanced': True}, {'mass_basis': 'unknown'}, {'period_after': '2026-09-01/2026-09-07'},
])
def test_actual_rejects_ambiguous_or_uncalibrated_modes(replacement_client, change):
    payload = actual_payload()
    payload.update(change)
    assert post(replacement_client, 'actual', payload).status_code == 400


@pytest.mark.parametrize('invalid', [None, True, '400', float('nan'), -1])
def test_actual_numbers_are_explicit_finite_nonnegative(replacement_client, invalid):
    payload = actual_payload()
    payload['production_data']['initial_coke_ratio'] = invalid
    assert post(replacement_client, 'actual', payload).status_code == 400


def test_zero_coal_change_returns_client_error_not_server_error(replacement_client):
    payload = actual_payload()
    payload['production_data']['final_coal_ratio'] = 150
    assert post(replacement_client, 'actual', payload).status_code == 400


def test_viewer_cannot_bypass_ui_permission(replacement_client):
    app, client, headers, _ = replacement_client
    with app.app_context():
        create_user({'username': 'viewer', 'password': 'ReplacementPassword123!', 'role': 'viewer'})
    login = client.post('/api/auth/login', json={'username': 'viewer', 'password': 'ReplacementPassword123!'}, headers=headers)
    headers = {'X-CSRF-Token': login.get_json()['csrf_token']}
    assert client.post('/api/calculate_actual_ratio', json=actual_payload(), headers=headers).status_code == 403
