import type {
  ActualRatioRequest,
  ActualRatioResponse,
  BlendingConstraints,
  Coal,
  CoalDraft,
  ConstraintViolation,
  OptimizationHistoryDetail,
  OptimizationHistoryItem,
  OptimizationRequest,
  OptimizationResponse,
  OptimizationResult,
  ParetoSolution,
  ReplacementHistoryDetail,
  ReplacementHistoryItem,
  TheoryRatioRequest,
  TheoryRatioResponse,
} from '../types';
import { DEFAULT_CONSTRAINTS } from '../constants';
import { seedCoals } from './seed';

/* ------------------------------------------------------------------ */
/* Persistent in-memory store                                          */
/* ------------------------------------------------------------------ */

const STORE_KEY = 'cbos_mock_store_v1';

interface Store {
  coals: Coal[];
  nextCoalId: number;
  optHistory: OptimizationHistoryDetail[];
  repHistory: ReplacementHistoryDetail[];
  nextOptId: number;
  nextRepId: number;
}

function load(): Store {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw) as Store;
  } catch {
    /* ignore */
  }
  const coals = seedCoals();
  return {
    coals,
    nextCoalId: coals.length + 1,
    optHistory: [],
    repHistory: [],
    nextOptId: 1,
    nextRepId: 1,
  };
}

let store = load();

function persist() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  } catch {
    /* ignore quota */
  }
}

export function resetMockStore() {
  localStorage.removeItem(STORE_KEY);
  store = load();
  persist();
}

/* ------------------------------------------------------------------ */
/* Small utilities                                                     */
/* ------------------------------------------------------------------ */

function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const nowIso = () => new Date().toISOString();
const nowStr = () => new Date().toISOString().replace('T', ' ').slice(0, 19);

/* ------------------------------------------------------------------ */
/* Coal CRUD                                                           */
/* ------------------------------------------------------------------ */

export function mockListCoals(params: { page: number; page_size: number; search: string; type: string }) {
  let rows = store.coals.slice();
  const q = params.search.trim().toLowerCase();
  if (q) {
    rows = rows.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.type.toLowerCase().includes(q) ||
        (c.supplier ?? '').toLowerCase().includes(q)
    );
  }
  if (params.type) rows = rows.filter((c) => c.type === params.type);
  const total = rows.length;
  const size = params.page_size;
  let data = rows;
  let page = params.page;
  let totalPages = 1;
  if (size > 0) {
    totalPages = Math.max(1, Math.ceil(total / size));
    page = Math.min(Math.max(1, params.page), totalPages);
    data = rows.slice((page - 1) * size, page * size);
  }
  return {
    status: 'success',
    data,
    pagination: { page, page_size: size, total, total_pages: totalPages },
  };
}

export function mockGetCoal(id: number): Coal | null {
  return store.coals.find((c) => c.id === id) ?? null;
}

export function mockCoalTypes(): string[] {
  return Array.from(new Set(store.coals.map((c) => c.type)));
}

function normalizeDraft(d: Partial<CoalDraft>): Partial<Coal> {
  const out: Partial<Coal> = { ...d };
  if (d.moisture !== undefined) out.total_moisture = d.moisture as number;
  if (d.mad !== undefined) out.air_dry_moisture = d.mad as number;
  return out;
}

export function mockCreateCoal(d: CoalDraft): Coal {
  if (store.coals.some((c) => c.name === d.name)) {
    throw { status: 409, message: '煤种名称已存在' };
  }
  const coal: Coal = {
    id: store.nextCoalId++,
    created_at: nowIso(),
    updated_at: nowIso(),
    total_moisture: d.moisture ?? null,
    air_dry_moisture: d.mad ?? null,
    ...normalizeDraft(d),
  } as Coal;
  coal.moisture = coal.total_moisture;
  coal.mad = coal.air_dry_moisture;
  store.coals.unshift(coal);
  persist();
  return coal;
}

