import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { ActualRatioResponse, TheoryRatioResponse } from '../lib/types';
import { api } from '../lib/http';
import { useSession } from '../lib/session';
import { getSettings, listAssays } from '../lib/v2';
import { buildActualRequest, buildTheoryRequest, type ReplacementFields } from '../lib/replacementRequest';
import { Icon, type IconName } from '../components/ui/Icon';
import { Field } from '../components/ui/bits';
import { useToast } from '../components/ui/Toast';
import { fixed } from '../lib/format';
import '../styles/replacement.css';

type Mode = 'theory' | 'actual';
type CalculationResult = (TheoryRatioResponse | ActualRatioResponse) & {
  input_snapshot?: { assay?: { label: string }; settings: { version: number }; actor: { display_name: string }; created_at: string };
};
interface NumericField { id: string; label: string; unit?: string }
const HEAT_FIELDS: NumericField[] = [
  { id: 'coal_decomp', label: '煤粉分解热', unit: 'kJ/kg 干煤' },
  { id: 'coal_physical', label: '加热至模型温度的物理热', unit: 'kJ/kg 干煤' },
];
const COKE_FIELDS: NumericField[] = [
  { id: 'coke_carbon', label: '元素碳 C（干基）', unit: '%' },
  { id: 'coke_ash', label: '灰分 A（干基）', unit: '%' },
  { id: 'coke_sio2', label: 'SiO₂（灰中含量）', unit: '%' },
];
const FURNACE_FIELDS: NumericField[] = [
  { id: 'eta_co', label: '煤气利用率 ηCO', unit: '%' },
  { id: 'slag_basicity', label: '炉渣碱度' },
  { id: 'slag_enthalpy', label: '炉渣热焓', unit: 'kJ/kg' },
];
const ACTUAL_FIELDS: NumericField[] = [
  { id: 'initial_coke', label: '调整前焦比', unit: 'kg/t 铁水' },
  { id: 'final_coke', label: '调整后焦比', unit: 'kg/t 铁水' },
  { id: 'initial_coal', label: '调整前煤比', unit: 'kg/t 铁水' },
  { id: 'final_coal', label: '调整后煤比', unit: 'kg/t 铁水' },
];

