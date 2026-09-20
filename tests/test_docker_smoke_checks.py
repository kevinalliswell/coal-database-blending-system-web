"""The release smoke must fail on incomplete evidence, not merely return 200."""
import importlib.util
from pathlib import Path

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