export function mockUpdateCoal(id: number, d: Partial<CoalDraft>): Coal {
  const coal = store.coals.find((c) => c.id === id);
  if (!coal) throw { status: 404, message: '煤种不存在' };
  if (d.name && d.name !== coal.name && store.coals.some((c) => c.name === d.name)) {
    throw { status: 409, message: '煤种名称已存在' };
  }
  Object.assign(coal, normalizeDraft(d));
  coal.moisture = coal.total_moisture;
  coal.mad = coal.air_dry_moisture;
  coal.updated_at = nowIso();
  persist();
  return coal;
}

export function mockDeleteCoal(id: number) {
  const idx = store.coals.findIndex((c) => c.id === id);
  if (idx < 0) throw { status: 404, message: '煤种不存在' };
  store.coals.splice(idx, 1);
  persist();
}

export function mockBatchDelete(ids: number[]) {
  store.coals = store.coals.filter((c) => !ids.includes(c.id));
  persist();
  return ids.length;
}

const CSV_HEADERS = [
  '煤种名称,煤种类型,供应商/产地,价格(元/吨),热值(kcal/kg),灰分(%),挥发分(%),固定碳(%),全硫(%),全水分(%),空干基水分(%),可磨性HGI,燃尽率(%),含碳量C(%),含氢量H(%),含氮量N(%)',
];

export function mockExportCsv(ids: number[] | null): Blob {
  const rows = ids ? store.coals.filter((c) => ids.includes(c.id)) : store.coals;
  const lines = [CSV_HEADERS[0]];
  for (const c of rows) {
    lines.push(
      [
        c.name,
        c.type,
        c.supplier ?? '',
        c.price,
        c.calorific_value,
        c.ash_content,
        c.volatile_matter,
        c.fixed_carbon,
        c.total_sulfur,
        c.total_moisture ?? '',
        c.air_dry_moisture ?? '',
        c.hgi ?? '',
        c.burnout_rate ?? '',
        c.carbon_content ?? '',
        c.hydrogen_content ?? '',
        c.nitrogen_content ?? '',
      ].join(',')
    );
  }
  return new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8' });
}

export function mockTemplateCsv(): Blob {
  return new Blob(['﻿' + CSV_HEADERS[0] + '\n'], { type: 'text/csv;charset=utf-8' });
}

export async function mockUpload(file: File) {
  const text = await file.text();
  const lines = text.replace(/^﻿/, '').split(/\r?\n/).filter((l) => l.trim());
  let created = 0;
  let updated = 0;
  let skipped = 0;
  const errors: string[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(',');
    const name = cells[0]?.trim();
    if (!name) {
      skipped++;
      continue;
    }
    const draft: CoalDraft = {
      name,
      analysis_basis: 'unknown',
      calorific_basis: 'unknown',
      price_basis: 'unknown',
      calorific_type: 'unknown',
      type: cells[1]?.trim() || '其他',
      supplier: cells[2]?.trim() || null,
      price: +cells[3] || 0,
      calorific_value: +cells[4] || 0,
      ash_content: +cells[5] || 0,
      volatile_matter: +cells[6] || 0,
      fixed_carbon: +cells[7] || 0,
      total_sulfur: +cells[8] || 0,
      moisture: cells[9] ? +cells[9] : null,
      mad: cells[10] ? +cells[10] : null,
      hgi: cells[11] ? +cells[11] : null,
      burnout_rate: cells[12] ? +cells[12] : null,
      carbon_content: cells[13] ? +cells[13] : null,
      hydrogen_content: cells[14] ? +cells[14] : null,
      nitrogen_content: cells[15] ? +cells[15] : null,
    };
    try {
      const existing = store.coals.find((c) => c.name === name);
      if (existing) {
        mockUpdateCoal(existing.id, draft);
        updated++;
      } else {
        mockCreateCoal(draft);
        created++;
      }
    } catch (e) {
      errors.push(`${name}: ${(e as { message?: string }).message ?? '导入失败'}`);
      skipped++;
    }
  }
  return {
    status: created + updated > 0 ? 'success' : 'error',
    message: `文件上传完成：新增 ${created} 条，更新 ${updated} 条，跳过 ${skipped} 条`,
    filename: file.name,
    coal_count: created + updated,
    created_count: created,
    updated_count: updated,
    skipped_count: skipped,
    errors: errors.slice(0, 20),
  };
}

