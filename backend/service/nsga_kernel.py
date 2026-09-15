"""NumPy kernel for the existing constrained-dominance comparison rules."""

import numpy as np


class ObjectiveProgress:
    """Track endpoint and compromise improvements on fixed initial scales.

    Sixteen nonnegative directions sample tradeoffs, including the three axes
    and the equal-weight compromise. This is a stopping heuristic, not a proof
    of front convergence. The first feasible population fixes all scales.
    """

    def __init__(self, threshold):
        self.threshold = threshold
        self.weights = np.array([[a/4, b/4, (4-a-b)/4]
                                 for a in range(5) for b in range(5-a)] + [[1/3]*3])
        self.origin = None
        self.scale = None
        self.best = np.full(len(self.weights), np.inf)

    def update(self, values):
        values = np.asarray(values, dtype=float)
        if self.origin is None:
            self.origin = values.min(axis=0)
            span = values.max(axis=0) - self.origin
            self.scale = np.where(span > 1e-12, span, 1.)
        scores = (((values - self.origin) / self.scale) @ self.weights.T).min(axis=0)
        improved = bool(np.any(scores < self.best - self.threshold))
        self.best = np.minimum(self.best, scores)
        return improved


def dominance_matrix(items):
    """Entry (i, j) is true exactly when i constrained-dominates j."""
    values = np.asarray([item['objective_tuple'] for item in items], dtype=float)
    feasible = np.asarray([item['is_feasible'] for item in items], dtype=bool)
    violations = np.asarray([item['violation_score'] for item in items], dtype=float)
    size = len(items)
    no_worse = np.ones((size, size), dtype=bool)
    better = np.zeros((size, size), dtype=bool)
    for column in values.T:
        no_worse &= column[:, None] <= column[None, :] + 1e-12
        better |= column[:, None] < column[None, :] - 1e-12
    result = no_worse & better & feasible[:, None] & feasible[None, :]
    result |= feasible[:, None] & ~feasible[None, :]
    result |= (~feasible[:, None] & ~feasible[None, :]
               & (violations[:, None] < violations[None, :] - 1e-12))
    np.fill_diagonal(result, False)
    return result
