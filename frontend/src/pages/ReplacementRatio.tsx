import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { ActualRatioResponse, TheoryRatioResponse } from '../lib/types';
import { api } from '../lib/http';
import { useSession } from '../lib/session';
import { getSettings, listAssays } from '../lib/v2';
import { buildActualRequest, buildTheoryRequest, type ReplacementFields } from '../lib/replacementRequest';
import { Icon } from '../components/ui/Icon';
import { Field } from '../components/ui/bits';
import { useToast } from '../components/ui/Toast';
import { fixed } from '../lib/format';

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
  const [result, setResult] = useState<CalculationResult | null>(null);
  const [error, setError] = useState('');
  const assays = useQuery({ queryKey: ['assays'], queryFn: listAssays });
  const settings = useQuery({ queryKey: ['settings'], queryFn: getSettings });
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

  return <fieldset className="page" disabled={mutation.isPending} style={{ border: 0, margin: 0, minWidth: 0 }}>
    <div className="page__head"><div><h1 className="page__title">置换比计算</h1><p className="page__lead">选择批次化验与明确的现场参数，保存可追溯的计算记录。</p></div></div>
    <div className="row gap-10 mb-20" role="group" aria-label="置换比模式">
      <button className={`btn ${mode === 'theory' ? 'btn--primary' : 'btn--ghost'}`} aria-pressed={mode === 'theory'} onClick={() => setMode('theory')}><Icon name="beaker" size={16} /> 理论置换比</button>
      <button className={`btn ${mode === 'actual' ? 'btn--primary' : 'btn--ghost'}`} aria-pressed={mode === 'actual'} onClick={() => setMode('actual')}><Icon name="scale" size={16} /> 实际置换比</button>
    </div>
    {dataError && <div className="panel panel__body mb-20" role="alert">数据加载失败：{dataError.message} <button className="btn btn--ghost" onClick={() => { void assays.refetch(); void settings.refetch(); }}>重试</button></div>}
    {!can('calculate') && <p role="status" className="text-mute">当前账号可查看数据，计算需要计算员或管理员权限。</p>}
    <div className="split"><div className="col gap-18">
      {mode === 'theory' ? <>
        <section className="panel"><div className="panel__head"><h2 className="panel__title">煤粉批次化验</h2></div><div className="panel__body col gap-12">
          <label htmlFor="replacement-assay">化验修订</label>
          <select id="replacement-assay" className="input" value={revisionId} onChange={event => setRevisionId(event.target.value)}>
            <option value="">{assays.isPending ? '正在加载化验…' : '请选择煤种 / 批次 / 化验修订'}</option>
            {assays.data?.map(record => <option key={record.id} value={record.id}>{record.label}{record.eligibility.theory.eligible && !record.archived ? '' : ' · 暂不可计算'}</option>)}
          </select>
          {!assays.isPending && !assays.data?.length && <p className="text-mute">尚无化验记录。请先在煤质资料中创建煤种、批次及化验修订。</p>}
          {selected && <>
            <p className="text-sm">{eligible?.eligible ? '该修订的理论计算输入已完整。以下成分已统一到干基；SiO₂ 为灰基。' : '该修订暂不能用于理论计算，请补充新化验修订：'}</p>
            {!!eligible?.issues.length && <ul role="status">{eligible.issues.map(issue => <li key={`${issue.field}-${issue.code}`}>{issue.message}</li>)}</ul>}
            <div className="grid grid--2">{Object.entries({ carbon_content: '元素碳 C_d', hydrogen_content: '元素氢 H_d', ash_content: '灰分 A_d', sio2_content: '灰中 SiO₂' }).map(([key, label]) => <div key={key} className="kv"><span className="kv__k">{label}</span><span className="kv__v">{eligible?.values[key] === undefined ? '未提供' : `${fixed(eligible.values[key], 4)}%`}</span></div>)}</div>
            <details><summary>查看化验换算依据</summary><ul>{eligible?.trace.map((line, index) => <li key={index}>{String(line)}</li>)}</ul></details>
          </>}
        </div></section>
        <ParamPanel title="煤粉热耗参数" fields={HEAT_FIELDS} values={values} onChange={set} />
        <ParamPanel title="焦炭化验 · 干基 C/A 与灰基 SiO₂" fields={COKE_FIELDS} values={values} onChange={set} />
        <section className="panel"><div className="panel__head"><h2 className="panel__title">高炉工艺参数</h2></div><div className="panel__body col gap-16">
          <NumericFields fields={FURNACE_FIELDS} values={values} onChange={set} />
          <label className="row gap-8"><input type="checkbox" checked={allowEstimate} onChange={event => setAllowEstimate(event.target.checked)} />明确使用风温估算鼓风热焓</label>
          <p className="text-xs text-mute">{allowEstimate ? '本次使用 1.3 × 风温的工程估算，结果与历史记录会标注估算来源。' : '请填写所用鼓风热焓；不填时不会自动按风温估算。'}体积口径须与模型风量一致。</p>
          <NumericFields fields={allowEstimate ? [{ id: 'wind_temp', label: '风温', unit: '°C' }] : [{ id: 'hot_blast', label: '鼓风热焓', unit: 'kJ/m³' }]} values={values} onChange={set} />
          <label htmlFor="replacement-source">焦炭、炉况和热耗来源说明</label><input id="replacement-source" className="input" value={values.parameter_source || ''} onChange={event => set('parameter_source', event.target.value)} placeholder="可填写报告编号、统计日期或工程参数依据" />
        </div></section>
      </> : <>
        <section className="panel"><div className="panel__head"><h2 className="panel__title">生产记录口径</h2></div><div className="panel__body col gap-12">
          <label htmlFor="replacement-mass">煤、焦炭耗量的共同质量基准</label><select id="replacement-mass" className="input" value={values.mass_basis || ''} onChange={event => set('mass_basis', event.target.value)}><option value="">请选择已核对的质量基准</option><option value="d">干基 · kg 干煤/干焦每吨铁水</option><option value="ar">收到基 · kg 收到煤/焦每吨铁水</option></select>
          <p className="text-xs text-mute">四项比耗应使用同一高炉、同一铁水统计定义和可比较期间。收到基结果包含实际含水影响；系统不自动将其解释为干基置换比。</p>
          {(['furnace_id', 'period_before', 'period_after'] as const).map((field, index) => <label key={field} className="col gap-8">{['高炉编号', '调整前统计期间', '调整后统计期间'][index]}<input className="input" value={values[field] || ''} onChange={event => set(field, event.target.value)} /></label>)}
        </div></section>
        <ParamPanel title="实际生产数据" fields={ACTUAL_FIELDS} values={values} onChange={set} />
        <section className="panel"><div className="panel__body col gap-12">
          <label className="row gap-8"><input type="checkbox" checked={corrected} onChange={event => setCorrected(event.target.checked)} />使用已有依据的修正量 K</label>
          <p className="text-xs text-mute">{corrected ? '请提供修正量及来源。系统不会套用产量、渣比、碳效率的固定经验权重。' : '未修正公式：焦比减少量 ÷ 煤比增加量。'}煤比变化不能为零。</p>
          {corrected && <><NumericFields fields={[{ id: 'adjustment', label: '修正量 K（可为负）', unit: 'kg/t 铁水' }]} values={values} onChange={set} /><label htmlFor="replacement-correction">修正来源（必填）</label><input id="replacement-correction" className="input" value={values.correction_source || ''} onChange={event => set('correction_source', event.target.value)} /></>}
        </div></section>
      </>}
      {result && <section className="panel"><div className="panel__head"><h2 className="panel__title">本次计算明细</h2></div><div className="panel__body">
        {Object.entries(result.details).map(([label, value]) => <div className="kv" key={label}><span className="kv__k">{label}</span><span className="kv__v">{fixed(value, 6)}</span></div>)}
        {'hot_blast_enthalpy_source' in result && <p className="text-sm">鼓风热焓来源：{result.hot_blast_enthalpy_source === 'temperature_estimate' ? '风温工程估算（已显式选择）' : '用户提供'}；使用值 {fixed(result.effective_hot_blast_enthalpy ?? 0, 3)} kJ/m³。</p>}
        {result.input_snapshot && <p className="text-xs text-mute">已保存计算快照：{result.input_snapshot.assay?.label || '生产期间实测数据'}；设置版本 {result.input_snapshot.settings.version}；操作者 {result.input_snapshot.actor.display_name}。历史记录保留当时原始值与换算口径。</p>}
      </div></section>}
    </div><aside className="split__aside"><section className="panel solve-card"><div className="panel__head"><h2 className="panel__title">计算结果</h2></div><div className="panel__body col gap-16">
      <div className="readout"><span className="readout__label">{mode === 'theory' ? '理论置换比 · 干基' : corrected ? '实际置换比 · 显式修正' : '实际置换比 · 未修正'}</span><span className="readout__value is-ember">{result ? fixed(result.ratio, 4) : '—'}</span><span className="text-xs text-mute">kg 焦 / kg 煤</span></div>
      {error && <p role="alert">{error}</p>}
      <button className="btn btn--primary btn--lg btn--block" disabled={!can('calculate') || mutation.isPending || !settings.data || !!dataError || (mode === 'theory' && (!eligible?.eligible || selected?.archived))} onClick={() => mutation.mutate()}>{mutation.isPending ? '计算中…' : '开始计算'}</button>
      <button className="btn btn--ghost" onClick={reset}><Icon name="reset" size={15} /> 清空输入</button>
      <p className="text-xs text-mute">{mode === 'theory' ? '理论模型是简化的碳氢热平衡计算，包含工程关系和模型常数。输入检查通过不等于现场效果验证，结果须结合高炉生产数据校核。' : '实际置换比反映所选期间的煤焦比变化，不能单独证明变化完全由喷煤造成。'}</p>
    </div></section></aside></div>
  </fieldset>;
}

function NumericFields({ fields, values, onChange }: { fields: NumericField[]; values: ReplacementFields; onChange: (field: string, value: string) => void }) {
  return <div className="grid grid--3 gap-14">{fields.map(field => <Field key={field.id} label={field.label} unit={field.unit} required><input className="input" type="number" step="any" aria-label={field.label} value={values[field.id] ?? ''} onChange={event => onChange(field.id, event.target.value)} /></Field>)}</div>;
}
function ParamPanel({ title, fields, values, onChange }: { title: string; fields: NumericField[]; values: ReplacementFields; onChange: (field: string, value: string) => void }) {
  return <section className="panel"><div className="panel__head"><h2 className="panel__title">{title}</h2></div><div className="panel__body"><NumericFields fields={fields} values={values} onChange={onChange} /></div></section>;
}
