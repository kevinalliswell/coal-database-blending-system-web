import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { exportCurrentReport, runOptimization } from '../lib/api';
import { buildExportPayload, captureRequest, dataValidationLabel, matchesRequest, resolveDataValidation } from '../lib/blendingResult';
import type {
  BlendingConstraints,
  Coal,
  GaParams,
  OptimizationResponse,
  OptimizationRequest,
  ParetoSolution,
} from '../lib/types';
import {
  CONSTRAINT_ROWS,
  DEFAULT_CONSTRAINTS,
  GA_PRESETS,
  OPTIMIZATION_TARGET,
  type GaPreset,
} from '../lib/constants';
import type { ReactNode } from 'react';
import { Icon, type IconName } from '../components/ui/Icon';
import { EmptyState, Segmented, StatusPill } from '../components/ui/bits';
import { GaDrawer } from '../components/blending/GaDrawer';
import { RatioDonut, MarginRadar, ParetoScatter } from '../components/blending/charts';
import { useChartPalette } from '../components/ui/Chart';
import { useToast } from '../components/ui/Toast';
import { downloadBlob, fixed, num, stamp } from '../lib/format';
import { useSession } from '../lib/session';
import { listAssays, getSettings, basisLabel, heatLabel, heatDisplay, heatCanonical, type Assay, type Settings } from '../lib/v2';
import { useDebounced } from '../hooks/useDebounced';

