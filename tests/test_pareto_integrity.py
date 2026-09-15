import pytest

from backend.service.blending_service import (
    ImprovedGeneticOptimizer,
    NSGA2BlendingOptimizer,
    OptimizedSmartBlendingAlgorithm,
)


def tradeoff_coals(count):
    return [
        dict(name=f'coal-{index}', price=price, calorific_value=heat,
             ash_content=10, volatile_matter=20, fixed_carbon=65, total_sulfur=.5)
        for index, (price, heat) in enumerate([(500, 6000), (900, 7400), (700, 6700)][:count])
    ]


def tradeoff_params(count):
    return dict(heat_min=5000, heat_max=8000, ash_min=0, ash_limit=20,
                volatile_min=10, volatile_max=30, fixed_carbon_min=50,
                fixed_carbon_max=80, sulfur_min=0, sulfur_limit=1,
                price_min=0, price_limit=1000,
                ratio_constraints={'min': [0.] * count, 'max': [1.] * count})


@pytest.mark.parametrize('coal_count', [2, 3])
def test_display_limit_preserves_full_front_recommendation_and_extremes(coal_count):
    results = []
    for limit in [200, 4, 1]:
        algorithm = OptimizedSmartBlendingAlgorithm()
        algorithm.set_optimizer_config(dict(population_size=30, max_generations=8,
                                             random_seed=42, pareto_solution_limit=limit))
        result = algorithm.calculate(tradeoff_coals(coal_count), tradeoff_params(coal_count))
        assert result['status'] == 'success'
        summary = result['summary']
        assert len(summary['pareto_solutions']) <= limit
        assert summary['recommended_solution'] in summary['pareto_solutions']
        results.append(summary)

    full, compact, single = results
    assert compact['recommended_solution'] == full['recommended_solution']
    assert single['recommended_solution'] == full['recommended_solution']
    for key, extreme in [('total_price', min), ('total_heat', max), ('quality_penalty', min)]:
        assert extreme(item[key] for item in compact['pareto_solutions']) == pytest.approx(
            extreme(item[key] for item in full['pareto_solutions']))
    if coal_count == 2:
        # Analytically, the normalized two-objective compromise is the midpoint.
        assert compact['recommended_solution']['optimal_ratios'] == pytest.approx([.5, .5])
        assert min(item['total_price'] for item in compact['pareto_solutions']) == 500
        assert max(item['total_heat'] for item in compact['pareto_solutions']) == 7400


def test_final_generation_returns_newly_found_dominating_solution(monkeypatch):
    base = ImprovedGeneticOptimizer(dict(population_size=2, max_generations=1,
                                         mutation_rate=1, crossover_rate=0, tournament_size=2))
    optimizer = NSGA2BlendingOptimizer(base)
    monkeypatch.setattr(optimizer, '_create_initial_population', lambda *args: [[1., 0.], [.8, .2]])
    monkeypatch.setattr(base, 'mutate', lambda *args: [0., 1.])

    def evaluate(ratios):
        value = ratios[0]
        return dict(is_feasible=True, violation_score=0, total_price=value, total_heat=1-value,
                    quality_penalty=value, objective_tuple=(value, value, value))

    result = optimizer.optimize(evaluate, 2, {'min': [0., 0.], 'max': [1., 1.]})
    assert [item['ratios'] for item in result] == [[0., 1.]]
