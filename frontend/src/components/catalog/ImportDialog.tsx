import { useState } from 'react';
import { Modal } from '../ui/Overlay';
import { apiData } from '../../lib/http';
import { basisLabel, heatLabel, type Assay, type Issue } from '../../lib/v2';
import { metricFields, metricLabel } from './fields';
import { TestDataDownloads } from './TestDataDownloads';

interface Preview {
  headers: {name: string; suggested: string | null; ambiguous: boolean}[];
  mapping: Record<string, string | null>; fields: string[];
  rows: { row: number; coal_name?: string; batch_code?: string; raw: Assay['raw']; issues: Issue[]; eligibility?: Assay['eligibility'] }[];
  issues: Issue[]; can_commit: boolean; preview_token: string | null; expires_at: string | null;
}
const fieldLabel = (field: string) => {
  const identity: Record<string, string> = {coal_name: '煤种名称', type: '煤种类型', batch_code: '批次编号', supplier: '供应商', received_at: '收货日期', sampled_at: '采样日期', report_number: '报告编号', notes: '备注'};
  if (identity[field]) return identity[field];
  const [metric, part] = field.split('.');
  return `${metricLabel(metric)} · ${{value: '原值', unit: '单位', basis: '基准', heat_type: '热值定义', hydrogen_includes_moisture: '含水中氢'}[part] || part}`;
};

