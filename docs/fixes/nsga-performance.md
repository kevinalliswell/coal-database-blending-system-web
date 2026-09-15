# NSGA-II performance, endpoint coverage and effective controls

The constrained-dominance rules now run in a NumPy matrix kernel. Feasibility
priority, violation ordering, the 1e-12 objective tolerance, front membership and
scalar traversal order remain unchanged. This removes the nested Python
comparison bottleneck without switching the default solver.

For three or more coals, initial populations also receive feasible LP solutions
for maximum heat and minimum quality penalty, alongside the existing minimum
cost solution. The current penalty is linear plus two absolute deviations, so
two epigraph variables suffice for its LP formulation. Seeds are checked by the
same solution evaluator before insertion. A population too small to hold three
distinct seeds prioritizes cost, heat, then penalty. The evolutionary front is
still approximate; this does not validate the coal model against plant data.

Exact ratio tuples now identify candidates. Rounding ratios to eight decimal
places previously merged distinct quality scores inside narrow feasible windows
and could discard an LP penalty endpoint.

Early stopping observes sixteen nonnegative scalarization directions, including
the three endpoints and balanced compromises. Its scales are fixed by the first
feasible population, so later changes in population ranges do not manufacture
progress. Stable endpoints alone no longer trigger stopping while monitored
compromises improve. This remains a heuristic, not a convergence certificate.

## Controls and compatibility

The panel exposes the active NSGA-II controls, random seed, normalized progress
threshold and display limit. Elite ratio, scalar penalty multiplier, diversity
factor and legacy thread controls have been removed from the panel. Old API
requests remain accepted, with explicit `parameter_warnings` and `warning`.
The obsolete heat target is not forwarded to the solver; heat minimum and
maximum define its process window. Its UI removal is delivered separately with
the result-snapshot fix.

Python and NumPy RNGs are instance-local. A missing seed is generated once and
recorded in the optimizer configuration before solving, so the effective input
snapshot can reproduce that run. Repeated requests do not reset process-global
RNG state. Reproduction assumes the same inputs, solver version and numerical
environment.

## Verification and measured performance

Regression checks compare ranks against scalar constrained dominance, cover
ties and infeasible candidates, verify seed isolation and API forwarding,
recover analytically known narrow-domain endpoints in one generation, and
detect compromise progress without changing normalization scales.

The review's six repository coals (IDs 1,2,5,6,7,8), each constrained to 5–60%,
were measured on macOS / Python 3.12.12 / NumPy 1.26.2 / SciPy 1.11.4, using
population 500, maximum 3000 generations, patience 200, seed 42 and the API's
default quality ranges:

| Implementation | Completed generations | Wall time |
|---|---:|---:|
| Reviewed original | Still running at generation 210 | Stopped at 200.006 s |
| Matrix kernel and local RNG alone | 1115 | 60.196 s |
| Final endpoint and compromise-progress implementation | 996 | 53.802 s |

The kernel-only measurement independently demonstrates the performance gain;
the final result does not rely on stopping immediately after seeding endpoints.
This workload completes below the repository's 180-second Gunicorn timeout on
the test machine. Production performance and other inputs still require their
own measurements. Matrix storage is quadratic in population size; the API
limits population to 2000. This change does not turn requests into background
jobs or eliminate the need for capacity planning.
