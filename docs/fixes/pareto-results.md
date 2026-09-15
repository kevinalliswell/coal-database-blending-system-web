# Pareto recommendation and display integrity

Recommendations now use the complete feasible front returned by the search.
Cost, heat and quality-penalty normalization are calculated from that same front
before applying the display limit. Changing `pareto_solution_limit` therefore
does not change a recommendation, its solution ID, or its normalization basis
for the same search result. Two-coal searches use a fixed 161-point grid so their
search resolution also remains independent of the display limit.

The displayed set retains the recommendation and, when enough slots are
available, minimum cost, maximum heat and minimum penalty. Remaining slots
maximize coverage in the normalized objective space. If fewer than four slots
are requested, the recommendation takes priority, followed by those endpoints
in the stated order. IDs refer to positions in the complete cost-sorted front
and may have gaps in the displayed subset.

When the generation limit is reached, NSGA-II returns the final selected
population, including improvements found in the last offspring generation.

Regression checks cover two- and three-coal recommendation invariance across
display budgets, analytically known two-coal endpoints and midpoint, and a
dominating solution discovered in the last generation. These checks establish
result integrity; a finite evolutionary search still does not certify global
Pareto optimality or industrial coal performance.