/* ------------------------------------------------------------------ */
/* Optimization (synthetic NSGA-II)                                    */
/* ------------------------------------------------------------------ */

interface Candidate {
  ratios: number[];
  price: number;
  heat: number;
  ash: number;
  volatile: number;
  fixed_carbon: number;
  sulfur: number;
  qp: number;
}

function blend(coals: Coal[], w: number[]) {
  const acc = { price: 0, heat: 0, ash: 0, volatile: 0, fixed_carbon: 0, sulfur: 0 };
  coals.forEach((c, i) => {
    acc.price += c.price * w[i];
    acc.heat += c.calorific_value * w[i];
    acc.ash += c.ash_content * w[i];
    acc.volatile += c.volatile_matter * w[i];
    acc.fixed_carbon += c.fixed_carbon * w[i];
    acc.sulfur += c.total_sulfur * w[i];
  });
  return acc;
}

/** sample a valid ratio vector within [min,max] fractions summing to 1 */
function sampleRatios(mins: number[], maxs: number[], rand: () => number): number[] | null {
  const n = mins.length;
  const base = mins.slice();
  let remaining = 1 - base.reduce((a, b) => a + b, 0);
  if (remaining < -1e-9) return null;
  const headroom = maxs.map((m, i) => m - base[i]);
  const totalHead = headroom.reduce((a, b) => a + b, 0);
  if (remaining > totalHead + 1e-9) return null;
  // distribute `remaining` across coals proportional to random * headroom
  for (let pass = 0; pass < 3 && remaining > 1e-9; pass++) {
    const weights = headroom.map((h, i) => (base[i] < maxs[i] ? h * (0.2 + rand()) : 0));
    const wsum = weights.reduce((a, b) => a + b, 0);
    if (wsum <= 1e-9) break;
    for (let i = 0; i < n; i++) {
      const give = Math.min(maxs[i] - base[i], (remaining * weights[i]) / wsum);
      base[i] += give;
    }
    remaining = 1 - base.reduce((a, b) => a + b, 0);
  }
  return base;
}

function within(v: number, lo: number, hi: number) {
  return v >= lo - 1e-6 && v <= hi + 1e-6;
}

