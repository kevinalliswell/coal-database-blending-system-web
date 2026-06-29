import math

from backend.service.blending_service import OptimizedSmartBlendingAlgorithm
from backend.routes.optimization import _build_api_result


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


def assert_solution_is_feasible(solution):
    assert solution['is_feasible'] is True
    assert solution['constraint_violations'] == []
    assert math.isclose(sum(solution['optimal_ratios']), 1.0, rel_tol=0, abs_tol=1e-6)


def dominates(left, right):
    left_objectives = left['objective_values']
    right_objectives = right['objective_values']
    left_values = [
        left_objectives['cost'],
        -left_objectives['heat'],
        left_objectives['quality_penalty'],
    ]
    right_values = [
        right_objectives['cost'],
        -right_objectives['heat'],
        right_objectives['quality_penalty'],
    ]

    return all(left <= right + 1e-9 for left, right in zip(left_values, right_values)) and any(
        left < right - 1e-9 for left, right in zip(left_values, right_values)
    )


def test_pci_optimization_returns_pareto_front_and_recommendation():
    algorithm = OptimizedSmartBlendingAlgorithm()
    algorithm.set_optimizer_config({
        'population_size': 80,
        'max_generations': 80,
        'parallel_computing': False,
        'random_seed': 42,
    })
    coals = build_coals()
    params = build_params()

    result = algorithm.calculate(coals, params, optimization_target='喷煤性价比最优')

    assert result['status'] == 'success'
    assert result['summary']['objective_type'] == 'pci_pareto_nsga2_v1'
    assert result['summary']['optimization_target'] == '多目标Pareto最优'

    pareto_solutions = result['summary']['pareto_solutions']
    recommended_solution = result['summary']['recommended_solution']
    assert len(pareto_solutions) >= 2
    assert recommended_solution['solution_id'] in {solution['solution_id'] for solution in pareto_solutions}

    for solution in pareto_solutions:
        assert_solution_is_feasible(solution)
        assert set(solution['objective_values']) == {'cost', 'heat', 'quality_penalty'}

    for left in pareto_solutions:
        for right in pareto_solutions:
            if left is not right:
                assert not dominates(left, right)

    assert result['summary']['is_feasible'] is True
    assert math.isclose(sum(item['ratio'] for item in result['coal_results']) / 100.0, 1.0, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(result['summary']['total_price'], recommended_solution['total_price'], rel_tol=0, abs_tol=1e-6)
    assert math.isclose(result['summary']['total_heat'], recommended_solution['total_heat'], rel_tol=0, abs_tol=1e-6)


def test_legacy_targets_map_to_same_pci_objective():
    algorithm = OptimizedSmartBlendingAlgorithm()
    algorithm.set_optimizer_config({
        'population_size': 40,
        'max_generations': 40,
        'parallel_computing': False,
        'random_seed': 7,
    })
    coals = build_coals()
    params = build_params()

    low_cost = algorithm.calculate(coals, params, optimization_target='最低成本')
    cost_effective = algorithm.calculate(coals, params, optimization_target='最高性价比')

    assert low_cost['status'] == 'success'
    assert cost_effective['status'] == 'success'
    assert low_cost['summary']['optimization_target'] == '多目标Pareto最优'
    assert cost_effective['summary']['optimization_target'] == '多目标Pareto最优'
    assert low_cost['summary']['recommended_solution']['solution_id']
    assert cost_effective['summary']['recommended_solution']['solution_id']


def test_api_result_keeps_legacy_fields_and_exposes_pareto_payload():
    algorithm = OptimizedSmartBlendingAlgorithm()
    algorithm.set_optimizer_config({
        'population_size': 50,
        'max_generations': 50,
        'parallel_computing': False,
        'random_seed': 11,
    })
    coals = build_coals()
    params = build_params()

    algorithm_result = algorithm.calculate(coals, params)
    payload = _build_api_result([coal['name'] for coal in coals], algorithm_result, 0.25)
    data = payload['result']

    assert payload['status'] == 'success'
    assert data['objective_type'] == 'pci_pareto_nsga2_v1'
    assert data['recommended_solution']['solution_id']
    assert len(data['pareto_solutions']) >= 2
    assert data['optimal_ratios'] == data['recommended_solution']['optimal_ratios']
    assert data['blending_ratio'] == dict(zip(data['coal_names'], data['optimal_ratios']))
    assert math.isclose(data['total_price'], data['recommended_solution']['total_price'], rel_tol=0, abs_tol=1e-6)
    assert data['fitness_value'] == data['recommended_solution']['quality_penalty']


def test_two_coal_blending_uses_fast_path_and_returns_pareto_result():
    algorithm = OptimizedSmartBlendingAlgorithm()
    algorithm.set_optimizer_config({
        'population_size': 50,
        'max_generations': 50,
        'parallel_computing': False,
        'random_seed': 11,
    })
    coals = [
        {
            'name': '山西潞阳洗末煤 S1.0（分析基）',
            'price': 998.46,
            'calorific_value': 7419.0,
            'ash_content': 11.5877775,
            'volatile_matter': 9.6089175,
            'fixed_carbon': 76.3035,
            'total_sulfur': 0.9,
        },
        {
            'name': '宁煤3#烟煤（分析基）',
            'price': 812.23,
            'calorific_value': 6540.0,
            'ash_content': 10.6145325,
            'volatile_matter': 32.10714,
            'fixed_carbon': 54.7783275,
            'total_sulfur': 0.84,
        },
    ]
    params = {
        'heat_target': 6800,
        'heat_min': 6000,
        'heat_max': 7800,
        'ash_min': 0.0,
        'ash_limit': 20.0,
        'volatile_min': 8.0,
        'volatile_max': 40.0,
        'fixed_carbon_min': 50.0,
        'fixed_carbon_max': 85.0,
        'sulfur_min': 0.0,
        'sulfur_limit': 1.2,
        'price_min': 0.0,
        'price_limit': 1500.0,
        'ratio_constraints': {
            'min': [0.0, 0.0],
            'max': [1.0, 1.0],
        },
    }

    result = algorithm.calculate(coals, params, optimization_target='喷煤性价比最优')

    assert result['status'] == 'success'
    assert result['summary']['generations_used'] == 0
    assert result['summary']['is_feasible'] is True
    assert len(result['summary']['pareto_solutions']) >= 1
    assert math.isclose(sum(result['summary']['recommended_solution']['optimal_ratios']), 1.0, rel_tol=0, abs_tol=1e-6)


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
        assert '多目标Pareto最优' in str(exc)
    else:
        raise AssertionError('最佳性能 should be rejected')
