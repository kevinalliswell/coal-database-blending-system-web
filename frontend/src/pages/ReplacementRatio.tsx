import { useEffect, useMemo, useState } from 'react';
import type { EChartsOption } from 'echarts';
import { useMutation } from '@tanstack/react-query';
import { calcActualRatio, calcTheoryRatio } from '../lib/api';
import type { ActualRatioResponse, TheoryRatioResponse } from '../lib/types';
import { Icon } from '../components/ui/Icon';
import { Field } from '../components/ui/bits';
import { Chart, tooltipBase, useChartPalette } from '../components/ui/Chart';
import { useToast } from '../components/ui/Toast';
import { fixed } from '../lib/format';

type Mode = 'theory' | 'actual';

interface FieldCfg {
  id: string;
  label: string;
  unit?: string;
  percent?: boolean; // UI shows %, payload sends fraction
  def: number;
  example: number;
}
interface Group {
  title: string;
  fields: FieldCfg[];
}

const THEORY_GROUPS: Group[] = [
  {
    title: '煤粉参数',
    fields: [
      { id: 'coal_carbon', label: '含碳量', unit: '%', percent: true, def: 78, example: 74.5 },
      { id: 'coal_hydrogen', label: '含氢量', unit: '%', percent: true, def: 3.5, example: 4.2 },
      { id: 'coal_ash', label: '灰分', unit: '%', percent: true, def: 12, example: 9.5 },
      { id: 'coal_sio2', label: '灰中 SiO₂', unit: '%', percent: true, def: 48, example: 45 },
      { id: 'coal_decomp', label: '分解热', unit: 'kcal/kg', def: 220, example: 260 },
      { id: 'coal_physical', label: '物理热', unit: 'kcal/kg', def: 450, example: 500 },
    ],
  },
  {
    title: '焦炭参数',
    fields: [
      { id: 'coke_carbon', label: '含碳量', unit: '%', percent: true, def: 86, example: 85 },
      { id: 'coke_ash', label: '灰分', unit: '%', percent: true, def: 11, example: 12.5 },
      { id: 'coke_sio2', label: '灰中 SiO₂', unit: '%', percent: true, def: 52, example: 50 },
    ],
  },
  {
    title: '高炉工艺参数',
    fields: [
      { id: 'eta_co', label: '煤气利用率 ηCO', def: 0.4444, example: 0.47 },
      { id: 'slag_basicity', label: '炉渣碱度', def: 1.15, example: 1.2 },
      { id: 'slag_enthalpy', label: '炉渣热焓', unit: 'kJ/kg', def: 1800, example: 1850 },
      { id: 'wind_temp', label: '风温', unit: '°C', def: 1180, example: 1220 },
      { id: 'hot_blast', label: '鼓风热焓', unit: 'kJ/m³', def: 1.5, example: 1.6 },
    ],
  },
];

const ACTUAL_BASIC: Group = {
  title: '基础生产数据',
  fields: [
    { id: 'initial_coke', label: '调整前焦比', unit: 'kg/t', def: 400, example: 420 },
    { id: 'final_coke', label: '调整后焦比', unit: 'kg/t', def: 370, example: 380 },
    { id: 'initial_coal', label: '调整前煤比', unit: 'kg/t', def: 150, example: 140 },
    { id: 'final_coal', label: '调整后煤比', unit: 'kg/t', def: 180, example: 185 },
    { id: 'adjustment', label: '修正系数', unit: 'kg/t', def: 2.5, example: 3.0 },
  ],
};
const ACTUAL_ADV: Group = {
  title: '生产因素修正',
  fields: [
    { id: 'iron_output', label: '铁水产量变化', unit: 't/d', def: 50, example: 80 },
    { id: 'slag_change', label: '渣比变化', unit: 'kg/t', def: -10, example: -15 },
    { id: 'carbon_eff', label: '碳利用效率变化', unit: '%', def: 2, example: 3 },
  ],
};