type BlendCoal = Coal & { assay: Assay };
interface Config {
  settingsVersion: number;
  selectedIds: number[];
  constraints: BlendingConstraints;
  gaParams: GaParams;
  presetId: GaPreset['id'] | 'custom';
}
function loadConfig(key: string, settings: Settings): Config {
  const defaults: Config = {settingsVersion: settings.version, selectedIds: [], constraints: {...settings.constraints, ratio_constraints: {}}, gaParams: settings.ga_params, presetId: 'custom'};
  try {
    const saved = JSON.parse(localStorage.getItem(key) || 'null');
    if (saved && saved.settingsVersion === settings.version) return {...defaults, ...saved};
  } catch { /* A damaged draft does not block a new calculation. */ }
  return defaults;
}
export default function SmartBlending() {
  const settingsQ = useQuery({queryKey: ['settings'], queryFn: getSettings, refetchInterval: 30_000});
  if (settingsQ.isPending) return <div className="page" role="status">正在读取系统计算口径…</div>;
  if (settingsQ.isError) return <div className="page" role="alert">{settingsQ.error.message}</div>;
  return <BlendingWorkspace settings={settingsQ.data} />;
}
function BlendingWorkspace({settings}: {settings: Settings}) {
  const toast = useToast();
  const {user, can} = useSession();
  const storageKey = `cbos_blending_v2_user_${user.id}`;
  const [cfg, setCfg] = useState<Config>(() => loadConfig(storageKey, settings));
  const [initialSettings] = useState(settings);
  const settingsChanged = cfg.settingsVersion !== settings.version;
  const heatUnit = initialSettings.heat_unit;
  const [gaOpen, setGaOpen] = useState(false);
  const [completed, setCompleted] = useState<{ response: OptimizationResponse; request: OptimizationRequest } | null>(null);
  const [activeId, setActiveId] = useState<string>('');
  const [progress, setProgress] = useState(0);
  const resultRef = useRef<HTMLDivElement>(null);

  const coalsQ = useQuery({queryKey: ['assays', cfg.settingsVersion], queryFn: () => listAssays(cfg.settingsVersion), enabled: !settingsChanged});
  const allCoals = useMemo(() => (settingsChanged ? [] : coalsQ.data || []).map(a => ({
    id: a.id, name: a.label, type: a.coal_type, assay: a,
    price: NaN, calorific_value: NaN, ash_content: NaN, volatile_matter: NaN, fixed_carbon: NaN, total_sulfur: NaN,
    ...a.eligibility.blending.values,
  } as BlendCoal)), [coalsQ.data, settingsChanged]);
  const coalById = useMemo(() => new Map(allCoals.map(c => [c.id, c])), [allCoals]);
  const selectedCoals = cfg.selectedIds.map(id => coalById.get(id)).filter((c): c is BlendCoal => !!c);
  useEffect(() => { try { localStorage.setItem(storageKey, JSON.stringify(cfg)); } catch { /* Storage may be disabled. */ } }, [cfg, storageKey]);

  const patchConstraint = (k: keyof BlendingConstraints, v: number) =>
    setCfg((c) => ({ ...c, constraints: { ...c.constraints, [k]: v } }));

  const getBound = (id: number) => cfg.constraints.ratio_constraints[String(id)] ?? { min: 0, max: 100 };
  const setBound = (id: number, part: 'min' | 'max', v: number) =>
    setCfg((c) => ({
      ...c,
      constraints: {
        ...c.constraints,
        ratio_constraints: { ...c.constraints.ratio_constraints, [String(id)]: { ...getBound(id), [part]: v } },
      },
    }));

  const toggleCoal = (id: number) =>
    setCfg((c) => ({
      ...c,
      selectedIds: c.selectedIds.includes(id) ? c.selectedIds.filter((x) => x !== id) : [...c.selectedIds, id],
    }));

  /* ---- preflight ---- */
  const sumMin = selectedCoals.reduce((a, c) => a + getBound(c.id).min, 0);
  const sumMax = selectedCoals.reduce((a, c) => a + getBound(c.id).max, 0);
  const issues: string[] = [];
  if (!can('calculate')) issues.push('当前账号没有执行计算权限');
  if (settingsChanged) issues.push('系统设置已改变，请刷新页面并重新确认约束');
  if (coalsQ.isError) issues.push(coalsQ.error.message);
  if (selectedCoals.length !== cfg.selectedIds.length) issues.push('部分化验记录已不可用，请重新选择');
  if (new Set(selectedCoals.map(c => c.assay.batch_id)).size !== selectedCoals.length) issues.push('同一批次只能选择一份修订');
  selectedCoals.forEach(c => { if (!c.assay.eligibility.blending.eligible) issues.push(`${c.name}：${c.assay.eligibility.blending.issues.map(i => i.message).join('；')}`); });
  if (cfg.selectedIds.length < 2) issues.push('至少选择 2 种煤');
  for (const r of CONSTRAINT_ROWS) {
    const lo = cfg.constraints[r.min] as number;
    const hi = cfg.constraints[r.max] as number;
    if (lo > hi) issues.push(`${r.label}下限不能大于上限`);
  }
  if (selectedCoals.length >= 2) {
    if (sumMin > 100.0001) issues.push(`配比下限之和 ${fixed(sumMin, 1)}% 超过 100%`);
    if (sumMax < 99.9999) issues.push(`配比上限之和 ${fixed(sumMax, 1)}% 不足 100%`);
    for (const c of selectedCoals) {
      const b = getBound(c.id);
      if (b.min > b.max) issues.push(`${c.name} 配比下限不能大于上限`);
    }
  }
  const canSolve = issues.length === 0;

  /* ---- solve ---- */
  // Historical local settings may still contain the retired, unused heat target.
  const submittedConstraints = { ...cfg.constraints };
  delete submittedConstraints.heat_target;
  const currentRequest: OptimizationRequest = {
    settings_version: cfg.settingsVersion,
    components: cfg.selectedIds.map(id => ({assay_revision_id: id, min_ratio: getBound(id).min, max_ratio: getBound(id).max})),
    optimization_target: OPTIMIZATION_TARGET,
    constraints: {
      ...submittedConstraints,
      ratio_constraints: {},
    },
    ga_params: cfg.gaParams,
  };
  const result = completed && matchesRequest(completed.request, currentRequest) ? completed.response : null;
  const resultConstraints = {
    ...DEFAULT_CONSTRAINTS,
    ...completed?.request.constraints,
    ...result?.constraints,
    ...result?.input_snapshot?.constraints,
  };
  const solveMut = useMutation({
    mutationFn: runOptimization,
    onMutate: () => setCompleted(null),
    onSuccess: (res, request) => {
      const data_validation = resolveDataValidation(res.result.data_validation, request);
      setCompleted({ response: { ...res, result: { ...res.result, data_validation } }, request });
      setActiveId(res.result.recommended_solution?.solution_id ?? '');
      if (res.status === 'success' && data_validation?.status === 'unverified') toast.warn('试算完成，仅用于筛选', `生成 ${res.result.pareto_solutions.length} 个数值可行候选方案`);
      else if (res.status === 'success') toast.success('优化完成', `生成 ${res.result.pareto_solutions.length} 个 Pareto 候选方案`);
      else toast.warn('无可行方案', res.message);
      if (res.history_saved === false) toast.warn('历史记录未保存', res.warning ?? '请先导出当前报告保存结果。');
      else if (res.warning) toast.warn('参数提示', res.warning);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
    },
    onError: (e: Error) => toast.error('优化失败', e.message),
  });

  useEffect(() => {
    if (!solveMut.isPending) {
      setProgress(0);
      return;
    }
    setProgress(8);
    const t = setInterval(() => setProgress((p) => Math.min(92, p + 6 + Math.random() * 8)), 260);
    return () => clearInterval(t);
  }, [solveMut.isPending]);

  const res = result?.result ?? null;
  const solutions = res?.pareto_solutions ?? [];
  const activeSolution: ParetoSolution | null =
    solutions.find((s) => s.solution_id === activeId) ?? res?.recommended_solution ?? null;
  const feasible = res?.is_feasible ?? false;

  const applyGlobalBound = (min: number, max: number) =>
    setCfg((c) => ({
      ...c,
      constraints: {
        ...c.constraints,
        ratio_constraints: Object.fromEntries(c.selectedIds.map((id) => [String(id), { min, max }])),
      },
    }));

  const copyShare = async () => {
    if (!res || !activeSolution) return;
    const lines = [
      '【智能混煤方案】',
      `方案: ${activeSolution.solution_id}`,
      ...activeSolution.coal_names.map((n, i) => `  ${n}: ${fixed(activeSolution.optimal_ratios[i] * 100, 1)}%`),
      `吨煤成本: ¥${fixed(activeSolution.total_price, 1)}`,
      `配比质量口径: ${basisLabel(initialSettings.ratio_basis)}`,
      `热值类型: ${heatLabel(initialSettings.heat_type)}`,
      `价格口径: 元/${initialSettings.ratio_basis === 'ar' ? '收到' : '干'}吨`,
      `综合热值: ${fixed(heatDisplay(activeSolution.total_heat, heatUnit), 2)} ${heatUnit}`,
      `灰分/硫分: ${fixed(activeSolution.total_ash, 1)}% / ${fixed(activeSolution.total_sulfur, 2)}%`,
      `数值约束: ${feasible ? '满足' : '存在约束冲突'}`,
      `数据状态: ${dataValidationLabel(res.data_validation)}`,
      ...(res.data_validation?.warnings ?? []),
      '用途: 仅作配煤评估参考，不代表现场工艺验证。',
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      toast.success('已复制分享文本');
    } catch {
      toast.error('复制失败', '浏览器不支持剪贴板');
    }
  };

  const exportMut = useMutation({
    mutationFn: exportCurrentReport,
    onSuccess: (blob) => {
      const ext = blob.type.includes('json') ? 'json' : 'xlsx';
      downloadBlob(blob, `混煤优化报告_${stamp()}.${ext}`);
      toast.success('报告已导出');
    },
    onError: (e: Error) => toast.error('导出失败', e.message),
  });

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">智能混煤优化</h1>
          <p className="page__lead">选煤 → 定约束 → 配比边界 → NSGA-II 多目标求解，输出 Pareto 候选与推荐配比。</p>
        </div>
      </div>

      <section className="panel mb-20"><div className="panel__body">
        <strong>本次口径：{basisLabel(initialSettings.ratio_basis)}配比 · {heatLabel(initialSettings.heat_type)} · 元/{initialSettings.ratio_basis === 'ar' ? '收到' : '干'}吨</strong>
        <p className="text-sm text-mute">化验原值自动换算到同一口径。每个批次选一份修订，缺少相关数据的记录不能加入计算。</p>
        {settingsChanged && <p role="alert" className="text-amber">系统设置已更新。<button className="btn" onClick={() => window.location.reload()}>刷新并确认新约束</button>正在运行的计算仍保留原口径。</p>}
      </div></section>

      <div className="split">
        {/* ---------------- left workspace ---------------- */}
        <div className="col gap-18">
          {/* Step 1 — select coals */}
          <section className="panel">
            <div className="panel__body">
              <div className="step">
                <span className="step__no">1</span>
                <span className="step__title">选择批次与化验修订</span>
                <StatusPill tone={selectedCoals.length >= 2 ? 'mint' : 'mute'}>已选 {selectedCoals.length} 种</StatusPill>
              </div>
              <CoalPicker coals={allCoals} heatUnit={heatUnit} loading={coalsQ.isLoading} selected={new Set(cfg.selectedIds)} onToggle={toggleCoal} />
              {selectedCoals.length > 0 && (
                <div className="row gap-8 wrap mt-16">
                  {selectedCoals.map((c) => (
                    <span key={c.id} className="chip">
                      {c.name}
                      <span className="chip__x" onClick={() => toggleCoal(c.id)}>
                        <Icon name="x" size={12} />
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Step 2 — process constraints */}
          <section className="panel">
            <div className="panel__body">
              <div className="step">
                <span className="step__no">2</span>
                <span className="step__title">工艺约束窗口</span>
                <span className="text-xs text-mute">先锁定生产边界，再在可行域内寻优</span>
              </div>
              {/* heat window */}
              <div className="cwin">
                <div>
                  <div className="cwin__label">热值</div>
                  <div className="cwin__unit">{heatUnit}</div>
                </div>
                <div className="row gap-10 wrap">
                  <div className="minmax grow">
                    <input className="input" type="number" aria-label="热值下限" step="any" value={+heatDisplay(cfg.constraints.heat_min, heatUnit).toFixed(4)} onChange={(e) => patchConstraint('heat_min', heatCanonical(+e.target.value, heatUnit))} />
                    <span className="minmax__sep">–</span>
                    <input className="input" type="number" aria-label="热值上限" step="any" value={+heatDisplay(cfg.constraints.heat_max, heatUnit).toFixed(4)} onChange={(e) => patchConstraint('heat_max', heatCanonical(+e.target.value, heatUnit))} />
                  </div>
                </div>
              </div>
              {CONSTRAINT_ROWS.filter((r) => r.key !== 'heat').map((r) => (
                <div className="cwin" key={r.key}>
                  <div>
                    <div className="cwin__label">{r.label}</div>
                    <div className="cwin__unit">{r.unit}</div>
                  </div>
                  <div className="minmax">
                    <input
                      className="input"
                      type="number"
                      aria-label={`${r.label}下限`}
                      step={r.step ?? 1}
                      value={cfg.constraints[r.min] as number}
                      onChange={(e) => patchConstraint(r.min, +e.target.value)}
                    />
                    <span className="minmax__sep">–</span>
                    <input
                      className="input"
                      type="number"
                      aria-label={`${r.label}上限`}
                      step={r.step ?? 1}
                      value={cfg.constraints[r.max] as number}
                      onChange={(e) => patchConstraint(r.max, +e.target.value)}
                    />
                  </div>
                </div>
              ))}
              <button className="btn btn--ghost btn--sm mt-12" onClick={() => setCfg((c) => ({ ...c, constraints: { ...initialSettings.constraints, ratio_constraints: c.constraints.ratio_constraints } }))}>
                <Icon name="reset" size={14} /> 恢复默认约束
              </button>
            </div>
          </section>

          {/* Step 3 — ratio bounds */}
          {selectedCoals.length > 0 && (
            <section className="panel">
              <div className="panel__body">
                <div className="step">
                  <span className="step__no">3</span>
                  <span className="step__title">单煤配比边界</span>
                  <span className="text-xs text-mute">各批次在混合物中所占比例的上下限</span>
                </div>
                <GlobalBound onApply={applyGlobalBound} />
                <div className="mt-12">
                  {selectedCoals.map((c) => {
                    const b = getBound(c.id);
                    return (
                      <div className="rbound" key={c.id}>
                        <div>
                          <div className="fw-500 text-sm">{c.name}</div>
                          <div className="text-xs text-mute">{c.type} · ¥{fixed(c.price, 0)} · {fixed(heatDisplay(c.calorific_value, heatUnit), 2)} {heatUnit}</div>
                        </div>
                        <div className="minmax">
                          <input className="input" type="number" aria-label={`${c.name} 配比下限`} min={0} max={100} value={b.min} onChange={(e) => setBound(c.id, 'min', +e.target.value)} />
                          <span className="minmax__sep">–</span>
                          <input className="input" type="number" aria-label={`${c.name} 配比上限`} min={0} max={100} value={b.max} onChange={(e) => setBound(c.id, 'max', +e.target.value)} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <RatioSumBar sumMin={sumMin} sumMax={sumMax} />
              </div>
            </section>
          )}
        </div>

        {/* ---------------- right solve panel ---------------- */}
        <aside className="split__aside">
          <div className="panel solve-card">
            <div className="panel__head">
              <div className="panel__title">
                <span className="tico"><Icon name="bolt" size={16} fill /></span> 求解面板
              </div>
              <StatusPill tone="ember">NSGA-II</StatusPill>
            </div>
            <div className="panel__body col gap-16">
              <div className="row between">
                <div className="readout">
                  <span className="readout__label">已选煤种</span>
                  <span className="readout__value is-ember">{selectedCoals.length}<span className="u">种</span></span>
                </div>
                <div className="readout" style={{ textAlign: 'right' }}>
                  <span className="readout__label">热值窗口</span>
                  <span className="mono fw-500">{fixed(heatDisplay(cfg.constraints.heat_min, heatUnit), 2)}–{fixed(heatDisplay(cfg.constraints.heat_max, heatUnit), 2)} {heatUnit}</span>
                </div>
              </div>

              {/* preflight */}
              <div className={`verdict ${canSolve ? 'verdict--ok' : 'verdict--bad'}`} style={{ padding: '12px 14px' }}>
                <span className="verdict__icon" style={{ width: 38, height: 38 }}>
                  <Icon name={canSolve ? 'checkCircle' : 'alert'} size={20} />
                </span>
                <div>
                  <div className="fw-600 text-sm">{canSolve ? '预检查通过，可以开始求解' : `${issues.length} 项需要调整`}</div>
                  {!canSolve && (
                    <ul className="text-xs text-mute mt-4" style={{ paddingLeft: 16, margin: 0 }}>
                      {issues.slice(0, 4).map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {/* preset */}
              <div>
                <div className="row between mb-8 items-center">
                  <span className="eyebrow">求解档位</span>
                  <button className="btn btn--sm btn--ghost" style={{ padding: '4px 10px' }} onClick={() => setGaOpen(true)}>
                    <Icon name="sliders" size={13} /> 高级参数
                  </button>
                </div>
                <Segmented
                  value={cfg.presetId === 'custom' ? 'balanced' : cfg.presetId}
                  options={GA_PRESETS.map((p) => ({ value: p.id, label: p.label }))}
                  onChange={(id) => {
                    const preset = GA_PRESETS.find((p) => p.id === id)!;
                    setCfg((c) => ({ ...c, gaParams: { ...c.gaParams, ...preset.params }, presetId: id }));
                  }}
                />
                {cfg.presetId === 'custom' && <div className="text-xs text-amber mt-6 row gap-4"><Icon name="sliders" size={12} /> 已自定义参数</div>}
              </div>

              {/* solve */}
              {solveMut.isPending ? (
                <div className="col gap-8">
                  <div className="bar">
                    <div className="bar__fill is-striped" style={{ width: `${progress}%` }} />
                  </div>
                  <div className="text-xs text-mute row gap-6">
                    <span className="spinner" /> NSGA-II 求解中 · 种群 {cfg.gaParams.population_size}
                  </div>
                </div>
              ) : (
                <button className="btn btn--primary btn--lg btn--block" disabled={!canSolve} onClick={() => solveMut.mutate(captureRequest(currentRequest))}>
                  <Icon name="play" size={16} fill /> 开始优化求解
                </button>
              )}

              {result && (
                <>
                  <div className="divider" style={{ margin: '4px 0' }} />
                  <div className="col gap-10">
                    <div className="row between">
                      <span className="text-sm text-mute">推荐吨煤成本</span>
                      <span className="mono fw-600 text-ember">{res && feasible ? `¥${fixed(res.recommended_solution.total_price, 1)}` : '—'}</span>
                    </div>
                    <div className="row between">
                      <span className="text-sm text-mute">综合热值</span>
                      <span className="mono fw-600">{res && feasible ? `${fixed(heatDisplay(res.recommended_solution.total_heat, heatUnit), 2)} ${heatUnit}` : '—'}</span>
                    </div>
                    <div className="row between">
                      <span className="text-sm text-mute">方案状态</span>
                      {feasible ? <StatusPill tone={res?.data_validation?.status === 'unverified' ? 'warn' : 'mint'}>{res?.data_validation?.status === 'unverified' ? '试算可行（未确认）' : '数值约束可行'}</StatusPill> : <StatusPill tone="danger">无可行解</StatusPill>}
                    </div>
                    <button className="btn btn--ghost btn--block mt-4" onClick={() => resultRef.current?.scrollIntoView({ behavior: 'smooth' })}>
                      <Icon name="arrowDown" size={15} /> 查看完整结果
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* ---------------- results ---------------- */}
      <div ref={resultRef} style={{ scrollMarginTop: 12 }}>
        {completed && !result && (
          <div className="verdict verdict--bad mt-24" role="status">
            参数已更改，上次结果已失效。请重新求解后查看、分享或导出方案。
          </div>
        )}
        {result && (result.history_saved === false || result.warning) && (
          <div className="verdict verdict--bad mt-24" role="alert">
            {result.warning ?? '本次结果未保存到历史记录，请先导出报告保存结果。'}
          </div>
        )}
        {result && res && (
          <section className="mt-24">
            <ResultsView
              heatUnit={heatUnit}
              res={res}
              feasible={feasible}
              constraints={resultConstraints}
              solutions={solutions}
              activeSolution={activeSolution}
              activeId={activeId}
              recommendedId={res.recommended_solution?.solution_id ?? ''}
              onPick={setActiveId}
              onExport={() => {
                if (completed && activeSolution) exportMut.mutate(buildExportPayload(result, completed.request, activeSolution));
              }}
              exporting={exportMut.isPending}
              onCopy={copyShare}
              onResolve={() => solveMut.mutate(captureRequest(currentRequest))}
              resolving={solveMut.isPending || !canSolve}
            />
          </section>
        )}
      </div>

      <GaDrawer
        open={gaOpen}
        onClose={() => setGaOpen(false)}
        params={cfg.gaParams}
        presetId={cfg.presetId}
        onApply={(gaParams, presetId) => setCfg((c) => ({ ...c, gaParams, presetId }))}
      />
    </div>
  );
}

/* ---------------- coal picker ---------------- */
function CoalPicker({
  coals,
  heatUnit,
  loading,
  selected,
  onToggle,
}: {
  coals: BlendCoal[];
  heatUnit: string;
  loading: boolean;
  selected: Set<number>;
  onToggle: (id: number) => void;
}) {
  const [q, setQ] = useState('');
  const [type, setType] = useState('');
  const search = useDebounced(q, 200);
  const types = useMemo(() => Array.from(new Set(coals.map((c) => c.type))), [coals]);
  const filtered = coals.filter(
    (c) =>
      (!type || c.type === type) &&
      (!search || c.name.toLowerCase().includes(search.toLowerCase()) || (c.supplier ?? '').includes(search))
  );

  return (
    <div>
      <div className="row gap-10 wrap mb-12">
        <div className="input-adorn grow" style={{ minWidth: 180 }}>
          <span className="tico"><Icon name="search" size={15} /></span>
          <input className="input" placeholder="搜索煤种" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className="select" style={{ width: 130 }} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">所有类型</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      {loading ? (
        <div className="col gap-8">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="sk" style={{ height: 52 }} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState icon="database" title="没有匹配的煤种" />
      ) : (
        <div className="col gap-8" style={{ maxHeight: 340, overflow: 'auto', paddingRight: 4 }}>
          {filtered.map((c) => {
            const picked = selected.has(c.id);
            return (
              <label key={c.id} className={`coal-pick${picked ? ' is-picked' : ''}`}>
                <input type="checkbox" className="check" checked={picked} disabled={!picked && !c.assay.eligibility.blending.eligible} onChange={() => onToggle(c.id)} />
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="row gap-8 items-center">
                    <span className="coal-pick__name truncate">{c.name}</span>
                    <span className="tag tag--type">{c.type}</span>
                  </div>
                  {!c.assay.eligibility.blending.eligible && <div className="text-xs text-amber">{c.assay.eligibility.blending.issues.map(i => i.message).join('；')}</div>}
                  <div className="coal-pick__metrics">
                    <span>¥{fixed(c.price, 0)}</span>
                    <span>{fixed(heatDisplay(c.calorific_value, heatUnit), 2)} {heatUnit}</span>
                    <span>灰 {fixed(c.ash_content, 1)}%</span>
                    <span>硫 {fixed(c.total_sulfur, 2)}%</span>
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

function GlobalBound({ onApply }: { onApply: (min: number, max: number) => void }) {
  const [min, setMin] = useState(0);
  const [max, setMax] = useState(100);
  return (
    <div className="row gap-10 wrap items-end" style={{ padding: '10px 12px', background: 'var(--surface-inset)', borderRadius: 'var(--r)', border: '1px solid var(--line)' }}>
      <span className="text-xs text-mute">批量设置 (%)</span>
      <div className="minmax" style={{ width: 170 }}>
        <input className="input" type="number" aria-label="批量配比下限" min={0} max={100} value={min} onChange={(e) => setMin(+e.target.value)} />
        <span className="minmax__sep">–</span>
        <input className="input" type="number" aria-label="批量配比上限" min={0} max={100} value={max} onChange={(e) => setMax(+e.target.value)} />
      </div>
      <button className="btn btn--sm btn--ghost" onClick={() => onApply(min, max)}>
        <Icon name="refresh" size={14} /> 应用到全部
      </button>
    </div>
  );
}

function RatioSumBar({ sumMin, sumMax }: { sumMin: number; sumMax: number }) {
  const okMin = sumMin <= 100.0001;
  const okMax = sumMax >= 99.9999;
  return (
    <div className="mt-16 col gap-8">
      <div className="row between text-xs">
        <span className="text-mute">配比下限之和</span>
        <span className={`mono ${okMin ? 'text-mint' : 'text-danger'}`}>{fixed(sumMin, 1)}% {okMin ? '≤ 100' : '> 100 ⚠'}</span>
      </div>
      <div className="row between text-xs">
        <span className="text-mute">配比上限之和</span>
        <span className={`mono ${okMax ? 'text-mint' : 'text-danger'}`}>{fixed(sumMax, 1)}% {okMax ? '≥ 100' : '< 100 ⚠'}</span>
      </div>
    </div>
  );
}

/* ---------------- results view ---------------- */
function ResultsView({
  heatUnit,
  res,
  feasible,
  constraints,
  solutions,
  activeSolution,
  activeId,
  recommendedId,
  onPick,
  onExport,
  exporting,
  onCopy,
  onResolve,
  resolving,
}: {
  res: OptimizationResponse['result'];
  feasible: boolean;
  constraints: BlendingConstraints;
  solutions: ParetoSolution[];
  activeSolution: ParetoSolution | null;
  activeId: string;
  recommendedId: string;
  onPick: (id: string) => void;
  onExport: () => void;
  exporting: boolean;
  onCopy: () => void;
  onResolve: () => void;
  resolving: boolean;
  heatUnit: string;
}) {
  const s = activeSolution;
  const unverified = res.data_validation?.status === 'unverified';
  const P = useChartPalette();
  return (
    <div className="col gap-18">
      {/* verdict */}
      <div className={`verdict ${unverified ? 'verdict--warn' : feasible ? 'verdict--ok' : 'verdict--bad'}`}>
        <span className="verdict__icon">
          <Icon name={unverified ? 'alert' : feasible ? 'checkCircle' : 'xCircle'} size={26} />
        </span>
        <div className="grow">
          <div className="fw-600" style={{ fontSize: 16 }}>
            {unverified ? '试算结果：基准未确认，仅用于筛选' : feasible ? '已找到数值约束可行方案' : '当前约束下无可行方案'}
          </div>
          <div className="text-sm text-mute">
            {dataValidationLabel(res.data_validation)}。{unverified ? '不可直接用于生产。' : '仅表示输入和数值约束检查，不代表现场工艺验证。'}
            <div>数值约束：{feasible ? '满足' : '未找到可行解'}</div>
            <div>{(res.diagnosis ?? []).join(' · ')}</div>
            {(res.data_validation?.warnings ?? []).map((warning, index) => <div key={index}>{warning}</div>)}
          </div>
        </div>
        <div className="row gap-8 wrap end">
          <button className="btn btn--ghost btn--sm" onClick={onResolve} disabled={resolving}>
            <Icon name="refresh" size={14} /> 重新求解
          </button>
          <button className="btn btn--ghost btn--sm" onClick={onCopy} disabled={!feasible}>
            <Icon name="copy" size={14} /> 复制分享
          </button>
          <button className="btn btn--primary btn--sm" onClick={onExport} disabled={!feasible || exporting}>
            {exporting ? <span className="spinner" /> : <Icon name="download" size={14} />} 导出报告
          </button>
        </div>
      </div>

      {!feasible ? (
        <section className="panel">
          <div className="panel__body">
            <div className="eyebrow mb-12">约束冲突诊断</div>
            <div className="col gap-8">
              {res.constraint_violations.map((v, i) => (
                <div key={i} className="row gap-10" style={{ padding: '10px 12px', background: 'var(--danger-soft)', borderRadius: 'var(--r-sm)' }}>
                  <Icon name="alert" size={16} className="text-danger" />
                  <div>
                    <span className="fw-500">{v.label}</span>
                    <div className="text-xs text-mute">{v.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      ) : (
        s && (
          <>
            {/* readouts */}
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 14 }}>
              <MiniReadout label="吨煤成本" value={`¥${fixed(s.total_price, 1)}`} tone="ember" />
              <MiniReadout label="综合热值" value={fixed(heatDisplay(s.total_heat, heatUnit), 2)} unit={heatUnit} />
              <MiniReadout label="灰分" value={fixed(s.total_ash, 1)} unit="%" />
              <MiniReadout label="挥发分" value={fixed(s.total_volatile, 1)} unit="%" />
              <MiniReadout label="固定碳" value={fixed(s.total_fixed_carbon, 1)} unit="%" />
              <MiniReadout label="硫分" value={fixed(s.total_sulfur, 2)} unit="%" />
              <MiniReadout label="质量偏离分" value={fixed(s.quality_penalty, 3)} tone="cyan" />
            </div>

            <div className="text-xs text-mute">质量偏离分按灰分、硫分及挥发分/固定碳窗口计算；分数越低越符合模型偏好，不是燃烧风险概率。</div>

            {/* charts row */}
            <div className="grid grid--3">
              <ChartPanel title="当前方案配比" icon="beaker">
                <RatioDonut names={s.coal_names} ratios={s.optimal_ratios} />
                <div className="col gap-6 mt-8">
                  {s.coal_names.map((n, i) => (
                    <div key={n} className="row between text-sm">
                      <span className="truncate" style={{ maxWidth: 150 }}>
                        <span className="dot-color" style={{ background: P.series[i % P.series.length] }} /> {n}
                      </span>
                      <span className="mono fw-500">{fixed(s.optimal_ratios[i] * 100, 1)}%</span>
                    </div>
                  ))}
                </div>
              </ChartPanel>

              <ChartPanel title="约束余量雷达" icon="target">
                <MarginRadar sol={s} constraints={constraints} heatUnit={heatUnit} />
                <div className="text-xs text-mute" style={{ textAlign: 'center' }}>越靠近中心越接近约束下限，越靠外越接近上限</div>
              </ChartPanel>

              <ChartPanel title="约束满足诊断" icon="gauge">
                <div className="col gap-12" style={{ padding: '4px 2px' }}>
                  {CONSTRAINT_ROWS.map((r) => (
                    <ConstraintGauge
                      key={r.key}
                      label={r.label}
                      unit={r.key === 'heat' ? heatUnit : r.unit}
                      value={r.key === 'heat' ? heatDisplay(s.total_heat, heatUnit) : (s as unknown as Record<string, number>)[r.metric]}
                      lo={r.key === 'heat' ? heatDisplay(constraints[r.min] as number, heatUnit) : constraints[r.min] as number}
                      hi={r.key === 'heat' ? heatDisplay(constraints[r.max] as number, heatUnit) : constraints[r.max] as number}
                    />
                  ))}
                </div>
              </ChartPanel>
            </div>

            {/* algorithm meta */}
            <div className="row gap-10 wrap">
              {(s.active_constraints ?? []).map((a) => (
                <span key={a} className="pill pill--warn"><Icon name="target" size={12} /> {a} 贴边</span>
              ))}
              <span className="pill"><Icon name="refresh" size={12} /> 迭代 {num(res.iterations)}</span>
              <span className="pill"><Icon name="gauge" size={12} /> 耗时 {fixed(res.time_taken, 2)}s</span>
              <span className="pill"><Icon name="zap" size={12} fill /> 质量偏离分 {fixed(s.quality_penalty, 4)}</span>
            </div>

            {/* pareto */}
            <section className="panel">
              <div className="panel__head">
                <div className="panel__title">
                  <span className="tico"><Icon name="chart" size={16} /></span> Pareto 前沿 · {solutions.length} 个候选方案
                </div>
                <span className="text-xs text-mute">点击散点或表格行切换查看方案</span>
              </div>
              <div className="panel__body">
                <div className="grid" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.1fr)', gap: 18, alignItems: 'start' }}>
                  <ParetoScatter heatUnit={heatUnit} solutions={solutions} recommendedId={recommendedId} activeId={activeId} onPick={onPick} />
                  <div className="tbl-wrap" style={{ maxHeight: 320 }}>
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th>方案</th>
                          <th className="num">成本</th>
                          <th className="num">热值 ({heatUnit})</th>
                          <th className="num">灰分</th>
                          <th className="num">硫分</th>
                          <th className="num">偏离分</th>
                        </tr>
                      </thead>
                      <tbody>
                        {solutions.map((sol) => (
                          <tr
                            key={sol.solution_id}
                            onClick={() => onPick(sol.solution_id)}
                            style={{ cursor: 'pointer' }}
                            className={`${sol.solution_id === recommendedId ? 'is-recommended' : ''} ${sol.solution_id === activeId ? 'is-active-sol' : ''}`}
                          >
                            <td>
                              <div className="row gap-6 items-center">
                                {sol.solution_id === recommendedId && <span className="pill pill--live" style={{ padding: '1px 7px' }}>推荐</span>}
                                <span className="mono text-xs text-mute">{sol.solution_id.replace('pareto_', '#')}</span>
                              </div>
                            </td>
                            <td className="num text-ember">{fixed(sol.total_price, 1)}</td>
                            <td className="num">{fixed(heatDisplay(sol.total_heat, heatUnit), 2)}</td>
                            <td className="num">{fixed(sol.total_ash, 1)}</td>
                            <td className="num">{fixed(sol.total_sulfur, 2)}</td>
                            <td className="num text-cyan">{fixed(sol.quality_penalty, 3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </section>
          </>
        )
      )}
    </div>
  );
}

function MiniReadout({ label, value, unit, tone }: { label: string; value: string; unit?: string; tone?: 'ember' | 'cyan' }) {
  return (
    <div className="panel" style={{ padding: '14px 16px' }}>
      <div className="readout">
        <span className="readout__label">{label}</span>
        <span className={`readout__value${tone === 'ember' ? ' is-ember' : tone === 'cyan' ? ' is-cyan' : ''}`} style={{ fontSize: 22 }}>
          {value}
          {unit && <span className="u">{unit}</span>}
        </span>
      </div>
    </div>
  );
}

function ChartPanel({ title, icon, children }: { title: string; icon: IconName; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel__head">
        <div className="panel__title">
          <span className="tico"><Icon name={icon} size={16} /></span> {title}
        </div>
      </div>
      <div className="panel__body">{children}</div>
    </section>
  );
}

function ConstraintGauge({ label, unit, value, lo, hi }: { label: string; unit: string; value: number; lo: number; hi: number }) {
  const inside = value >= lo - 1e-6 && value <= hi + 1e-6;
  const pos = hi > lo ? Math.max(0, Math.min(100, ((value - lo) / (hi - lo)) * 100)) : 50;
  return (
    <div>
      <div className="row between text-xs mb-4">
        <span className="text-soft">{label}</span>
        <span className={`mono ${inside ? 'text-mint' : 'text-danger'}`}>
          {fixed(value, unit === '%' || unit === 'MJ/kg' ? 2 : 0)} {unit}
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, borderRadius: 999, background: 'var(--surface-inset)', border: '1px solid var(--line)' }}>
        <div
          style={{
            position: 'absolute',
            left: `${pos}%`,
            top: '50%',
            width: 8,
            height: 8,
            borderRadius: '50%',
            transform: 'translate(-50%,-50%)',
            background: inside ? 'var(--mint)' : 'var(--danger)',
            boxShadow: `0 0 8px ${inside ? 'var(--mint)' : 'var(--danger)'}`,
          }}
        />
      </div>
      <div className="row between" style={{ fontSize: 9, color: 'var(--ink-faint)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
        <span>{fixed(lo, unit === '%' ? 1 : 0)}</span>
        <span>{fixed(hi, unit === '%' ? 1 : 0)}</span>
      </div>
    </div>
  );
}
