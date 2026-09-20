import { useEffect, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiData, download } from '../lib/http';
import { useSession } from '../lib/session';
import type { Assay } from '../lib/v2';
import { downloadBlob, stamp } from '../lib/format';
import { Modal } from '../components/ui/Overlay';
import { useToast } from '../components/ui/Toast';
import { AssayView } from '../components/catalog/AssayView';
import { AssayEditor } from '../components/catalog/AssayEditor';
import { ImportDialog } from '../components/catalog/ImportDialog';
import '../components/catalog/catalog.css';

interface Batch { id: number; coal_id: number; code: string; supplier: string | null; received_at: string | null; archived: boolean; revision_count: number; latest_assay: Assay | null }
interface CatalogCoal { id: number; name: string; type: string; supplier: string | null; archived: boolean; batches: Batch[] }
type Editor = {kind: 'coal'; coal?: CatalogCoal} | {kind: 'batch'; coal: CatalogCoal} | {kind: 'assay'; batch: Batch; previous?: Assay} | {kind: 'import'};

export default function CoalDatabase() {
  const {can} = useSession(); const toast = useToast(); const cache = useQueryClient();
  const [search, setSearch] = useState(''); const [showArchived, setShowArchived] = useState(false);
  const [coalId, setCoalId] = useState<number | null>(null); const [batchId, setBatchId] = useState<number | null>(null);
  const [revisionId, setRevisionId] = useState<number | null>(null); const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false);
  const query = useQuery({queryKey: ['catalog', showArchived], queryFn: () => apiData<CatalogCoal[]>(`/api/catalog?include_archived=${showArchived}`)});
  const coals = (query.data || []).filter(coal => `${coal.name} ${coal.type} ${coal.supplier || ''}`.toLowerCase().includes(search.toLowerCase()));
  const coal = coals.find(item => item.id === coalId) || coals[0];
  const batches = coal?.batches.filter(batch => showArchived || !batch.archived) || [];
  const batch = batches.find(item => item.id === batchId) || batches[0];
  const assays = useQuery({queryKey: ['catalog-assays', batch?.id], enabled: Boolean(batch), queryFn: () => apiData<Assay[]>(`/api/batches/${batch!.id}/assays`)});
  const assay = assays.data?.find(item => item.id === revisionId) || assays.data?.[0];
  useEffect(() => {setBatchId(null); setRevisionId(null);}, [coal?.id]);
  useEffect(() => {setRevisionId(null);}, [batch?.id]);
  function refresh() {
    void cache.invalidateQueries({queryKey: ['catalog']}); void cache.invalidateQueries({queryKey: ['catalog-assays']});
    void cache.invalidateQueries({queryKey: ['assays']}); void cache.invalidateQueries({queryKey: ['health']});
  }
  function saved() {setEditor(null); setRevisionId(null); refresh(); toast.success('记录已保存');}
  async function archive(url: string, archived: boolean) {
    setBusy(true);
    try {await apiData(url, {method: 'PATCH', body: JSON.stringify({archived})}); refresh(); toast.success(archived ? '已归档，历史记录继续保留' : '已恢复');}
    catch (error) {toast.error('操作失败', (error as Error).message);} finally {setBusy(false);}
  }
  async function exportData(template = false, format = 'xlsx') {
    setBusy(true);
    try {const blob = await download(`/api/catalog/${template ? 'template' : 'export'}?format=${format}&include_archived=true`); downloadBlob(blob, `${template ? 'CBOS化验导入模板' : `CBOS全部化验原值_${stamp()}`}.${format}`);}
    catch (error) {toast.error('下载失败', (error as Error).message);} finally {setBusy(false);}
  }
  return <div className="page catalog-page">
    <div className="page__head"><div><h1 className="page__title">煤种与批次化验</h1><p className="page__lead">保存报告原值，追溯每个批次与修订。缺项可以保存，计算时按所需字段判断资格。</p></div><div className="page__actions">
      {can('export') && <><button className="btn btn--ghost" disabled={busy} onClick={() => void exportData(true)}>下载导入模板</button><button className="btn" disabled={busy} onClick={() => void exportData()}>导出全部原始记录</button><button className="btn btn--ghost" disabled={busy} onClick={() => void exportData(false, 'csv')}>CSV</button></>}
      {can('data_write') && <><button className="btn" onClick={() => setEditor({kind: 'import'})}>文件 / 粘贴导入</button><button className="btn btn--primary" onClick={() => setEditor({kind: 'coal'})}>新增煤种</button></>}
    </div></div>
    <div className="catalog-toolbar"><label>查找煤种<input type="search" placeholder="名称、类型或供应商" value={search} onChange={event => setSearch(event.target.value)} /></label><label className="catalog-check"><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} />显示已归档</label><span className="text-mute">{coals.length} 种煤</span></div>
    {query.isLoading && <p role="status">正在读取煤种与批次…</p>}
    {query.error && <div role="alert" className="catalog-error">{(query.error as Error).message} <button className="btn" onClick={() => void query.refetch()}>重试</button></div>}
    {!query.isLoading && !query.error && !coals.length && <section className="panel catalog-empty"><h2>尚无匹配的煤种</h2><p>{search ? '试试其他名称，或清空搜索。' : can('data_write') ? '先新增煤种与批次，或使用模板导入化验报告。' : '数据维护员录入后，可在此查看原始记录。'}</p></section>}
    {coal && <div className="catalog-layout"><aside className="panel catalog-master-list" aria-label="煤种列表"><h2>煤种主档</h2>{coals.map(item => <button key={item.id} className={`catalog-master ${item.id === coal.id ? 'is-selected' : ''}`} onClick={() => setCoalId(item.id)} aria-pressed={item.id === coal.id}><strong>{item.name}</strong><span>{item.type} · {item.batches.length} 个批次{item.archived ? ' · 已归档' : ''}</span></button>)}</aside>
      <section className="panel catalog-workspace"><header className="catalog-section-head"><div><h2>{coal.name}</h2><p className="text-mute">{coal.type} · {coal.supplier || '主档供应商未填写'}{coal.archived && ' · 已归档'}</p></div>{can('data_write') && <div className="catalog-actions"><button className="btn btn--ghost" onClick={() => setEditor({kind: 'coal', coal})}>编辑主档</button><button className="btn btn--ghost" disabled={busy} onClick={() => void archive(`/api/catalog/${coal.id}`, !coal.archived)}>{coal.archived ? '恢复煤种' : '归档煤种'}</button><button className="btn" disabled={coal.archived} onClick={() => setEditor({kind: 'batch', coal})}>新增批次</button></div>}</header>
        {!batches.length ? <div className="catalog-empty"><h3>还没有可用批次</h3><p>为一批到货创建批次，再录入多份化验记录。</p></div> : <>
          <nav className="catalog-batches" aria-label="批次选择">{batches.map(item => <button key={item.id} className={`catalog-batch ${item.id === batch?.id ? 'is-selected' : ''}`} aria-pressed={item.id === batch?.id} onClick={() => setBatchId(item.id)}><strong>{item.code}</strong><span>{item.received_at || '收货日期未记录'} · {item.revision_count} 份化验{item.archived && ' · 已归档'}</span></button>)}</nav>
          {batch && <><div className="catalog-section-head"><div><h3>批次 {batch.code}</h3><p className="text-mute">供应商：{batch.supplier || '未填写'}</p></div>{can('data_write') && <div className="catalog-actions"><button className="btn btn--ghost" disabled={busy} onClick={() => void archive(`/api/batches/${batch.id}`, !batch.archived)}>{batch.archived ? '恢复批次' : '归档批次'}</button><button className="btn btn--primary" disabled={batch.archived || coal.archived} onClick={() => setEditor({kind: 'assay', batch})}>新增化验</button></div>}</div>
            {assays.isLoading && <p role="status">正在读取修订记录…</p>}{assays.error && <p role="alert" className="catalog-error">{(assays.error as Error).message}</p>}
            {assay ? <><div className="catalog-revisions"><label>查看化验修订<select value={assay.id} onChange={event => setRevisionId(Number(event.target.value))}>{assays.data?.map(item => <option value={item.id} key={item.id}>R{item.revision} · {item.report_number || '无报告编号'} · {item.sampled_at || '采样时间未记录'}</option>)}</select></label>{can('data_write') && <button className="btn" disabled={batch.archived || coal.archived} onClick={() => setEditor({kind: 'assay', batch, previous: assay})}>以此记录新增修订</button>}</div><AssayView assay={assay} /></> : !assays.isLoading && !assays.error && <p className="catalog-note">批次已保存，尚未录入化验。可先保存不完整记录，后续新增修订补全。</p>}
          </>}
        </>}
      </section>
    </div>}
    {editor?.kind === 'import' && <ImportDialog onClose={() => setEditor(null)} onSaved={saved} />}
    {editor?.kind === 'assay' && <AssayEditor batchId={editor.batch.id} previous={editor.previous} onClose={() => setEditor(null)} onSaved={saved} />}
    {editor && (editor.kind === 'coal' || editor.kind === 'batch') && <MetadataEditor editor={editor} onClose={() => setEditor(null)} onSaved={saved} />}
  </div>;
}