export function ImportDialog({onClose, onSaved}: {onClose: () => void; onSaved: () => void}) {
  const [file, setFile] = useState<File | null>(null); const [text, setText] = useState('');
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [metadata, setMetadata] = useState<Record<string, Record<string, unknown>>>({});
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [dirty, setDirty] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  function reset() { setPreview(null); setMapping({}); setMetadata({}); setConfirmed([]); setError(''); setDirty(false); }
  const changeMetadata = (metric: string, part: string, value: unknown) => {
    setMetadata(current => ({...current, [metric]: {...current[metric], [part]: value}})); setDirty(true);
  };
  async function inspect() {
    setBusy(true); setError('');
    try {
      let body: FormData | string;
      const options = {mapping, metric_metadata: metadata, confirmed_headers: confirmed};
      if (file) { body = new FormData(); body.set('file', file); Object.entries(options).forEach(([key, value]) => (body as FormData).set(key, JSON.stringify(value))); }
      else body = JSON.stringify({text, ...options});
      const result = await apiData<Preview>('/api/catalog/import/preview', {method: 'POST', body});
      setPreview(result); setDirty(false);
    } catch (e) { setError((e as Error).message); setDirty(true); } finally { setBusy(false); }
  }
  async function commit() {
    if (!preview?.preview_token || dirty) return;
    setBusy(true); setError('');
    try { await apiData('/api/catalog/import/commit', {method: 'POST', body: JSON.stringify({preview_token: preview.preview_token})}); onSaved(); }
    catch (e) { setError((e as Error).message); setDirty(true); } finally { setBusy(false); }
  }
  return <Modal open title="导入批次化验" subtitle="先确认列映射与原始基准，再一次性写入全部有效行" maxWidth={1150} onClose={onClose}>
    <fieldset className="catalog-form catalog-fieldset" disabled={busy}>
      <TestDataDownloads />
      <div className="catalog-form-grid"><label>选择 CSV / XLSX 文件<input type="file" accept=".csv,.xlsx" onChange={e => {reset(); setFile(e.target.files?.[0] || null); setText('');}} /></label><p className="catalog-note">每次最多 2,000 行、10 MB。同名煤种同批次会追加新修订。原记录不会被覆盖。</p></div>
      <label>或粘贴表格（首行为表头）<textarea rows={5} disabled={Boolean(file)} value={text} placeholder={'煤种名称\t煤种类型\t批次编号\t灰分\n样煤\t烟煤\tB001\t12.5'} onChange={e => {reset(); setText(e.target.value);}} /></label>
      {file && <button className="btn btn--ghost" onClick={() => {setFile(null); reset();}}>清除文件，改为粘贴</button>}
      {preview && <>
        <h3>1. 核对列映射</h3><p className="catalog-note">未知列请明确选择“忽略”。没有报告依据的基准、单位或定义可保持“未确认”，并勾选确认；相关计算会提示缺项。</p>
        <div className="catalog-table-wrap"><table className="catalog-table"><thead><tr><th>原表头</th><th>对应字段</th><th>缺失元信息补充（有报告依据时填写）</th><th>确认</th></tr></thead><tbody>{preview.headers.map(header => {
          const selected = Object.prototype.hasOwnProperty.call(mapping, header.name) ? mapping[header.name] : preview.mapping[header.name];
          const metricKey = selected?.endsWith('.value') ? selected.split('.')[0] : null;
          const metric = metricFields.find(item => item.key === metricKey);
          return <tr key={header.name}><th scope="row">{header.name}{header.ambiguous && <small className="catalog-warning">需核对</small>}</th>
            <td><select aria-label={`${header.name}对应字段`} value={selected || ''} onChange={e => {setMapping(current => ({...current, [header.name]: e.target.value || null})); setDirty(true);}}><option value="">忽略此列</option>{preview.fields.map(field => <option key={field} value={field}>{fieldLabel(field)}</option>)}</select></td>
            <td>{metric && <div className="catalog-mapping-meta">
              <select aria-label={`${header.name}补充单位`} value={String(metadata[metric.key]?.unit || 'unknown')} onChange={e => changeMetadata(metric.key, 'unit', e.target.value)}>{metric.units.map(unit => <option key={unit} value={unit}>{unit === 'unknown' ? '单位未确认' : unit}</option>)}</select>
              <select aria-label={`${header.name}补充基准`} value={String(metadata[metric.key]?.basis || 'unknown')} onChange={e => changeMetadata(metric.key, 'basis', e.target.value)}>{metric.bases.map(basis => <option key={basis} value={basis}>{basisLabel(basis)}</option>)}</select>
              {metric.key === 'calorific_value' && <select aria-label="补充热值定义" value={String(metadata[metric.key]?.heat_type || 'unknown')} onChange={e => changeMetadata(metric.key, 'heat_type', e.target.value)}>{['unknown', 'gr_v', 'net_v', 'net_p'].map(type => <option key={type} value={type}>{heatLabel(type)}</option>)}</select>}
              {metric.key === 'hydrogen_content' && <select aria-label="补充氢定义" value={metadata[metric.key]?.hydrogen_includes_moisture == null ? 'unknown' : String(metadata[metric.key].hydrogen_includes_moisture)} onChange={e => changeMetadata(metric.key, 'hydrogen_includes_moisture', e.target.value === 'unknown' ? null : e.target.value === 'true')}><option value="unknown">水中氢未确认</option><option value="true">包含水中氢</option><option value="false">不含水中氢</option></select>}
            </div>}</td><td><label className="catalog-check"><input type="checkbox" checked={confirmed.includes(header.name)} onChange={e => {setConfirmed(current => e.target.checked ? [...current, header.name] : current.filter(name => name !== header.name)); setDirty(true);}} />已核对，缺失定义保留未知</label></td></tr>;
        })}</tbody></table></div>
        <h3>2. 逐行预览 · {preview.rows.length} 行</h3>
        {preview.issues.length > 0 && <ul className="catalog-issues">{preview.issues.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul>}
        <div className="catalog-table-wrap"><table className="catalog-table"><thead><tr><th>原行号</th><th>煤种 / 批次</th><th>已识别原值</th><th>保存检查 / 计算资格</th></tr></thead><tbody>{preview.rows.slice(0, 100).map(row => <tr key={row.row}><td>{row.row}</td><td>{row.coal_name || '缺煤种名称'} / {row.batch_code || '缺批次'}</td><td>{Object.entries(row.raw).map(([key, value]) => <div key={key}>{metricLabel(key)}：{value.value} {value.unit || '未确认'} · {basisLabel(value.basis || 'unknown')}{value.heat_type && ` · ${heatLabel(value.heat_type)}`}</div>)}</td><td>{row.issues.length ? <ul className="catalog-issues">{row.issues.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul> : <><span>可保存</span>{row.eligibility && <div className="catalog-note">混煤：{row.eligibility.blending.eligible ? '可计算' : '待补充'} · 理论置换比：{row.eligibility.theory.eligible ? '可计算' : '待补充'}</div>}</>}</td></tr>)}</tbody></table></div>
        {preview.rows.length > 100 && <p>表格显示前 100 行；全部 {preview.rows.length} 行均已校验。错误行：{preview.rows.filter(row => row.issues.length).map(row => row.row).join('、') || '无'}。</p>}
        <p role="status">{dirty ? '映射或确认内容已修改，请重新预览。' : preview.can_commit ? '全部行均可保存。未完整化验仅保存原值，不自动取得计算资格。' : '请处理以上问题后重新预览，尚未写入化验记录。'}</p>
      </>}
      <p role="alert" className="catalog-error">{error}</p>
      <div className="catalog-actions"><button className="btn" disabled={busy || (!file && !text.trim())} onClick={() => void inspect()}>{busy ? '处理中…' : preview ? '重新预览' : '解析并预览'}</button><button className="btn btn--primary" disabled={busy || dirty || !preview?.can_commit} onClick={() => void commit()}>确认导入 {preview?.rows.length || 0} 份记录</button></div>
    </fieldset>
  </Modal>;
}
