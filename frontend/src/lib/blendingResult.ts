import type { DataValidation, OptimizationRequest, OptimizationResponse, ParetoSolution } from './types';

export function captureRequest(request: OptimizationRequest): OptimizationRequest {
  return structuredClone(request);
}

export function matchesRequest(submitted: OptimizationRequest | null, current: OptimizationRequest): boolean {
  return submitted !== null && JSON.stringify(submitted) === JSON.stringify(current);
}

export function resolveDataValidation(validation: DataValidation | undefined, submitted: OptimizationRequest): DataValidation | undefined {
  if (submitted.calculation_mode !== 'screening') return validation;
  return {
    status: 'unverified',
    scope: 'screening_only',
    ratio_basis: submitted.ratio_basis ?? 'unknown',
    warnings: validation?.warnings?.length ? validation.warnings : ['本次使用未确认数据试算，仅用于筛选，不可直接用于生产。'],
  };
}

export function dataValidationLabel(validation: DataValidation | undefined, mode?: OptimizationRequest['calculation_mode']): string {
  if (mode === 'screening' || validation?.status === 'unverified') return '基准未确认，仅用于筛选';
  if (validation?.status === 'verified') return '基准检查通过';
  return '基准验证未记录';
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
      data_validation: resolveDataValidation(response.result.data_validation, submitted),
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