export async function mockOptimize(req: OptimizationRequest): Promise<OptimizationResponse> {
  const coals = (req.selected_coal_ids ?? [])
    .map((id) => store.coals.find((c) => c.id === id))
    .filter((c): c is Coal => !!c);
  if (coals.length < 2) {
    throw { status: 400, message: '至少选择两种煤' };
  }
  const c: BlendingConstraints = { ...DEFAULT_CONSTRAINTS, ...req.constraints } as BlendingConstraints;
  const rc = req.constraints.ratio_constraints ?? {};
  const mins = coals.map((co) => (rc[String(co.id)]?.min ?? 0) / 100);
  const maxs = coals.map((co) => (rc[String(co.id)]?.max ?? 100) / 100);

  const rand = rng(Date.now() & 0xffffffff);
  const feasible: Candidate[] = [];
  const N = 520;
  for (let i = 0; i < N; i++) {
    const w = sampleRatios(mins, maxs, rand);
    if (!w) break;
    const b = blend(coals, w);
    const ok =
      within(b.heat, c.heat_min, c.heat_max) &&
      within(b.ash, c.ash_min, c.ash_max) &&
      within(b.volatile, c.volatile_min, c.volatile_max) &&
      within(b.fixed_carbon, c.fixed_carbon_min, c.fixed_carbon_max) &&
      within(b.sulfur, c.sulfur_min, c.sulfur_max) &&
      within(b.price, c.price_min, c.price_max);
    if (!ok) continue;
    const heatSpan = Math.max(1, c.heat_max - c.heat_min);
    const qp = Math.abs(b.heat - (c.heat_target ?? (c.heat_min + c.heat_max) / 2)) / heatSpan + b.sulfur * 0.05 + b.ash * 0.002;
    feasible.push({ ratios: w, ...b, qp });
  }

  const iterations = Math.min(req.ga_params.max_generations, 120 + Math.floor(rand() * 340));
  const time_taken = +(0.6 + rand() * 2.4).toFixed(2);
  const timestamp = nowIso();

  if (feasible.length === 0) {
    const result = infeasibleResult(coals, c, req.optimization_target, timestamp);
    return { status: 'no_feasible_solution', message: '当前约束与所选煤种组合下不存在可行混煤方案', result };
  }

  // Pareto front on (price ↓, qp ↓)
  const front = feasible.filter(
    (a) => !feasible.some((b) => b !== a && b.price <= a.price && b.qp <= a.qp && (b.price < a.price || b.qp < a.qp))
  );
  front.sort((a, b) => a.price - b.price);
  const capped = front.slice(0, 20);

  // recommended = closest to ideal point in normalized (price, qp)
  const pr = capped.map((s) => s.price);
  const qq = capped.map((s) => s.qp);
  const pMin = Math.min(...pr);
  const pMax = Math.max(...pr);
  const qMin = Math.min(...qq);
  const qMax = Math.max(...qq);
  const normDist = (s: Candidate) => {
    const np = pMax > pMin ? (s.price - pMin) / (pMax - pMin) : 0;
    const nq = qMax > qMin ? (s.qp - qMin) / (qMax - qMin) : 0;
    return Math.hypot(np, nq);
  };
  let best = capped[0];
  let bestD = Infinity;
  capped.forEach((s) => {
    const d = normDist(s);
    if (d < bestD) {
      bestD = d;
      best = s;
    }
  });

  const names = coals.map((co) => co.name);
  const toSolution = (s: Candidate, idx: number): ParetoSolution => ({
    solution_id: `pareto_${String(idx + 1).padStart(3, '0')}`,
    rank: 1,
    crowding_distance: +(0.3 + rand()).toFixed(3),
    coal_names: names,
    optimal_ratios: s.ratios,
    blending_ratio: Object.fromEntries(names.map((n, i) => [n, s.ratios[i]])),
    total_price: +s.price.toFixed(2),
    total_heat: Math.round(s.heat),
    total_ash: +s.ash.toFixed(2),
    total_volatile: +s.volatile.toFixed(2),
    total_fixed_carbon: +s.fixed_carbon.toFixed(2),
    total_sulfur: +s.sulfur.toFixed(3),
    performance_price_ratio: +((s.heat / s.price) * 100).toFixed(2),
    quality_penalty: +s.qp.toFixed(4),
    objective_values: { cost: +s.price.toFixed(2), heat: Math.round(s.heat), quality_penalty: +s.qp.toFixed(4) },
    is_feasible: true,
    violation_score: 0,
    constraint_violations: [],
    active_constraints: activeConstraints(s, c),
  });

  const pareto_solutions = capped.map(toSolution);
  const recommended = toSolution(best, capped.indexOf(best));

  const result: OptimizationResult = {
    objective_type: 'pci_pareto_nsga2_v1',
    optimization_target: '多目标Pareto最优',
    coal_names: names,
    optimal_ratios: best.ratios,
    blending_ratio: Object.fromEntries(names.map((n, i) => [n, best.ratios[i]])),
    total_price: +best.price.toFixed(2),
    total_heat: Math.round(best.heat),
    total_ash: +best.ash.toFixed(2),
    total_volatile: +best.volatile.toFixed(2),
    total_fixed_carbon: +best.fixed_carbon.toFixed(2),
    total_sulfur: +best.sulfur.toFixed(3),
    performance_price_ratio: +((best.heat / best.price) * 100).toFixed(2),
    iterations,
    time_taken,
    fitness_value: +best.qp.toFixed(4),
    quality_penalty: +best.qp.toFixed(4),
    is_feasible: true,
    constraints_satisfied: true,
    constraint_violations: [],
    violation_score: 0,
    active_constraints: recommended.active_constraints ?? [],
    diagnosis: [
      '线性可行性预检查通过，并生成了最低成本可行 seed',
      `NSGA-II 生成 ${pareto_solutions.length} 个非支配 Pareto 候选方案`,
    ],
    objective_values: { cost: +best.price.toFixed(2), heat: Math.round(best.heat), quality_penalty: +best.qp.toFixed(4) },
    recommended_solution: recommended,
    pareto_solutions,
    timestamp,
  };

  // save history
  const item: OptimizationHistoryDetail = {
    id: store.nextOptId++,
    timestamp,
    date: nowStr(),
    coal_names: names,
    optimal_ratios: best.ratios,
    ratio_items: names.map((n, i) => ({ coal_name: n, ratio: best.ratios[i], ratio_percent: best.ratios[i] * 100 })),
    total_price: result.total_price,
    total_heat: result.total_heat,
    total_ash: result.total_ash,
    total_volatile: result.total_volatile,
    total_fixed_carbon: result.total_fixed_carbon,
    total_sulfur: result.total_sulfur,
    performance_price_ratio: result.performance_price_ratio ?? null,
    iterations,
    time_taken,
    fitness_value: result.fitness_value,
    constraints_satisfied: true,
    constraints: req.constraints,
    request_payload: req,
    result_payload: result,
  };
  store.optHistory.unshift(item);
  persist();

  return { status: 'success', message: '多目标Pareto优化完成', history_saved: true, result };
}

