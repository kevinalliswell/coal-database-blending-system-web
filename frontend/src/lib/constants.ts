import type { BlendingConstraints, GaParams } from './types';

export const COAL_TYPES = ['无烟煤', '烟煤', '贫煤', '褐煤', '其他'] as const;

/** Coal quality fields shown across forms / detail, with labels + units. */
export interface FieldMeta {
  key: keyof import('./types').Coal;
  label: string;
  unit?: string;
  required?: boolean;
  group: 'basic' | 'proximate' | 'ultimate' | 'other';
  step?: number;
}

export const COAL_FIELDS: FieldMeta[] = [
  { key: 'name', label: '煤种名称', required: true, group: 'basic' },
  { key: 'type', label: '煤种类型', required: true, group: 'basic' },
  { key: 'supplier', label: '供应商/产地', group: 'basic' },
  { key: 'price', label: '价格', unit: '元/吨', required: true, group: 'basic', step: 0.01 },
  { key: 'calorific_value', label: '热值', unit: 'kcal/kg', required: true, group: 'proximate' },
  { key: 'ash_content', label: '灰分', unit: '%', required: true, group: 'proximate', step: 0.01 },
  { key: 'volatile_matter', label: '挥发分', unit: '%', required: true, group: 'proximate', step: 0.01 },
  { key: 'fixed_carbon', label: '固定碳', unit: '%', required: true, group: 'proximate', step: 0.01 },
  { key: 'total_sulfur', label: '全硫', unit: '%', required: true, group: 'proximate', step: 0.01 },
  { key: 'moisture', label: '全水分', unit: '%', group: 'proximate', step: 0.01 },
  { key: 'mad', label: '空干基水分', unit: '%', group: 'proximate', step: 0.01 },
  { key: 'hgi', label: '可磨性 HGI', group: 'other' },
  { key: 'burnout_rate', label: '燃尽率', unit: '%', group: 'other', step: 0.01 },
  { key: 'carbon_content', label: '含碳量 C', unit: '%', group: 'ultimate', step: 0.01 },
  { key: 'hydrogen_content', label: '含氢量 H', unit: '%', group: 'ultimate', step: 0.01 },
  { key: 'nitrogen_content', label: '含氮量 N', unit: '%', group: 'ultimate', step: 0.01 },
];

export const DEFAULT_CONSTRAINTS: BlendingConstraints = {
  heat_target: 6800,
  heat_min: 6000,
  heat_max: 7800,
  ash_min: 0,
  ash_max: 20,
  volatile_min: 8,
  volatile_max: 40,
  fixed_carbon_min: 50,
  fixed_carbon_max: 85,
  sulfur_min: 0,
  sulfur_max: 1.2,
  price_min: 0,
  price_max: 1500,
  ratio_constraints: {},
};

/** The process-window constraint rows, driving the constraints UI. */
export const CONSTRAINT_ROWS: {
  key: string;
  label: string;
  unit: string;
  min: keyof BlendingConstraints;
  max: keyof BlendingConstraints;
  metric: keyof import('./types').ParetoSolution | 'total_price' | 'total_heat';
  step?: number;
}[] = [
  { key: 'heat', label: '热值', unit: 'kcal/kg', min: 'heat_min', max: 'heat_max', metric: 'total_heat' },
  { key: 'ash', label: '灰分', unit: '%', min: 'ash_min', max: 'ash_max', metric: 'total_ash', step: 0.1 },
  { key: 'volatile', label: '挥发分', unit: '%', min: 'volatile_min', max: 'volatile_max', metric: 'total_volatile', step: 0.1 },
  { key: 'fixed_carbon', label: '固定碳', unit: '%', min: 'fixed_carbon_min', max: 'fixed_carbon_max', metric: 'total_fixed_carbon', step: 0.1 },
  { key: 'sulfur', label: '硫分', unit: '%', min: 'sulfur_min', max: 'sulfur_max', metric: 'total_sulfur', step: 0.01 },
  { key: 'price', label: '价格', unit: '元/吨', min: 'price_min', max: 'price_max', metric: 'total_price' },
];

export const DEFAULT_GA: GaParams = {
  population_size: 500,
  max_generations: 3000,
  mutation_rate: 0.2,
  crossover_rate: 0.85,
  tournament_size: 7,
  early_stopping_patience: 200,
  adaptive_mutation: true,
  convergence_threshold: 1e-6,
  pareto_solution_limit: 20,
};

/** Named presets for the effective NSGA-II controls. */
export interface GaPreset {
  id: 'fast' | 'balanced' | 'fine';
  label: string;
  desc: string;
  params: Partial<GaParams>;
}
export const GA_PRESETS: GaPreset[] = [
  {
    id: 'fast',
    label: '快速',
    desc: '小种群 · 少迭代，秒级出解，适合快速试算',
    params: { population_size: 200, max_generations: 800, early_stopping_patience: 100 },
  },
  {
    id: 'balanced',
    label: '标准',
    desc: '默认配置，兼顾精度与速度',
    params: { population_size: 500, max_generations: 3000, early_stopping_patience: 200 },
  },
  {
    id: 'fine',
    label: '精细',
    desc: '大种群 · 多迭代，追求最优 Pareto 前沿',
    params: { population_size: 900, max_generations: 6000, early_stopping_patience: 400 },
  },
];

export const GA_FIELDS: { key: keyof GaParams; label: string; hint: string; min: number; max: number; step?: number }[] = [
  { key: 'population_size', label: '种群大小', hint: '影响搜索广度与耗时', min: 50, max: 2000 },
  { key: 'max_generations', label: '最大迭代次数', hint: '算法最多进化多少代', min: 100, max: 10000 },
  { key: 'mutation_rate', label: '变异率', hint: '基因变异概率', min: 0, max: 1, step: 0.01 },
  { key: 'crossover_rate', label: '交叉率', hint: '个体交叉概率', min: 0, max: 1, step: 0.01 },
  { key: 'tournament_size', label: '锦标赛大小', hint: '父代选择规模', min: 2, max: 20 },
  { key: 'early_stopping_patience', label: '早停耐心值', hint: '连续无改进代数上限', min: 50, max: 1000 },
  { key: 'random_seed', label: '随机种子', hint: '相同输入和种子可复现；留空自动生成', min: 0, max: 4294967295 },
  { key: 'convergence_threshold', label: '收敛阈值', hint: '归一化目标及折中方向的改善阈值', min: 0, max: 1, step: 0.000001 },
  { key: 'pareto_solution_limit', label: '展示方案数', hint: '仅控制展示数量，不改变推荐', min: 1, max: 2000 },
];

export const OPTIMIZATION_TARGET = '多目标Pareto最优';
