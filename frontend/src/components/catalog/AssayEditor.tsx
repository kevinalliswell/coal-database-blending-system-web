import { useState, type FormEvent } from 'react';
import { Modal } from '../ui/Overlay';
import { apiData } from '../../lib/http';
import type { Assay, RawMetric } from '../../lib/v2';
import { basisLabel, heatLabel } from '../../lib/v2';
import { metricFields, draftFromRaw, rawFromDraft, type AssayDraft, type MetricDraft } from './fields';
import { EligibilityView } from './AssayView';

export function AssayEditor({ batchId, previous, onClose, onSaved }: { batchId: number; previous?: Assay; onClose: () => void; onSaved: () => void }) {
  const [draft, setDraft] = useState<AssayDraft>(() => draftFromRaw(previous?.raw || {}));
  const [report, setReport] = useState(previous?.report_number || '');
  const [sampled, setSampled] = useState(previous?.sampled_at || '');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Assay['eligibility'] | null>(null);
  const change = (key: string, part: Partial<MetricDraft>) => {
    setDraft(current => ({ ...current, [key]: { ...(current[key] || { value: '', unit: 'unknown', basis: 'unknown' }), ...part } }));
    setPreview(null);
  };
  async function evaluate() {
    setError(''); setBusy(true);
    try { const result = await apiData<{eligibility: Assay['eligibility']}>('/api/assays/preview', { method: 'POST', body: JSON.stringify({raw: rawFromDraft(draft)}) }); setPreview(result.eligibility); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      await apiData(`/api/batches/${batchId}/assays`, { method: 'POST', body: JSON.stringify({ raw: rawFromDraft(draft), report_number: report || null, sampled_at: sampled || null, notes: notes || null }) });
      onSaved();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Modal open onClose={onClose} title={previous ? `由 R${previous.revision} 新增修订` : '新增化验记录'} maxWidth={1050}>
    <form className="catalog-form" onSubmit={save}>
      <fieldset disabled={busy} className="catalog-fieldset">
      <p className="catalog-note">按报告原值填写。缺项可以保存；单位、基准和热值定义不明确时请选择“未确认”。保存会新增修订，原记录完整保留。</p>
      <div className="catalog-form-grid"><label>报告编号<input value={report} maxLength={120} onChange={e => setReport(e.target.value)} /></label><label>采样日期<input type="date" value={sampled.slice(0, 10)} onChange={e => setSampled(e.target.value)} /></label><label>本次修订说明<input value={notes} maxLength={10000} onChange={e => setNotes(e.target.value)} /></label></div>
      <div className="catalog-table-wrap"><table className="catalog-table catalog-editor"><thead><tr><th>指标</th><th>原始值（留空表示缺失）</th><th>单位</th><th>原始基准</th><th>指标定义</th></tr></thead><tbody>
        {metricFields.map(field => { const item = draft[field.key]; return <tr key={field.key}>
          <th scope="row">{field.label}</th><td><input aria-label={`${field.label}原值`} type="number" step="any" min="0" value={item?.value || ''} onChange={e => change(field.key, {value: e.target.value})} /></td>
          <td><select aria-label={`${field.label}单位`} value={item?.unit || 'unknown'} onChange={e => change(field.key, {unit: e.target.value})}>{field.units.map(unit => <option key={unit} value={unit}>{unit === 'unknown' ? '未确认' : unit}</option>)}</select></td>
          <td><select aria-label={`${field.label}基准`} value={item?.basis || 'unknown'} onChange={e => change(field.key, {basis: e.target.value as RawMetric['basis']})}>{field.bases.map(basis => <option key={basis} value={basis}>{basisLabel(basis)}</option>)}</select></td>
          <td>{field.key === 'calorific_value' && <select aria-label="热值定义" value={item?.heat_type || 'unknown'} onChange={e => change(field.key, {heat_type: e.target.value as RawMetric['heat_type']})}>{['unknown', 'gr_v', 'net_v', 'net_p'].map(type => <option key={type} value={type}>{heatLabel(type)}</option>)}</select>}
          {field.key === 'hydrogen_content' && <select aria-label="元素氢是否含水中氢" value={item?.hydrogen_includes_moisture == null ? 'unknown' : String(item.hydrogen_includes_moisture)} onChange={e => change(field.key, {hydrogen_includes_moisture: e.target.value === 'unknown' ? null : e.target.value === 'true'})}><option value="unknown">未确认</option><option value="true">包含水中氢</option><option value="false">不含水中氢</option></select>}</td>
        </tr>; })}
      </tbody></table></div>
      <p className="catalog-error" role="alert">{error}</p>
      {preview && <EligibilityView eligibility={preview} />}
      <div className="catalog-actions"><button className="btn" type="button" disabled={busy} onClick={() => void evaluate()}>检查计算资格与换算</button><button className="btn btn--primary" disabled={busy} type="submit">{busy ? '处理中…' : '保存为新修订'}</button></div>
      </fieldset>
    </form>
  </Modal>;
}