export default function ReplacementRatio() {
  const { can } = useSession();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>('theory');
  const [values, setValues] = useState<ReplacementFields>({});
  const [revisionId, setRevisionId] = useState('');
  const [allowEstimate, setAllowEstimate] = useState(false);
  const [corrected, setCorrected] = useState(false);
  const [completed, setResult] = useState<CalculationResult | null>(null);
  const [error, setError] = useState('');
  const settings = useQuery({ queryKey: ['settings'], queryFn: getSettings, refetchInterval: 30_000 });
  const assays = useQuery({ queryKey: ['assays', settings.data?.version],
    queryFn: () => listAssays(settings.data!.version), enabled: settings.data !== undefined });
  const result = completed?.input_snapshot?.settings.version === settings.data?.version ? completed : null;
  const selected = assays.data?.find(record => record.id === Number(revisionId));
  const eligible = selected?.eligibility.theory;

  useEffect(() => { setResult(null); setError(''); }, [mode, values, revisionId, allowEstimate, corrected, settings.data?.version]);
  const set = (field: string, value: string) => setValues(previous => ({ ...previous, [field]: value }));
  const mutation = useMutation({
    mutationFn: async () => {
      if (!can('calculate')) throw new Error('当前账号没有计算权限');
      const body = mode === 'theory'
        ? buildTheoryRequest(values, selected, settings.data, allowEstimate)
        : buildActualRequest(values, settings.data, corrected);
      return api<CalculationResult>(`/api/calculate_${mode}_ratio`, { method: 'POST', body: JSON.stringify(body) });
    },
    onSuccess: response => { setResult(response); setError(''); toast.success('置换比计算完成', `结果 ${fixed(response.ratio, 4)}`); },
    onError: (failure: Error) => { setError(failure.message); setResult(null); },
  });
  const reset = () => { setValues({}); setRevisionId(''); setAllowEstimate(false); setCorrected(false); setResult(null); setError(''); };
  const dataError = settings.error || (mode === 'theory' ? assays.error : null);

  return <fieldset className="page replacement-page" disabled={mutation.isPending}>
    <div className="page__head"><div><h1 className="page__title">置换比计算</h1><p className="page__lead">选择计算方式，填写煤质与生产参数，评估每千克喷吹煤对应的焦炭替代量。</p></div></div>
    <div className="rr-modes" role="group" aria-label="置换比模式">
      <ModeCard active={mode === 'theory'} icon="beaker" title="理论置换比" description="煤粉、焦炭成分与高炉参数 · 干基热平衡模型" onClick={() => setMode('theory')} />
      <ModeCard active={mode === 'actual'} icon="scale" title="实际置换比" description="同一高炉前后期间的煤比、焦比 · 生产数据反算" onClick={() => setMode('actual')} />
    </div>
    {dataError && <div className="panel panel__body mb-20" role="alert">数据加载失败：{dataError.message} <button className="btn btn--ghost" onClick={() => { void assays.refetch(); void settings.refetch(); }}>重试</button></div>}
    {completed && !result && <p role="status">本次返回结果使用旧设置版本，已保存在历史中。当前设置已更新，请确认参数后重新计算。</p>}
    {!can('calculate') && <p role="status" className="text-mute">当前账号可查看数据，计算需要计算员或管理员权限。</p>}
    <div className="rr-layout"><div className="rr-form">
      {mode === 'theory' ? <>
        <section className="panel"><SectionHeading step="01" title="煤粉批次化验" /><div className="panel__body col gap-12">
          <label htmlFor="replacement-assay">化验修订</label>
          <select id="replacement-assay" className="input" value={revisionId} onChange={event => setRevisionId(event.target.value)}>
            <option value="">{assays.isPending ? '正在加载化验…' : '请选择煤种 / 批次 / 化验修订'}</option>
            {assays.data?.map(record => <option key={record.id} value={record.id}>{record.label}{record.eligibility.theory.eligible && !record.archived ? '' : ' · 暂不可计算'}</option>)}
          </select>
          {!assays.isPending && !assays.data?.length && <p className="text-mute">尚无化验记录。请先在煤质资料中创建煤种、批次及化验修订。</p>}
          {!selected && !!assays.data?.length && <p className="rr-hint">选择化验后，自动带入干基元素碳、氢和灰分，以及灰中 SiO₂。</p>}
          {selected && <>
            <p className="text-sm">{eligible?.eligible ? '该修订的理论计算输入已完整。以下成分已统一到干基；SiO₂ 为灰基。' : '该修订暂不能用于理论计算，请补充新化验修订：'}</p>
            {!!eligible?.issues.length && <ul role="status">{eligible.issues.map(issue => <li key={`${issue.field}-${issue.code}`}>{issue.message}</li>)}</ul>}
            <div className="rr-assay-values">{Object.entries({ carbon_content: '元素碳 C_d', hydrogen_content: '元素氢 H_d', ash_content: '灰分 A_d', sio2_content: '灰中 SiO₂' }).map(([key, label]) => <div key={key} className="kv"><span className="kv__k">{label}</span><span className="kv__v">{eligible?.values[key] === undefined ? '未提供' : `${fixed(eligible.values[key], 4)}%`}</span></div>)}</div>
            <details><summary>查看化验换算依据</summary><ul>{eligible?.trace.map((line, index) => <li key={index}>{String(line)}</li>)}</ul></details>
          </>}
        </div></section>
        <ParamPanel step="02" title="煤粉热耗参数" fields={HEAT_FIELDS} values={values} onChange={set} />
        <ParamPanel step="03" title="焦炭化验" description="C、A 按干基填写；SiO₂ 为灰中含量。" fields={COKE_FIELDS} values={values} onChange={set} />
        <section className="panel"><SectionHeading step="04" title="高炉工艺参数" /><div className="panel__body col gap-16">
          <NumericFields fields={FURNACE_FIELDS} values={values} onChange={set} />
          <div className="rr-option"><label className="rr-check"><input type="checkbox" checked={allowEstimate} onChange={event => setAllowEstimate(event.target.checked)} /><span>明确使用风温估算鼓风热焓</span></label>
          <p className="text-xs text-mute">{allowEstimate ? '本次使用 1.3 × 风温的工程估算，结果与历史记录会标注估算来源。' : '请填写所用鼓风热焓；不填时不会自动按风温估算。'}体积口径须与模型风量一致。</p>
          </div>
          <NumericFields fields={allowEstimate ? [{ id: 'wind_temp', label: '风温', unit: '°C' }] : [{ id: 'hot_blast', label: '鼓风热焓', unit: 'kJ/m³' }]} values={values} onChange={set} />
          <div className="rr-field"><label htmlFor="replacement-source">焦炭、炉况和热耗来源说明 <span className="text-mute">· 选填</span></label><input id="replacement-source" aria-label="焦炭、炉况和热耗来源说明" className="input" value={values.parameter_source || ''} onChange={event => set('parameter_source', event.target.value)} placeholder="报告编号、统计日期或工程参数依据" /></div>
        </div></section>
      </> : <>
        <section className="panel"><SectionHeading step="01" title="生产记录口径" /><div className="panel__body col gap-12">
          <label htmlFor="replacement-mass">煤、焦炭耗量的共同质量基准</label><select id="replacement-mass" className="input" value={values.mass_basis || ''} onChange={event => set('mass_basis', event.target.value)}><option value="">请选择已核对的质量基准</option><option value="d">干基 · kg 干煤/干焦每吨铁水</option><option value="ar">收到基 · kg 收到煤/焦每吨铁水</option></select>
          <p className="text-xs text-mute">四项比耗应使用同一高炉、同一铁水统计定义和可比较期间。收到基结果包含实际含水影响；系统不自动将其解释为干基置换比。</p>
          <div className="rr-fields rr-fields--2 rr-periods">{(['furnace_id', 'period_before', 'period_after'] as const).map((field, index) => <label key={field} className={`rr-field${index === 0 ? ' rr-field--full' : ''}`}>{['高炉编号', '调整前统计期间', '调整后统计期间'][index]}<input className="input" value={values[field] || ''} onChange={event => set(field, event.target.value)} /></label>)}</div>
        </div></section>
        <ParamPanel step="02" title="实际生产数据" description="按同一质量基准填写，单位均为 kg/t 铁水。" fields={ACTUAL_FIELDS} values={values} onChange={set} />
        <section className="panel"><SectionHeading step="03" title="生产修正" /><div className="panel__body col gap-12">
          <label className="rr-check"><input type="checkbox" checked={corrected} onChange={event => setCorrected(event.target.checked)} /><span>使用已有依据的修正量 K</span></label>
          <p className="text-xs text-mute">{corrected ? '请提供修正量及来源。系统不会套用产量、渣比、碳效率的固定经验权重。' : '未修正公式：焦比减少量 ÷ 煤比增加量。'}煤比变化不能为零。</p>
          {corrected && <><NumericFields fields={[{ id: 'adjustment', label: '修正量 K（可为负）', unit: 'kg/t 铁水' }]} values={values} onChange={set} /><div className="rr-field"><label htmlFor="replacement-correction">修正来源（必填）</label><input id="replacement-correction" className="input" value={values.correction_source || ''} onChange={event => set('correction_source', event.target.value)} /></div></>}
        </div></section>
      </>}
      {result && <section className="panel"><div className="panel__head"><h2 className="panel__title">本次计算明细</h2></div><div className="panel__body">
        {Object.entries(result.details).map(([label, value]) => <div className="kv" key={label}><span className="kv__k">{label}</span><span className="kv__v">{fixed(value, 6)}</span></div>)}
        {'hot_blast_enthalpy_source' in result && <p className="text-sm">鼓风热焓来源：{result.hot_blast_enthalpy_source === 'temperature_estimate' ? '风温工程估算（已显式选择）' : '用户提供'}；使用值 {fixed(result.effective_hot_blast_enthalpy ?? 0, 3)} kJ/m³。</p>}
        {result.input_snapshot && <p className="text-xs text-mute">已保存计算快照：{result.input_snapshot.assay?.label || '生产期间实测数据'}；设置版本 {result.input_snapshot.settings.version}；操作者 {result.input_snapshot.actor.display_name}。历史记录保留当时原始值与换算口径。</p>}
      </div></section>}
    </div><aside className="rr-aside"><section className="panel rr-result"><div className="panel__head"><h2 className="panel__title">计算结果</h2><Icon name="activity" size={17} /></div><div className="panel__body col gap-16">
      <div className="readout rr-result__readout" aria-live="polite"><span className="readout__label">{mode === 'theory' ? '理论置换比 · 干基' : corrected ? '实际置换比 · 显式修正' : '实际置换比 · 未修正'}</span><span className="readout__value is-ember">{result ? fixed(result.ratio, 4) : '—'}</span><span className="text-xs text-mute">kg 焦 / kg 煤</span>{!result && <span className="rr-result__placeholder">填写参数后开始计算</span>}</div>
      {error && <p className="rr-error" role="alert">{error}</p>}
      <button className="btn btn--primary btn--lg btn--block" disabled={!can('calculate') || mutation.isPending || !settings.data || !!dataError || (mode === 'theory' && (!eligible?.eligible || selected?.archived))} onClick={() => mutation.mutate()}>{mutation.isPending ? '计算中…' : '开始计算'}</button>
      <button className="btn btn--ghost btn--block" onClick={reset}><Icon name="reset" size={15} /> 清空输入</button>
      <div className="rr-result__note"><strong>使用说明</strong><p>{mode === 'theory' ? '简化的碳氢热平衡估算，结果须结合高炉生产数据校核。输入检查通过不等于现场效果验证。' : '反映所选期间的煤焦比变化，不能单独证明变化完全由喷煤造成。'}</p></div>
    </div></section></aside></div>
  </fieldset>;
}

