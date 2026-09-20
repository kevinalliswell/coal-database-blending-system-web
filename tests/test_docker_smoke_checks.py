"""The release smoke must fail on incomplete evidence, not merely return 200."""
import importlib.util
from http.client import RemoteDisconnected
import io
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

spec = importlib.util.spec_from_file_location('docker_smoke', Path(__file__).parents[1] / 'scripts' / 'smoke-docker.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def candidate(count=6):
    ratios = [1/count] * count
    result = {'optimal_ratios': ratios}
    values = dict(total_price=0., total_heat=0., total_ash=0., total_volatile=0., total_fixed_carbon=0., total_sulfur=0.)
    for i, ratio in enumerate(ratios):
        dry, ash = 1 - (8+i)/100, 10+i
        volatile = (9+i if i < 3 else 32+i) * (100-ash)/100
        for field, value in dict(total_price=950-50*i, total_heat=(29-.4*i)/.0041868,
                                total_ash=ash*dry, total_volatile=volatile*dry,
                                total_fixed_carbon=(100-ash-volatile)*dry, total_sulfur=(.5+.03*i)*dry).items():
            values[field] += ratio * value
    return {**result, **values}


def payload(front):
    return {'status': 'success', 'history_saved': True, 'input_snapshot': {'schema_version': 2},
            'result': {'pareto_solutions': front, 'recommended_solution': front[0] if front else {}}}


def test_empty_pareto_front_is_not_a_six_coal_validation():
    with pytest.raises(AssertionError):
        smoke.verify_blend(payload([]))


def test_five_coal_vector_cannot_be_reported_as_six_coal_validation():
    with pytest.raises(AssertionError):
        smoke.verify_blend(payload([candidate(5)]))


def test_bad_recommendation_is_checked_even_when_display_front_is_correct():
    result = payload([candidate()])
    result['result']['recommended_solution'] = {**candidate(), 'total_price': 0}
    with pytest.raises(AssertionError):
        smoke.verify_blend(result)


def test_six_coal_balances_pass():
    smoke.verify_blend(payload([candidate()]))


def test_equal_unknown_builds_do_not_prove_expected_commit():
    with pytest.raises(AssertionError):
        smoke.verify_system({'version': '2.0.0', 'build_commit': 'unknown', 'mode': 'web'}, 'a'*40, '2.0.0')
    with pytest.raises(AssertionError):
        smoke.verify_system({'version': '1.1.1', 'build_commit': 'a'*40, 'mode': 'web'}, 'a'*40, '2.0.0')


@pytest.mark.parametrize('failure', [ConnectionResetError('starting'), RemoteDisconnected('starting'),
                                  TimeoutError('starting'), URLError('not listening')])
def test_readiness_retries_transient_transport_errors_only(monkeypatch, failure):
    request = Mock(side_effect=[failure, {'status': 'ok'}])
    monkeypatch.setattr(smoke.API, 'call', request)
    monkeypatch.setattr(smoke.time, 'sleep', lambda _: None)
    smoke.wait_ready('http://localhost')
    assert request.call_count == 2


@pytest.mark.parametrize('http_status,body', [(503, b'{"status":"ok"}'), (200, b'{"status":"error"}')])
def test_readiness_rejects_failed_response_before_success(monkeypatch, http_status, body):
    responses = [HTTPError('http://localhost/health', http_status, 'starting', {}, io.BytesIO(body)),
                 HTTPError('http://localhost/health', 200, 'OK', {}, io.BytesIO(b'{"status":"ok"}'))]
    opened = Mock(side_effect=responses)
    monkeypatch.setattr(smoke, 'build_opener', lambda *_: type('Opener', (), {'open': opened})())
    monkeypatch.setattr(smoke.time, 'sleep', lambda _: None)
    smoke.wait_ready('http://localhost')
    assert opened.call_count == 2


def test_readiness_has_a_deadline_and_preserves_last_error(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(smoke.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(smoke.time, 'sleep', lambda delay: clock.__setitem__(0, clock[0] + delay))
    request = Mock(side_effect=ConnectionResetError('not ready'))
    monkeypatch.setattr(smoke.API, 'call', request)
    with pytest.raises(RuntimeError, match='healthy') as failed:
        smoke.wait_ready('http://localhost', timeout=3)
    assert isinstance(failed.value.__cause__, ConnectionResetError)
    assert clock[0] == 3
    assert request.call_count == 3
    assert [call.kwargs['timeout'] for call in request.call_args_list] == [3, 2, 1]


def test_business_calls_do_not_retry_transport_errors(monkeypatch):
    opened = Mock(side_effect=ConnectionResetError('business failed'))
    monkeypatch.setattr(smoke, 'build_opener', lambda *_: type('Opener', (), {'open': opened})())
    with pytest.raises(ConnectionResetError):
        smoke.API('http://localhost').call('/api/catalog')
    assert opened.call_count == 1