function initValues(mode: Mode): Record<string, number> {
  const out: Record<string, number> = {};
  const groups = mode === 'theory' ? THEORY_GROUPS : [ACTUAL_BASIC, ACTUAL_ADV];
  groups.forEach((g) => g.fields.forEach((f) => (out[f.id] = f.def)));
  return out;
}

export default function ReplacementRatio() {
  const toast = useToast();
  const [mode, setMode] = useState<Mode>('theory');
  const [values, setValues] = useState<Record<string, number>>(() => initValues('theory'));
  const [advanced, setAdvanced] = useState(false);
  const [theoryRes, setTheoryRes] = useState<TheoryRatioResponse | null>(null);
  const [actualRes, setActualRes] = useState<ActualRatioResponse | null>(null);

  useEffect(() => {
    setValues(initValues(mode));
    setTheoryRes(null);
    setActualRes(null);
  }, [mode]);

  const set = (id: string, v: number) => setValues((s) => ({ ...s, [id]: v }));

  const theoryMut = useMutation({
    mutationFn: () =>
      calcTheoryRatio({
        coal_params: {
          carbon_content: values.coal_carbon / 100,
          hydrogen_content: values.coal_hydrogen / 100,
          ash_content: values.coal_ash / 100,
          sio2_content: values.coal_sio2 / 100,
          decomposition_heat: values.coal_decomp,
          physical_heat: values.coal_physical,
        },
        coke_params: {
          carbon_content: values.coke_carbon / 100,
          ash_content: values.coke_ash / 100,
          sio2_content: values.coke_sio2 / 100,
        },
        blast_furnace_params: {
          eta_co: values.eta_co,
          slag_basicity: values.slag_basicity,
          slag_enthalpy: values.slag_enthalpy,
          wind_temperature: values.wind_temp,
          hot_blast_enthalpy: values.hot_blast,
        },
      }),
    onSuccess: (r) => {
      setTheoryRes(r);
      toast.success('理论置换比计算完成', `置换比 ${fixed(r.ratio, 4)}`);
    },
    onError: (e: Error) => toast.error('计算失败', e.message),
  });

  const actualMut = useMutation({
    mutationFn: () =>
      calcActualRatio({
        production_data: {
          initial_coke_ratio: values.initial_coke,
          final_coke_ratio: values.final_coke,
          initial_coal_ratio: values.initial_coal,
          final_coal_ratio: values.final_coal,
          adjustment_factor: values.adjustment,
          iron_output_change: advanced ? values.iron_output : 0,
          slag_ratio_change: advanced ? values.slag_change : 0,
          carbon_efficiency_change: advanced ? values.carbon_eff : 0,
        },
        enable_advanced: advanced,
      }),
    onSuccess: (r) => {
      setActualRes(r);
      toast.success('实际置换比计算完成', `置换比 ${fixed(r.ratio, 4)}`);
    },
    onError: (e: Error) => toast.error('计算失败', e.message),
  });

  const running = theoryMut.isPending || actualMut.isPending;
  const calc = () => (mode === 'theory' ? theoryMut.mutate() : actualMut.mutate());
  const loadExample = () => {
    const groups = mode === 'theory' ? THEORY_GROUPS : [ACTUAL_BASIC, ACTUAL_ADV];
    const ex: Record<string, number> = {};
    groups.forEach((g) => g.fields.forEach((f) => (ex[f.id] = f.example)));
    setValues(ex);
    toast.info('已载入示例参数');
  };
  const reset = () => {
    setValues(initValues(mode));
    setTheoryRes(null);
    setActualRes(null);
  };

  const result = mode === 'theory' ? theoryRes : actualRes;
  const ratio = result?.ratio ?? null;
  const details = result?.details ?? null;

  const donutData = useMemo(() => contribData(mode, details), [mode, details]);

  const groups = mode === 'theory' ? THEORY_GROUPS : [ACTUAL_BASIC];

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">置换比计算</h1>
          <p className="page__lead">计算高炉喷吹煤的理论置换比与实际生产置换比，为煤比调整提供依据。</p>
        </div>
      </div>

      {/* mode cards */}
      <div className="grid grid--2 mb-20">
        <ModeCard active={mode === 'theory'} icon="beaker" title="理论置换比" desc="基于煤粉/焦炭成分与高炉工艺参数的碳氢热平衡模型" onClick={() => setMode('theory')} />
        <ModeCard active={mode === 'actual'} icon="scale" title="实际置换比" desc="基于焦比、煤比调整前后的生产数据反算，支持生产因素修正" onClick={() => setMode('actual')} />
      </div>

      <div className="split">
        <div className="col gap-18">
          {groups.map((g) => (
            <ParamPanel key={g.title} title={g.title} fields={g.fields} values={values} onChange={set} />
          ))}

          {mode === 'actual' && (
            <section className="panel">
              <div className="panel__body">
                <div className="row between mb-12">
                  <div className="panel__title" style={{ fontSize: 14 }}>
                    <span className="tico"><Icon name="sliders" size={15} /></span> {ACTUAL_ADV.title}
                  </div>
                  <label className="switch">
                    <input type="checkbox" checked={advanced} onChange={(e) => setAdvanced(e.target.checked)} />
                    <span className="switch__track" />
                    <span className="text-sm">{advanced ? '已启用修正' : '启用修正'}</span>
                  </label>
                </div>
                <div className="grid grid--3" style={{ gap: 14, opacity: advanced ? 1 : 0.45, pointerEvents: advanced ? 'auto' : 'none' }}>
                  {ACTUAL_ADV.fields.map((f) => (
                    <Field key={f.id} label={f.label} unit={f.unit}>
                      <input className="input" type="number" value={values[f.id] ?? ''} disabled={!advanced} onChange={(e) => set(f.id, +e.target.value)} />
                    </Field>
                  ))}
                </div>
                {!advanced && <div className="text-xs text-mute mt-8">未启用时，这三项按 0 处理，仅计算基础置换比。</div>}
              </div>
            </section>
          )}

          {/* details */}
          {details && (
            <section className="panel">
              <div className="panel__head">
                <div className="panel__title"><span className="tico"><Icon name="chart" size={16} /></span> 计算明细</div>
              </div>
              <div className="panel__body">
                <div className="grid" style={{ gridTemplateColumns: donutData.length ? 'minmax(0,1fr) 240px' : '1fr', gap: 18 }}>
                  <div>
                    {Object.entries(details).map(([k, v]) => (
                      <div key={k} className="kv">
                        <span className="kv__k">{k}</span>
                        <span className="kv__v">{fixed(v, 6)}</span>
                      </div>
                    ))}
                  </div>
                  {donutData.length > 0 && (
                    <div>
                      <div className="eyebrow mb-8" style={{ textAlign: 'center' }}>构成占比</div>
                      <ContribDonut items={donutData} />
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}
        </div>

        {/* aside result / action */}
        <aside className="split__aside">
          <div className="panel solve-card">
            <div className="panel__head">
              <div className="panel__title"><span className="tico"><Icon name="target" size={16} /></span> 计算结果</div>
              <span className="pill pill--cyan">{mode === 'theory' ? '理论' : advanced ? '实际·修正' : '实际·基础'}</span>
            </div>
            <div className="panel__body col gap-16">
              <div style={{ textAlign: 'center', padding: '10px 0' }}>
                <div className="readout__label">{mode === 'theory' ? '理论置换比' : '实际置换比'}</div>
                <div className="readout__value is-ember" style={{ fontSize: 48, marginTop: 6 }}>
                  {ratio === null ? '—' : fixed(ratio, 4)}
                </div>
                <div className="text-xs text-mute mt-4">kg 焦 / kg 煤</div>
              </div>

              <button className="btn btn--primary btn--lg btn--block" onClick={calc} disabled={running}>
                {running ? <span className="spinner" /> : <Icon name="play" size={16} fill />} 开始计算
              </button>
              <div className="row gap-10">
                <button className="btn btn--ghost grow" onClick={loadExample} disabled={running}>
                  <Icon name="box" size={15} /> 载入示例
                </button>
                <button className="btn btn--ghost grow" onClick={reset} disabled={running}>
                  <Icon name="reset" size={15} /> 重置
                </button>
              </div>

              <div className="divider" style={{ margin: '2px 0' }} />
              <div className="text-xs text-mute">
                {mode === 'theory'
                  ? '理论模型基于煤粉与焦炭的碳、氢、灰分及高炉工艺参数，反映置换比的理论上限。'
                  : '实际置换比由焦比与煤比的调整量反算，修正模式进一步纳入产量、渣比与碳效率影响。'}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function ModeCard({ active, icon, title, desc, onClick }: { active: boolean; icon: 'beaker' | 'scale'; title: string; desc: string; onClick: () => void }) {
  return (
    <div className={`mode-card${active ? ' is-active' : ''}`} onClick={onClick}>
      <span className="mode-card__icon"><Icon name={icon} size={20} /></span>
      <div>
        <div className="row gap-8 items-center">
          <span className="fw-600" style={{ fontFamily: 'var(--font-display)' }}>{title}</span>
          {active && <Icon name="check" size={15} className="text-ember" />}
        </div>
        <div className="text-xs text-mute mt-4">{desc}</div>
      </div>
    </div>
  );
}

function ParamPanel({ title, fields, values, onChange }: { title: string; fields: FieldCfg[]; values: Record<string, number>; onChange: (id: string, v: number) => void }) {
  return (
    <section className="panel">
      <div className="panel__head">
        <div className="panel__title"><span className="tico"><Icon name="sliders" size={15} /></span> {title}</div>
      </div>
      <div className="panel__body">
        <div className="grid grid--3" style={{ gap: 14 }}>
          {fields.map((f) => (
            <Field key={f.id} label={f.label} unit={f.unit ?? (f.percent ? '%' : undefined)}>
              <input className="input" type="number" step="any" value={values[f.id] ?? ''} onChange={(e) => onChange(f.id, +e.target.value)} />
            </Field>
          ))}
        </div>
      </div>
    </section>
  );
}

function contribData(mode: Mode, details: Record<string, number> | null): { name: string; value: number }[] {
  if (!details) return [];
  const keys =
    mode === 'theory'
      ? ['煤粉含碳量', '煤粉中氢参加还原而节约的碳量', '煤粉中灰分造渣所消耗的碳', '煤粉分解热和加热至1500°C物理热所消耗的碳']
      : ['焦比减少量(kg/t)', '煤比增加量(kg/t)', '修正系数(kg/t)'];
  return keys
    .filter((k) => k in details && Math.abs(details[k]) > 1e-9)
    .map((k) => ({ name: k.replace(/\(.*\)/, '').replace('煤粉', ''), value: Math.abs(details[k]) }));
}

function ContribDonut({ items }: { items: { name: string; value: number }[] }) {
  const P = useChartPalette();
  const option: EChartsOption = {
    color: P.series,
    tooltip: { ...tooltipBase(P), trigger: 'item', formatter: (p: unknown) => { const d = p as { name: string; value: number; percent: number }; return `${d.name}<br/><b>${d.value.toFixed(4)}</b> · ${d.percent}%`; } },
    legend: { bottom: 0, textStyle: { color: P.inkMute, fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '42%'],
        itemStyle: { borderColor: P.surface, borderWidth: 2 },
        label: { show: false },
        data: items,
      },
    ],
  };
  return <Chart option={option} height={230} />;
}
