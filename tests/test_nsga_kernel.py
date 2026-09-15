import copy
import random

import numpy as np
import pytest

from backend.routes.optimization import _build_ga_config
from backend.service.blending_service import ImprovedGeneticOptimizer, NSGA2BlendingOptimizer
from backend.service.blending_service import OptimizedSmartBlendingAlgorithm


def reference_fronts(items):
    remaining = list(range(len(items)))
    result = []
    while remaining:
        front = [right for right in remaining if not any(
            NSGA2BlendingOptimizer.dominates(items[left], items[right]) for left in remaining if left != right)]
        assert front
        result.append(set(front))
        remaining = [index for index in remaining if index not in front]
    return result


def test_sort_matches_scalar_constrained_dominance_with_ties():
    rng = np.random.default_rng(47)
    items = [dict(objective_tuple=tuple(row), is_feasible=index % 4 != 0,
                  violation_score=float(index % 5))
             for index, row in enumerate(rng.integers(0, 12, size=(80, 3)))]
    items.extend(copy.deepcopy(items[:3]))
    items.extend([dict(objective_tuple=(1., 1., 1.), is_feasible=True, violation_score=0),
                  dict(objective_tuple=(1. + 5e-13, 1., 1.), is_feasible=True, violation_score=0)])
    expected = reference_fronts(items)
    optimizer = NSGA2BlendingOptimizer(ImprovedGeneticOptimizer())
    actual = optimizer.fast_non_dominated_sort(items)
    assert [set(front) for front in actual] == expected
    for rank, front in enumerate(actual, start=1):
        assert all(items[index]['rank'] == rank for index in front)
    assert optimizer.fast_non_dominated_sort([]) in ([], [[]])


def test_progress_detects_compromise_improvement_without_rescaling():
    from backend.service.nsga_kernel import ObjectiveProgress
    endpoints = np.array([[0., 1., 1.], [1., 0., 1.], [1., 1., 0.]])
    for scales, offsets in [(np.ones(3), np.zeros(3)),
                            (np.array([1000., 100., .01]), np.array([500., 2000., 0.]))]:
        progress = ObjectiveProgress(1e-6)
        assert progress.update(endpoints * scales + offsets)
        improved = np.vstack([endpoints, [.4, .4, .4]])
        assert progress.update(improved * scales + offsets)
        assert not progress.update(improved * scales + offsets)
        # A worse point expanding this generation's range cannot create progress.
        assert not progress.update(np.vstack([improved, [100., 100., 100.]]) * scales + offsets)


def test_api_passes_supported_reproducibility_controls():
    config = _build_ga_config(dict(random_seed=47, convergence_threshold=1e-4, pareto_solution_limit=9))
    assert config['random_seed'] == 47
    assert config['convergence_threshold'] == 1e-4
    assert config['pareto_solution_limit'] == 9


def test_legacy_controls_are_reported_instead_of_presented_as_effective():
    from backend.routes.optimization import _build_parameter_warnings
    legacy = dict(elite_ratio=.9, parallel_computing=True, parallel_workers=16,
                  constraint_penalty_factor=1e9, diversity_factor=1)
    config = _build_ga_config(legacy)
    assert config['parallel_computing'] is False
    assert config['parallel_workers'] == 1
    assert 'elite_ratio' not in config
    assert 'constraint_penalty_factor' not in config
    assert 'diversity_factor' not in config
    warnings = _build_parameter_warnings({'ga_params': legacy, 'constraints': {'heat_target': 6800}})
    assert any('elite_ratio' in message for message in warnings)
    assert any('heat_target' in message for message in warnings)


def test_automatic_seed_is_available_for_history_reproduction():
    optimizer = ImprovedGeneticOptimizer()
    seed = optimizer.config.get('random_seed')
    assert isinstance(seed, int)
    assert 0 <= seed < 2**32


def test_seeded_optimization_does_not_change_process_random_generators():
    random.seed(987)
    np.random.seed(987)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    optimizer = NSGA2BlendingOptimizer(ImprovedGeneticOptimizer(dict(
        population_size=4, max_generations=2, random_seed=47)))

    def objective(ratios):
        return dict(is_feasible=True, violation_score=0, total_price=ratios[0],
                    total_heat=ratios[1], quality_penalty=0,
                    objective_tuple=(ratios[0], -ratios[1], 0))

    limits = {'min': [0., 0., 0.], 'max': [1., 1., 1.]}
    first = optimizer.optimize(objective, 3, limits)
    second = optimizer.optimize(objective, 3, limits)
    assert first == second
    assert random.getstate() == python_state
    actual_numpy = np.random.get_state()
    assert actual_numpy[0] == numpy_state[0]
    np.testing.assert_array_equal(actual_numpy[1], numpy_state[1])
    assert actual_numpy[2:] == numpy_state[2:]


def test_linear_objective_endpoints_seed_a_narrow_feasible_front():
    coals = [dict(name=name, price=price, calorific_value=heat, volatile_matter=volatile,
                  fixed_carbon=98-10-volatile, ash_content=10, total_sulfur=.5)
             for name, price, heat, volatile in [
                 ('anthracite-A', 600, 6500, 10), ('anthracite-B', 900, 7500, 10),
                 ('bituminous-A', 700, 6500, 30), ('bituminous-B', 1000, 7500, 30)]]
    params = dict(heat_min=6000, heat_max=7800, ash_min=0, ash_limit=20,
                  volatile_min=20-1e-8, volatile_max=20+1e-8,
                  fixed_carbon_min=50, fixed_carbon_max=85, sulfur_min=0, sulfur_limit=1.2,
                  price_min=0, price_limit=1500,
                  ratio_constraints={'min': [.05]*4, 'max': [.6]*4})
    algorithm = OptimizedSmartBlendingAlgorithm()
    algorithm.set_optimizer_config(dict(population_size=12, max_generations=1, random_seed=42))
    result = algorithm.calculate(coals, params)
    assert result['status'] == 'success'
    front = result['summary']['pareto_solutions']
    assert min(item['total_price'] for item in front) == pytest.approx(680)
    assert max(item['total_heat'] for item in front) == pytest.approx(7400)
    # In this feasible plane only volatility varies the penalty; the midpoint is attainable.
    assert min(item['quality_penalty'] for item in front) == pytest.approx((.5 + .5/1.2 + .5/17.5)/4, abs=1e-6)