function activeConstraints(s: Candidate, c: BlendingConstraints): string[] {
  const out: string[] = [];
  const near = (v: number, lo: number, hi: number, span: number) => {
    if (Math.abs(v - lo) < span * 0.04) return 'min';
    if (Math.abs(v - hi) < span * 0.04) return 'max';
    return null;
  };
  const checks: [number, number, number, string][] = [
    [s.heat, c.heat_min, c.heat_max, '热值'],
    [s.ash, c.ash_min, c.ash_max, '灰分'],
    [s.sulfur, c.sulfur_min, c.sulfur_max, '硫分'],
    [s.price, c.price_min, c.price_max, '价格'],
  ];
  for (const [v, lo, hi, label] of checks) {
    const n = near(v, lo, hi, Math.max(1, hi - lo));
    if (n === 'min') out.push(`${label}下限`);
    if (n === 'max') out.push(`${label}上限`);
  }
  return out;
}

function infeasibleResult(
  coals: Coal[],
  c: BlendingConstraints,
  target: string,
  timestamp: string
): OptimizationResult {
  // identify the constraint most likely conflicting: compare achievable heat range
  const heats = coals.map((x) => x.calorific_value);
  const violations: ConstraintViolation[] = [];
  if (Math.max(...heats) < c.heat_min) violations.push({ label: '热值下限', detail: '所选煤种的最高热值仍低于热值下限' });
  if (Math.min(...heats) > c.heat_max) violations.push({ label: '热值上限', detail: '所选煤种的最低热值仍高于热值上限' });
  const sul = coals.map((x) => x.total_sulfur);
  if (Math.min(...sul) > c.sulfur_max) violations.push({ label: '硫分上限', detail: '所选煤种的最低硫分仍高于硫分上限' });
  if (violations.length === 0)
    violations.push({ label: '约束组合', detail: '多项工艺窗口相互挤压，可行域为空，建议放宽最紧的一项' });
  return {
    objective_type: 'pci_pareto_nsga2_v1',
    optimization_target: target,
    coal_names: coals.map((x) => x.name),
    optimal_ratios: [],
    blending_ratio: {},
    total_price: NaN as unknown as number,
    total_heat: NaN as unknown as number,
    total_ash: NaN as unknown as number,
    total_volatile: NaN as unknown as number,
    total_fixed_carbon: NaN as unknown as number,
    total_sulfur: NaN as unknown as number,
    iterations: 0,
    time_taken: 0,
    fitness_value: NaN as unknown as number,
    quality_penalty: NaN as unknown as number,
    is_feasible: false,
    constraints_satisfied: false,
    constraint_violations: violations,
    violation_score: null,
    active_constraints: [],
    diagnosis: ['约束与当前煤种集合存在冲突，未找到可行混煤方案', '建议放宽表中标红的关键约束或增选煤种'],
    objective_values: { cost: 0, heat: 0, quality_penalty: 0 },
    recommended_solution: {
      solution_id: 'none',
      coal_names: coals.map((x) => x.name),
      optimal_ratios: [],
      total_price: 0,
      total_heat: 0,
      total_ash: 0,
      total_volatile: 0,
      total_fixed_carbon: 0,
      total_sulfur: 0,
      quality_penalty: 0,
      is_feasible: false,
    },
    pareto_solutions: [],
    timestamp,
  };
}