function NumericFields({ fields, values, onChange }: { fields: NumericField[]; values: ReplacementFields; onChange: (field: string, value: string) => void }) {
  return <div className={`rr-fields rr-fields--${fields.length === 3 ? 3 : fields.length === 1 ? 1 : 2}`}>{fields.map(field => <Field key={field.id} label={field.label} unit={field.unit} required><input className="input" type="number" step="any" aria-label={field.label} value={values[field.id] ?? ''} onChange={event => onChange(field.id, event.target.value)} /></Field>)}</div>;
}
function ParamPanel({ step, title, description, fields, values, onChange }: { step: string; title: string; description?: string; fields: NumericField[]; values: ReplacementFields; onChange: (field: string, value: string) => void }) {
  return <section className="panel"><SectionHeading step={step} title={title} /><div className="panel__body">{description && <p className="rr-hint rr-hint--above">{description}</p>}<NumericFields fields={fields} values={values} onChange={onChange} /></div></section>;
}
function SectionHeading({ step, title }: { step: string; title: string }) {
  return <div className="panel__head rr-section-heading"><span className="rr-step" aria-hidden="true">{step}</span><h2 className="panel__title">{title}</h2></div>;
}
function ModeCard({ active, icon, title, description, onClick }: { active: boolean; icon: IconName; title: string; description: string; onClick: () => void }) {
  return <button type="button" className={`mode-card rr-mode${active ? ' is-active' : ''}`} aria-pressed={active} aria-label={title} onClick={onClick}><span className="mode-card__icon"><Icon name={icon} size={22} /></span><span className="rr-mode__copy"><strong>{title}</strong><span>{description}</span></span><span className="rr-mode__indicator" aria-hidden="true"><Icon name={active ? 'checkCircle' : 'chevronRight'} size={18} /></span></button>;
}