function MetadataEditor({editor, onClose, onSaved}: {editor: Extract<Editor, {kind: 'coal' | 'batch'}>; onClose: () => void; onSaved: () => void}) {
  const isBatch = editor.kind === 'batch'; const coal = editor.coal;
  const [name, setName] = useState(isBatch ? '' : coal?.name || ''); const [type, setType] = useState(coal?.type || '');
  const [supplier, setSupplier] = useState(isBatch ? '' : coal?.supplier || ''); const [received, setReceived] = useState('');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const url = isBatch ? `/api/catalog/${coal!.id}/batches` : coal ? `/api/catalog/${coal.id}` : '/api/catalog';
      const body = isBatch ? {code: name, supplier: supplier || null, received_at: received || null} : {name, type, supplier: supplier || null};
      await apiData(url, {method: !isBatch && coal ? 'PATCH' : 'POST', body: JSON.stringify(body)}); onSaved();
    } catch (e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <Modal open title={isBatch ? `新增批次 · ${coal!.name}` : coal ? '编辑煤种主档' : '新增煤种主档'} onClose={onClose}><form className="catalog-form" onSubmit={submit}>
    <label>{isBatch ? '批次编号' : '煤种名称'}<input required autoFocus maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
    {!isBatch && <label>煤种类型<input required maxLength={50} list="catalog-coal-types" value={type} onChange={event => setType(event.target.value)} /><datalist id="catalog-coal-types"><option value="无烟煤" /><option value="烟煤" /></datalist></label>}
    <label>供应商（可留空）<input maxLength={100} value={supplier} onChange={event => setSupplier(event.target.value)} /></label>
    {isBatch && <label>收货日期（可留空）<input type="date" value={received} onChange={event => setReceived(event.target.value)} /></label>}
    <p className="catalog-note">{isBatch ? '批次编号在同一煤种内唯一。各份化验报告保存为独立修订。' : '主档只描述煤种。原始指标在批次化验中录入。'}</p><p className="catalog-error" role="alert">{error}</p><button className="btn btn--primary" disabled={busy}>{busy ? '保存中…' : '保存'}</button>
  </form></Modal>;
}
