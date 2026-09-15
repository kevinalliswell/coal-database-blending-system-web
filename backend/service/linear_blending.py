"""Deterministic objective endpoints for the current linear blending model."""

import numpy as np
from scipy.optimize import linprog


def objective_endpoint_seeds(metrics, params, ratio_limits, inequalities, limits):
    size = len(metrics['price'])
    bounds = list(zip(ratio_limits['min'], ratio_limits['max']))
    seeds = []
    maximum_heat = linprog(-metrics['heat'], A_ub=inequalities or None, b_ub=limits or None,
                           A_eq=[np.ones(size)], b_eq=[1.], bounds=bounds, method='highs')
    if maximum_heat.success:
        seeds.append(maximum_heat.x.tolist())

    # On the feasible domain, ash/sulfur are linear and the other terms are
    # absolute deviations. Two epigraph variables represent those deviations.
    objective = np.zeros(size + 2)
    for metric, lower, upper in [('ash', 'ash_min', 'ash_limit'), ('sulfur', 'sulfur_min', 'sulfur_limit')]:
        if params.get(lower) is not None and params.get(upper) is not None:
            span = float(params[upper]) - float(params[lower])
            if span > 0:
                objective[:size] += metrics[metric] / (4 * max(span, 1e-9))
    rows = [list(row) + [0., 0.] for row in inequalities]
    right = list(limits)
    for extra, (metric, lower, upper) in enumerate([
        ('volatile', 'volatile_min', 'volatile_max'),
        ('fixed_carbon', 'fixed_carbon_min', 'fixed_carbon_max'),
    ]):
        if params.get(lower) is None or params.get(upper) is None:
            continue
        low, high = float(params[lower]), float(params[upper])
        if high == low:
            continue  # An equality fixes this penalty at zero on the exact feasible set.
        midpoint, half_span = (low + high)/2, max((high - low)/2, 1e-9)
        objective[size + extra] = .25
        for sign in [1, -1]:
            row = np.zeros(size + 2)
            row[:size] = sign * metrics[metric] / half_span
            row[size + extra] = -1.
            rows.append(row.tolist())
            right.append(sign * midpoint / half_span)
    minimum_penalty = linprog(objective, A_ub=rows or None, b_ub=right or None,
                              A_eq=[np.r_[np.ones(size), 0., 0.]], b_eq=[1.],
                              bounds=bounds + [(0., None), (0., None)], method='highs')
    if minimum_penalty.success:
        seeds.append(minimum_penalty.x[:size].tolist())
    return seeds
