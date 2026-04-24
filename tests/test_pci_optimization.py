import math

from backend.service.blending_service import OptimizedSmartBlendingAlgorithm


def build_params():
    return {
        'heat_min': 5900,
        'heat_max': 6200,
        'ash_min': 8.0,
        'ash_limit': 12.0,
        'volatile_min': 18.0,
        'volatile_max': 28.0,
        'fixed_carbon_min': 60.0,
        'fixed_carbon_max': 72.0,
        'sulfur_min': 0.4,
        'sulfur_limit': 0.8,
        'price_min': 400.0,
        'price_limit': 800.0,
        'ratio_constraints': {
            'min': [0.0, 0.0, 0.0],
            'max': [1.0, 1.0, 1.0],
        },
    }


def build_coals():
    return [
        {
            'name': '经济煤',
            'price': 500.0,
            'calorific_value': 6000.0,
            'ash_content': 10.0,
            'volatile_matter': 20.0,
            'fixed_carbon': 65.0,
            'total_sulfur': 0.5,
        },
        {
            'name': '高热值煤',
            'price': 700.0,
            'calorific_value': 6400.0,
            'ash_content': 9.0,
            'volatile_matter': 19.0,
            'fixed_carbon': 68.0,
            'total_sulfur': 0.4,
        },
        {
            'name': '高硫低价煤',
            'price': 450.0,
            'calorific_value': 6100.0,
            'ash_content': 10.5,
            'volatile_matter': 21.0,
            'fixed_carbon': 64.0,
            'total_sulfur': 1.1,
        },
    ]


def test_pci_optimization_prefers_lowest_cost_feasible_solution():
    algorithm = OptimizedSmartBlendingAlgorithm()
    coals = build_coals()
    params = build_params()

    result = algorithm.calculate(coals, params, optimization_target='喷煤性价比最优')

    assert result['status'] == 'success'
    assert result['summary']['is_feasible'] is True
    assert result['summary']['optimization_target'] == '喷煤性价比最优'
    assert math.isclose(sum(item['ratio'] for item in result['coal_results']) / 100.0, 1.0, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(result['summary']['total_price'], 475.0, rel_tol=0, abs_tol=1e-3)

    ratio_map = {item['name']: item['ratio'] for item in result['coal_results']}
    assert math.isclose(ratio_map['经济煤'], 50.0, rel_tol=0, abs_tol=1e-3)
    assert math.isclose(ratio_map['高硫低价煤'], 50.0, rel_tol=0, abs_tol=1e-3)


def test_legacy_targets_map_to_same_pci_objective():
    algorithm = OptimizedSmartBlendingAlgorithm()
    coals = build_coals()
    params = build_params()

    low_cost = algorithm.calculate(coals, params, optimization_target='最低成本')
    cost_effective = algorithm.calculate(coals, params, optimization_target='最高性价比')

    assert low_cost['status'] == 'success'
    assert cost_effective['status'] == 'success'
    assert low_cost['summary']['optimization_target'] == '喷煤性价比最优'
    assert cost_effective['summary']['optimization_target'] == '喷煤性价比最优'
    assert math.isclose(low_cost['summary']['total_price'], cost_effective['summary']['total_price'], rel_tol=0, abs_tol=1e-6)


def test_returns_no_feasible_solution_when_constraints_conflict():
    algorithm = OptimizedSmartBlendingAlgorithm()
    coals = [
        {
            'name': '高硫煤A',
            'price': 500.0,
            'calorific_value': 6000.0,
            'ash_content': 10.0,
            'volatile_matter': 20.0,
            'fixed_carbon': 65.0,
            'total_sulfur': 0.95,
        },
        {
            'name': '高硫煤B',
            'price': 520.0,
            'calorific_value': 6050.0,
            'ash_content': 10.0,
            'volatile_matter': 21.0,
            'fixed_carbon': 64.0,
            'total_sulfur': 1.05,
        },
    ]
    params = {
        'heat_min': 5900,
        'heat_max': 6200,
        'ash_min': 8.0,
        'ash_limit': 12.0,
        'volatile_min': 18.0,
        'volatile_max': 28.0,
        'fixed_carbon_min': 60.0,
        'fixed_carbon_max': 72.0,
        'sulfur_min': 0.4,
        'sulfur_limit': 0.8,
        'price_min': 400.0,
        'price_limit': 800.0,
        'ratio_constraints': {
            'min': [0.0, 0.0],
            'max': [1.0, 1.0],
        },
    }

    result = algorithm.calculate(coals, params, optimization_target='喷煤性价比最优')

    assert result['status'] == 'no_feasible_solution'
    assert result['summary']['is_feasible'] is False
    assert result['coal_results'] == []
    assert result['summary']['constraint_violations']


def test_best_performance_target_is_rejected():
    algorithm = OptimizedSmartBlendingAlgorithm()

    try:
        algorithm.calculate(build_coals(), build_params(), optimization_target='最佳性能')
    except ValueError as exc:
        assert '喷煤性价比最优' in str(exc)
    else:
        raise AssertionError('最佳性能 should be rejected')
