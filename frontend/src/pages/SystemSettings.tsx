import { useEffect, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/http';
import { CONSTRAINT_ROWS, GA_FIELDS } from '../lib/constants';
import { useSession } from '../lib/session';
import { basisLabel, getSettings, heatCanonical, heatDisplay, heatLabel, type Settings } from '../lib/v2';

export default function SystemSettings() {
  const { can } = useSession();
  const cache = useQueryClient();
  const [saved, setSaved] = useState<Settings | null>(null);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function load() {
    const value = await getSettings(); setSaved(value); setDraft(structuredClone(value)); setConfirmed(false); setError(''); setMessage('');
  }
  useEffect(() => { if (can('admin')) void load().catch(e => setError(e.message)); }, []);
  if (!can('admin')) return <div className="page"><p>需要管理员权限。</p></div>;
  if (!draft || !saved) return <div className="page"><p role="status">{error || '正在读取系统设置…'}</p>{error && <button className="btn" onClick={() => void load().catch(e => setError(e.message))}>重试</button>}</div>;
  const changedBasis = draft.ratio_basis !== saved.ratio_basis || draft.heat_type !== saved.heat_type;
  const update = (patch: Partial<Settings>) => { setDraft({...draft, ...patch}); setMessage(''); if ('ratio_basis' in patch || 'heat_type' in patch) setConfirmed(false); };
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setMessage(''); setBusy(true);
    try {
      const result = await api<{ data: Settings }>('/api/settings', {method: 'PUT', body: JSON.stringify({...draft, constraints_confirmed: confirmed})});
      setSaved(result.data); setDraft(structuredClone(result.data)); setConfirmed(false); setMessage(`已保存 · 版本 ${result.data.version}`);
      await cache.invalidateQueries({queryKey: ['settings']}); await cache.invalidateQueries({queryKey: ['assays']}); await cache.invalidateQueries({queryKey: ['catalog']});
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <div className="page"><div className="page__head"><div><h1 className="page__title">系统设置</h1><p className="page__lead">当前版本 {saved.version} · 新计算使用这些默认值。历史记录保留当时的设置快照。</p></div></div>
    <form className="v2-form" onSubmit={submit}><fieldset disabled={busy} style={{border: 0, padding: 0, minWidth: 0}}>
      <section className="panel v2-card"><h2>名称与计算口径</h2><div className="v2-grid">
        <label>系统名称<input required maxLength={80} value={draft.system_name} onChange={e => update({system_name: e.target.value})} /></label><label>所属组织<input maxLength={160} value={draft.organization} onChange={e => update({organization: e.target.value})} /></label>
        <label>配比质量基准<select value={draft.ratio_basis} onChange={e => update({ratio_basis: e.target.value as Settings['ratio_basis']})}>{(['ar', 'd'] as const).map(value => <option key={value} value={value}>{basisLabel(value)}</option>)}</select></label>
        <label>目标热值类型<select value={draft.heat_type} onChange={e => update({heat_type: e.target.value as Settings['heat_type']})}>{(['net_v', 'gr_v'] as const).map(value => <option key={value} value={value}>{heatLabel(value)}</option>)}</select></label>
        <label>热值显示单位<select value={draft.heat_unit} onChange={e => update({heat_unit: e.target.value as Settings['heat_unit']})}><option>MJ/kg</option><option>kcal/kg</option></select></label>
      </div><p className="text-mute">修改质量基准或热值类型不会自动换算工艺约束，需按新的口径重新核实全部上下限。切换显示单位只改变热值展示。</p></section>
      <section className="panel v2-card"><h2>默认工艺约束</h2><div className="v2-grid">{CONSTRAINT_ROWS.map(row => <div key={row.key}><h3>{row.label} · {row.key === 'heat' ? draft.heat_unit : row.unit}</h3><div className="v2-grid">{([['下限', row.min], ['上限', row.max]] as const).map(([label, key]) => <label key={key}>{row.label}{label}<input required type="number" min={0} max={['ash', 'volatile', 'fixed_carbon', 'sulfur'].includes(row.key) ? 100 : undefined} step="any" value={row.key === 'heat' ? Number(heatDisplay(Number(draft.constraints[key]), draft.heat_unit).toPrecision(12)) : Number(draft.constraints[key])} onChange={e => update({constraints: {...draft.constraints, [key]: row.key === 'heat' ? heatCanonical(e.target.valueAsNumber, draft.heat_unit) : e.target.valueAsNumber}})} /></label>)}</div></div>)}</div>
        {changedBasis && <label style={{marginTop: 20}}><span><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> 我已按新的质量基准和热值类型核实上述全部约束</span></label>}
      </section>
      <section className="panel v2-card"><h2>默认优化参数</h2><div className="v2-grid">{GA_FIELDS.map(field => <label key={field.key}>{field.label}<input type="number" required={field.key !== 'random_seed'} min={field.min} max={field.max} step={field.step || 1} value={draft.ga_params[field.key] == null ? '' : Number(draft.ga_params[field.key])} onChange={e => { const ga = {...draft.ga_params}; if (field.key === 'random_seed' && !e.target.value) delete ga.random_seed; else Object.assign(ga, {[field.key]: e.target.valueAsNumber}); update({ga_params: ga}); }} /><span className="text-mute">{field.hint}</span></label>)}</div><label style={{marginTop: 20}}><span><input type="checkbox" checked={draft.ga_params.adaptive_mutation} onChange={e => update({ga_params: {...draft.ga_params, adaptive_mutation: e.target.checked}})} /> 自适应变异</span></label></section>
      <div className="v2-actions"><button className="btn btn--primary" disabled={busy || (changedBasis && !confirmed)}>{busy ? '正在保存…' : '保存设置'}</button><button className="btn btn--ghost" type="button" onClick={() => void load().catch(e => setError(e.message))}>重新加载，放弃未保存修改</button><span role="status">{message}</span></div>
      <p role="alert" className="v2-error">{error}</p>
    </fieldset></form></div>;
}
