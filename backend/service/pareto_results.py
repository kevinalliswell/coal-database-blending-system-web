"""Choose recommendations and display coverage using the complete front."""

import numpy as np


def normalized_objectives(solutions):
    """Normalize minimization coordinates against the same complete front."""
    values = np.asarray([
        [item['objective_values']['cost'], -item['objective_values']['heat'],
         item['objective_values']['quality_penalty']]
        for item in solutions
    ], dtype=float)
    minimum = values.min(axis=0)
    span = values.max(axis=0) - minimum
    return np.divide(values - minimum, span, out=np.zeros_like(values), where=span > 1e-12)


def select_display_solutions(solutions, recommended, limit):
    """Keep the recommendation, objective endpoints, then spread remaining slots.

    A limit below four may not fit all distinct endpoints. The recommendation
    takes priority, followed by minimum cost, maximum heat and minimum penalty.
    Solution IDs and the normalization basis remain those of the full front.
    """
    limit = max(1, int(limit))
    if len(solutions) <= limit:
        return solutions

    points = normalized_objectives(solutions)
    recommended_index = next(index for index, item in enumerate(solutions)
                             if item['solution_id'] == recommended['solution_id'])
    endpoints = [
        min(range(len(solutions)), key=lambda index: solutions[index]['total_price']),
        max(range(len(solutions)), key=lambda index: solutions[index]['total_heat']),
        min(range(len(solutions)), key=lambda index: solutions[index]['quality_penalty']),
    ]
    selected = list(dict.fromkeys([recommended_index, *endpoints]))[:limit]
    nearest_distance = np.full(len(solutions), np.inf)
    for index in selected:
        nearest_distance = np.minimum(nearest_distance, np.sum((points - points[index]) ** 2, axis=1))
    while len(selected) < limit:
        nearest_distance[selected] = -1
        index = int(np.argmax(nearest_distance))
        selected.append(index)
        nearest_distance = np.minimum(nearest_distance, np.sum((points - points[index]) ** 2, axis=1))
    return [solutions[index] for index in sorted(selected)]
