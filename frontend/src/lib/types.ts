/* Domain models — mirror the Flask backend contracts exactly. */

export interface Coal {
  id: number;
  name: string;
  type: string;
  price: number;
  calorific_value: number;
  ash_content: number;
  volatile_matter: number;
  fixed_carbon: number;
  total_sulfur: number;
  total_moisture: number | null;
  air_dry_moisture: number | null;
  moisture: number | null; // alias of total_moisture
  mad: number | null; // alias of air_dry_moisture
  supplier: string | null;
  hgi: number | null;
  burnout_rate: number | null;
  carbon_content: number | null;
  hydrogen_content: number | null;
  nitrogen_content: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export type CoalDraft = Omit<Coal, 'id' | 'created_at' | 'updated_at' | 'total_moisture' | 'air_dry_moisture'>;

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface CoalListResponse {
  status: string;
  data: Coal[];
  pagination: Pagination;
}

export interface HealthInfo {
  status: string;
  app: string;
  storage_mode: string;
  coal_count: number;
}

/* ---------- Optimization ---------- */

export interface RatioBound {
  min: number; // percent 0-100
  max: number;
}

export interface BlendingConstraints {
  /** Legacy historical field; not used by the optimizer. */
  heat_target?: number;
  heat_min: number;
  heat_max: number;
  ash_min: number;
  ash_max: number;
  volatile_min: number;
  volatile_max: number;
  fixed_carbon_min: number;
  fixed_carbon_max: number;
  sulfur_min: number;
  sulfur_max: number;
  price_min: number;
  price_max: number;
  ratio_constraints: Record<string, RatioBound>;
}

export interface GaParams {
  population_size: number;
  max_generations: number;
  mutation_rate: number;
  crossover_rate: number;
  tournament_size: number;
  /** @deprecated Ignored by NSGA-II; accepted only for old saved requests. */
  elite_ratio?: number;
  early_stopping_patience: number;
  constraint_penalty_factor?: number;
  parallel_workers?: number;
  adaptive_mutation: boolean;
  parallel_computing?: boolean;
  diversity_factor?: number;
  random_seed?: number;
  convergence_threshold?: number;
  pareto_solution_limit?: number;
}

export interface OptimizationRequest {
  optimization_target: string;
  selected_coal_ids: number[];
  constraints: Partial<BlendingConstraints>;
  ga_params: GaParams;
}

export interface ObjectiveValues {
  cost: number;
  heat: number;
  quality_penalty: number;
}

export interface ParetoSolution {
  solution_id: string;
  rank?: number;
  crowding_distance?: number;
  coal_names: string[];
  optimal_ratios: number[]; // fractions summing to 1
  blending_ratio?: Record<string, number>;
  total_price: number;
  total_heat: number;
  total_ash: number;
  total_volatile: number;
  total_fixed_carbon: number;
  total_sulfur: number;
  performance_price_ratio?: number;
  quality_penalty: number;
  objective_values?: ObjectiveValues;
  is_feasible: boolean;
  violation_score?: number;
  constraint_violations?: ConstraintViolation[];
  active_constraints?: string[];
}

export interface ConstraintViolation {
  label: string;
  detail: string;
}

export interface OptimizationResult {
  selected_solution_id?: string;
  objective_type: string;
  optimization_target: string;
  coal_names: string[];
  optimal_ratios: number[];
  blending_ratio: Record<string, number>;
  total_price: number;
  total_heat: number;
  total_ash: number;
  total_volatile: number;
  total_fixed_carbon: number;
  total_sulfur: number;
  performance_price_ratio?: number;
  iterations: number;
  time_taken: number;
  fitness_value: number;
  quality_penalty: number;
  is_feasible: boolean;
  constraints_satisfied: boolean;
  constraint_violations: ConstraintViolation[];
  violation_score: number | null;
  active_constraints: string[];
  diagnosis: string[];
  objective_values: ObjectiveValues;
  recommended_solution: ParetoSolution;
  pareto_solutions: ParetoSolution[];
  timestamp: string;
}

export type OptimizationStatus =
  | 'success'
  | 'no_feasible_solution'
  | 'search_failed'
  | 'error';

export interface OptimizationResponse {
  status: OptimizationStatus;
  message: string;
  history_saved?: boolean;
  warning?: string;
  parameter_warnings?: string[];
  constraints?: Partial<BlendingConstraints>;
  input_snapshot?: {
    schema_version: number;
    coals: Coal[];
    algorithm_coals: Record<string, unknown>[];
    algorithm_params: Record<string, unknown>;
    ga_config: Record<string, unknown>;
    constraints: Partial<BlendingConstraints>;
  };
  result: OptimizationResult;
}

export interface OptimizationHistoryItem {
  id: number;
  timestamp: string;
  date: string;
  coal_names: string[];
  optimal_ratios: number[];
  ratio_items: { coal_name: string; ratio: number; ratio_percent: number }[];
  total_price: number | null;
  total_heat: number | null;
  total_ash: number | null;
  total_volatile: number | null;
  total_fixed_carbon: number | null;
  total_sulfur: number | null;
  performance_price_ratio: number | null;
  iterations: number | null;
  time_taken: number | null;
  fitness_value: number | null;
  constraints_satisfied: boolean;
}

export interface OptimizationHistoryDetail extends OptimizationHistoryItem {
  constraints: Partial<BlendingConstraints>;
  request_payload: OptimizationRequest;
  result_payload: OptimizationResponse | OptimizationResult;
}

/* ---------- Replacement ratio ---------- */

export interface TheoryCoalParams {
  carbon_content: number;
  hydrogen_content: number;
  ash_content: number;
  sio2_content: number;
  decomposition_heat: number;
  physical_heat: number;
}
export interface TheoryCokeParams {
  carbon_content: number;
  ash_content: number;
  sio2_content: number;
}
export interface BlastFurnaceParams {
  eta_co: number;
  slag_basicity: number;
  slag_enthalpy: number;
  wind_temperature: number;
  hot_blast_enthalpy: number;
}
export interface TheoryRatioRequest {
  coal_params: TheoryCoalParams;
  coke_params: TheoryCokeParams;
  blast_furnace_params: BlastFurnaceParams;
}
export interface TheoryRatioResponse {
  status: string;
  ratio: number;
  details: Record<string, number>;
  carbon_burning_heat?: number;
  hydrogen_saving_carbon?: number;
  decomposition_heat_consumption?: number;
  physical_heat_consumption?: number;
  hydrogen_replacement_heat?: number;
  message?: string;
}

export interface ProductionData {
  initial_coke_ratio: number;
  final_coke_ratio: number;
  initial_coal_ratio: number;
  final_coal_ratio: number;
  adjustment_factor: number;
  iron_output_change: number;
  slag_ratio_change: number;
  carbon_efficiency_change: number;
}
export interface ActualRatioRequest {
  production_data: ProductionData;
  enable_advanced: boolean;
}
export interface ActualRatioResponse {
  status: string;
  ratio: number;
  calculation_type: 'basic' | 'advanced';
  details: Record<string, number>;
  message?: string;
}

export interface ReplacementHistoryItem {
  id: number;
  date: string;
  calculation_type: 'theory' | 'actual';
  calculation_mode: 'theory' | 'basic' | 'advanced';
  ratio_value: number;
  parameter_summary: string;
}
export interface ReplacementHistoryDetail extends ReplacementHistoryItem {
  request_payload: Record<string, unknown>;
  result_payload: Record<string, unknown>;
}

/* ---------- Generic ---------- */
export interface ApiError {
  status: 'error';
  message: string;
}