export function mockOptHistory(): OptimizationHistoryItem[] {
  return store.optHistory.map((h) => ({ ...h }));
}
export function mockOptHistoryDetail(id: number): OptimizationHistoryDetail | null {
  return store.optHistory.find((h) => h.id === id) ?? null;
}

/* ------------------------------------------------------------------ */
/* Replacement ratio (illustrative formulas)                          */
/* ------------------------------------------------------------------ */

export function mockTheoryRatio(req: TheoryRatioRequest): TheoryRatioResponse {
  const { coal_params: p, coke_params: k, blast_furnace_params: bf } = req;
  const blastEnthalpy = bf.hot_blast_enthalpy ?? 1.3 * bf.wind_temperature;
  const carbonHeat = 1.2 * blastEnthalpy + 9794 - 2758;
  const etaH = Math.max(0, Math.min(1, 1.41 * bf.eta_co - 1.07 * bf.eta_co ** 2));
  const hydrogen_saving_carbon = p.hydrogen_content * etaH * (6 + 62222 / carbonHeat);
  const coalSlagCarbon = p.ash_content * (1 + p.sio2_content * bf.slag_basicity) * bf.slag_enthalpy / carbonHeat;
  const heatCarbon = (p.decomposition_heat + p.physical_heat) * 4.184 / carbonHeat;
  const cokeSlagCarbon = k.ash_content * (1 + k.sio2_content * bf.slag_basicity) * bf.slag_enthalpy / carbonHeat;
  const numerator = p.carbon_content + hydrogen_saving_carbon - coalSlagCarbon - heatCarbon;
  const denominator = k.carbon_content - cokeSlagCarbon;
  if (!(denominator > 0)) throw { status: 400, message: '置换比计算错误: 焦炭有效碳量必须大于零' };
  const ratio = numerator / denominator;
  const details: Record<string, number> = {
    煤粉含碳量: r6(p.carbon_content),
    煤粉中氢参加还原而节约的碳量: r6(hydrogen_saving_carbon),
    煤粉中灰分造渣所消耗的碳: r6(coalSlagCarbon),
    '煤粉分解热和加热至1500°C物理热所消耗的碳': r6(heatCarbon),
    焦炭含碳量: r6(k.carbon_content),
    焦炭中灰分造渣所消耗的碳: r6(cokeSlagCarbon),
    置换比分子: r6(numerator),
    置换比分母: r6(denominator),
    理论置换比: r6(ratio),
  };
  const res: TheoryRatioResponse = {
    status: 'success',
    ratio: r6(ratio),
    details,
    carbon_burning_heat: r6(carbonHeat),
    hydrogen_saving_carbon: r6(hydrogen_saving_carbon),
    decomposition_heat_consumption: r6(p.decomposition_heat),
    physical_heat_consumption: r6(p.physical_heat),
    total_heat_consumption: r6(p.decomposition_heat + p.physical_heat),
    effective_hot_blast_enthalpy: r6(blastEnthalpy),
    hot_blast_enthalpy_source: bf.hot_blast_enthalpy == null ? 'temperature_estimate' : 'provided',
    hydrogen_replacement_heat: 62222,
  };
  saveRep('theory', 'theory', res.ratio, req, res, theorySummary(p, k, bf));
  return res;
}

