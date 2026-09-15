import type { OptimizationRequest, OptimizationResponse, ParetoSolution } from './types';

export function captureRequest(request: OptimizationRequest): OptimizationRequest {
  return structuredClone(request);
}

export function matchesRequest(submitted: OptimizationRequest | null, current: OptimizationRequest): boolean {
  return submitted !== null && JSON.stringify(submitted) === JSON.stringify(current);
}

/** Export the candidate being viewed, with the completed run's input window. */
export function buildExportPayload(
  response: OptimizationResponse,
  submitted: OptimizationRequest,
  solution: ParetoSolution,
): OptimizationResponse {
  return {
    ...response,
    constraints: response.input_snapshot?.constraints ?? response.constraints ?? submitted.constraints,
    result: {
      ...response.result,
      ...solution,
      blending_ratio: Object.fromEntries(solution.coal_names.map((name, i) => [name, solution.optimal_ratios[i]])),
      fitness_value: solution.quality_penalty,
      constraints_satisfied: solution.is_feasible,
      constraint_violations: solution.constraint_violations ?? [],
      active_constraints: solution.active_constraints ?? [],
      violation_score: solution.violation_score ?? null,
      recommended_solution: solution,
      selected_solution_id: solution.solution_id,
    },
  };
}