export function mockActualRatio(req: ActualRatioRequest): ActualRatioResponse {
  const d = req.production_data;
  const cokeReduction = d.initial_coke_ratio - d.final_coke_ratio;
  const coalIncrease = d.final_coal_ratio - d.initial_coal_ratio;
  if (Math.abs(coalIncrease) < 1e-9) throw { status: 500, message: '煤比增加量不能为 0' };
  const basic = (cokeReduction + d.adjustment_factor) / coalIncrease;
  const details: Record<string, number> = {
    '调整前焦比(kg/t)': r2(d.initial_coke_ratio),
    '调整后焦比(kg/t)': r2(d.final_coke_ratio),
    '调整前煤比(kg/t)': r2(d.initial_coal_ratio),
    '调整后煤比(kg/t)': r2(d.final_coal_ratio),
    '焦比减少量(kg/t)': r2(cokeReduction),
    '煤比增加量(kg/t)': r2(coalIncrease),
    '修正系数(kg/t)': r2(d.adjustment_factor),
    实际置换比: r4(basic),
  };
  let ratio = basic;
  let calculation_type: 'basic' | 'advanced' = 'basic';
  if (req.enable_advanced) {
    calculation_type = 'advanced';
    const outputCorrection = d.iron_output_change * 0.05;
    const slagCorrection = d.slag_ratio_change * 0.02;
    const efficiencyCorrection = d.carbon_efficiency_change * 0.1;
    const total = outputCorrection + slagCorrection + efficiencyCorrection;
    ratio = basic + total / coalIncrease;
    Object.assign(details, {
      '铁水产量变化(t/d)': r2(d.iron_output_change),
      铁水产量修正项: r4(outputCorrection),
      '渣比变化(kg/t)': r2(d.slag_ratio_change),
      渣比修正项: r4(slagCorrection),
      '碳利用效率变化(%)': r2(d.carbon_efficiency_change),
      碳效率修正项: r4(efficiencyCorrection),
      总修正量: r4(total),
      修正后实际置换比: r4(ratio),
    });
  }
  const res: ActualRatioResponse = { status: 'success', ratio: r4(ratio), calculation_type, details };
  saveRep('actual', calculation_type, res.ratio, req, res, actualSummary(d));
  return res;
}

function saveRep(
  type: 'theory' | 'actual',
  mode: 'theory' | 'basic' | 'advanced',
  ratio: number,
  req: unknown,
  res: unknown,
  summary: string
) {
  const item: ReplacementHistoryDetail = {
    id: store.nextRepId++,
    date: nowStr(),
    calculation_type: type,
    calculation_mode: mode,
    ratio_value: ratio,
    parameter_summary: summary,
    request_payload: req as Record<string, unknown>,
    result_payload: res as Record<string, unknown>,
  };
  store.repHistory.unshift(item);
  persist();
}

function theorySummary(p: TheoryRatioRequest['coal_params'], k: TheoryRatioRequest['coke_params'], bf: TheoryRatioRequest['blast_furnace_params']) {
  return `煤粉含碳 ${(p.carbon_content * 100).toFixed(2)}%，焦炭含碳 ${(k.carbon_content * 100).toFixed(2)}%，煤气利用率 ${bf.eta_co}`;
}
function actualSummary(d: ActualRatioRequest['production_data']) {
  return `焦比 ${d.initial_coke_ratio}→${d.final_coke_ratio}，煤比 ${d.initial_coal_ratio}→${d.final_coal_ratio}`;
}

export function mockRepHistory(): ReplacementHistoryItem[] {
  return store.repHistory.map(({ request_payload: _r, result_payload: _p, ...rest }) => rest);
}
export function mockRepHistoryDetail(id: number): ReplacementHistoryDetail | null {
  return store.repHistory.find((h) => h.id === id) ?? null;
}

const r2 = (v: number) => +v.toFixed(2);
const r4 = (v: number) => +v.toFixed(4);
const r6 = (v: number) => +v.toFixed(6);

export function mockHealth() {
  return { status: 'ok', app: '煤粉数据库管理及配煤优化控制台', storage_mode: 'mock', coal_count: store.coals.length };
}
