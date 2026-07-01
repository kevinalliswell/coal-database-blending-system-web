import { useMemo, useRef, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  batchDeleteCoals,
  coalTypes,
  createCoal,
  deleteCoal,
  downloadTemplate,
  exportCoals,
  listCoals,
  updateCoal,
  uploadCoals,
} from '../lib/api';
import type { Coal, CoalDraft } from '../lib/types';
import { COAL_FIELDS } from '../lib/constants';
import { Icon } from '../components/ui/Icon';
import { EmptyState, SkeletonRows } from '../components/ui/bits';
import { Drawer, Modal, ConfirmDialog } from '../components/ui/Overlay';
import { CoalForm } from '../components/CoalForm';
import { useToast } from '../components/ui/Toast';
import { downloadBlob, fixed, num, stamp } from '../lib/format';
import { useDebounced } from '../hooks/useDebounced';

export default function CoalDatabase() {
  const toast = useToast();
  const qc = useQueryClient();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchInput, setSearchInput] = useState('');
  const search = useDebounced(searchInput, 250);
  const [type, setType] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Coal | null>(null);
  const [detail, setDetail] = useState<Coal | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [confirm, setConfirm] = useState<null | { ids: number[]; label: string }>(null);

  const query = useMemo(() => ({ page, page_size: pageSize, search, type }), [page, pageSize, search, type]);
  const coals = useQuery({
    queryKey: ['coals', query],
    queryFn: () => listCoals(query),
    placeholderData: keepPreviousData,
  });
  const types = useQuery({ queryKey: ['coalTypes'], queryFn: coalTypes });

  const rows = coals.data?.data ?? [];
  const pag = coals.data?.pagination;
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['coals'] });
    qc.invalidateQueries({ queryKey: ['coalTypes'] });
    qc.invalidateQueries({ queryKey: ['health'] });
  };

  const saveMut = useMutation({
    mutationFn: (d: CoalDraft) => (editing ? updateCoal(editing.id, d) : createCoal(d)),
    onSuccess: () => {
      toast.success(editing ? '煤种已更新' : '煤种已添加');
      setFormOpen(false);
      setEditing(null);
      invalidate();
    },
    onError: (e: Error) => toast.error('保存失败', e.message),
  });

  const delMut = useMutation({
    mutationFn: (ids: number[]) => (ids.length === 1 ? deleteCoal(ids[0]).then(() => 1) : batchDeleteCoals(ids)),
    onSuccess: (_n, ids) => {
      toast.success(`已删除 ${ids.length} 条煤种`);
      setSelected((s) => {
        const next = new Set(s);
        ids.forEach((i) => next.delete(i));
        return next;
      });
      invalidate();
    },
    onError: (e: Error) => toast.error('删除失败', e.message),
  });

  const exportMut = useMutation({
    mutationFn: (ids: number[] | null) => exportCoals(ids),
    onSuccess: (blob) => {
      const ext = blob.type.includes('csv') ? 'csv' : 'xlsx';
      downloadBlob(blob, `煤种数据导出_${stamp()}.${ext}`);
      toast.success('导出完成');
    },
    onError: (e: Error) => toast.error('导出失败', e.message),
  });

  const allOnPageSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const someOnPageSelected = rows.some((r) => selected.has(r.id));

  const toggleAllOnPage = () => {
    setSelected((s) => {
      const next = new Set(s);
      if (allOnPageSelected) rows.forEach((r) => next.delete(r.id));
      else rows.forEach((r) => next.add(r.id));
      return next;
    });
  };
  const toggleOne = (id: number) =>
    setSelected((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">煤种数据库</h1>
          <p className="page__lead">维护煤种的工业分析与元素分析指标，作为混煤优化的数据基础。</p>
        </div>
        <div className="page__actions">
          <button className="btn btn--ghost" onClick={() => downloadTemplate().then((b) => downloadBlob(b, `煤种导入模板.csv`))}>
            <Icon name="download" size={15} /> 导入模板
          </button>
          <button className="btn btn--ghost" onClick={() => setImportOpen(true)}>
            <Icon name="upload" size={15} /> 批量导入
          </button>
          <button className="btn btn--ghost" onClick={() => exportMut.mutate(null)}>
            <Icon name="download" size={15} /> 导出全部
          </button>
          <button
            className="btn btn--primary"
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Icon name="plus" size={15} /> 添加煤种
          </button>
        </div>
      </div>

      <div className="panel">
        {/* toolbar */}
        <div className="panel__body" style={{ paddingBottom: 0 }}>
          <div className="row gap-12 wrap between">
            <div className="row gap-10 wrap grow">
              <div className="input-adorn" style={{ width: 260, maxWidth: '100%' }}>
                <span className="tico"><Icon name="search" size={15} /></span>
                <input
                  className="input"
                  placeholder="搜索名称 / 类型 / 供应商"
                  value={searchInput}
                  onChange={(e) => {
                    setSearchInput(e.target.value);
                    setPage(1);
                  }}
                />
              </div>
              <select
                className="select"
                style={{ width: 150 }}
                value={type}
                onChange={(e) => {
                  setType(e.target.value);
                  setPage(1);
                }}
              >
                <option value="">所有类型</option>
                {(types.data ?? []).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select className="select" style={{ width: 120 }} value={pageSize} onChange={(e) => { setPageSize(+e.target.value); setPage(1); }}>
                {[10, 20, 50].map((n) => (
                  <option key={n} value={n}>
                    每页 {n} 条
                  </option>
                ))}
              </select>
            </div>
            <div className="row gap-10">
              {selected.size > 0 && (
                <>
                  <span className="pill pill--ember">已选 {selected.size} 项</span>
                  <button className="btn btn--sm btn--ghost" onClick={() => exportMut.mutate([...selected])}>
                    <Icon name="download" size={14} /> 导出选中
                  </button>
                  <button className="btn btn--sm btn--danger btn--ghost" onClick={() => setConfirm({ ids: [...selected], label: `选中的 ${selected.size} 条` })}>
                    <Icon name="trash" size={14} /> 删除选中
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* table */}
        <div className="panel__body">
          {coals.isLoading ? (
            <SkeletonRows rows={pageSize > 10 ? 8 : 6} cols={7} />
          ) : rows.length === 0 ? (
            <EmptyState icon="database" title="没有匹配的煤种" sub="调整搜索或类型筛选，或添加新的煤种记录。" />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl" style={{ minWidth: 720 }}>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>
                      <input
                        type="checkbox"
                        className={`check${!allOnPageSelected && someOnPageSelected ? ' check--indeterminate' : ''}`}
                        checked={allOnPageSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = !allOnPageSelected && someOnPageSelected;
                        }}
                        onChange={toggleAllOnPage}
                      />
                    </th>
                    <th>煤种信息</th>
                    <th className="num">价格 <span className="text-xs text-mute">元/吨</span></th>
                    <th className="num">热值 <span className="text-xs text-mute">kcal/kg</span></th>
                    <th className="num">灰分 %</th>
                    <th className="num">挥发分 %</th>
                    <th className="num">全硫 %</th>
                    <th style={{ width: 108 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => (
                    <tr key={c.id} className={selected.has(c.id) ? 'is-selected' : ''}>
                      <td>
                        <input type="checkbox" className="check" checked={selected.has(c.id)} onChange={() => toggleOne(c.id)} />
                      </td>
                      <td style={{ minWidth: 210 }}>
                        <div className="fw-500" style={{ lineHeight: 1.3 }}>{c.name}</div>
                        <div className="row gap-8 items-center mt-4">
                          <span className="tag tag--type">{c.type}</span>
                          <span className="text-xs text-mute">{c.supplier || '—'} · #{c.id}</span>
                        </div>
                      </td>
                      <td className="num text-ember">{fixed(c.price, 1)}</td>
                      <td className="num">{num(c.calorific_value)}</td>
                      <td className="num">{fixed(c.ash_content, 1)}</td>
                      <td className="num">{fixed(c.volatile_matter, 1)}</td>
                      <td className="num">{fixed(c.total_sulfur, 2)}</td>
                      <td>
                        <div className="row gap-4">
                          <button className="btn btn-icon btn--ghost" title="详情" onClick={() => setDetail(c)}>
                            <Icon name="eye" size={15} />
                          </button>
                          <button className="btn btn-icon btn--ghost" title="编辑" onClick={() => { setEditing(c); setFormOpen(true); }}>
                            <Icon name="edit" size={15} />
                          </button>
                          <button className="btn btn-icon btn--ghost" title="删除" onClick={() => setConfirm({ ids: [c.id], label: c.name })}>
                            <Icon name="trash" size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* footer */}
        {pag && rows.length > 0 && (
          <div className="panel__head" style={{ borderTop: '1px solid var(--line)', borderBottom: 'none' }}>
            <span className="text-sm text-mute mono">
              第 {(pag.page - 1) * (pag.page_size || rows.length) + 1}–{(pag.page - 1) * (pag.page_size || rows.length) + rows.length} 条 / 共 {pag.total} 条
            </span>
            <Pager page={pag.page} totalPages={pag.total_pages} onPage={setPage} />
          </div>
        )}
      </div>

      {/* Add / Edit drawer */}
      <Drawer
        open={formOpen}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        title={editing ? '编辑煤种' : '添加煤种'}
        subtitle={editing ? editing.name : '录入新的煤种指标'}
        icon={<Icon name={editing ? 'edit' : 'plus'} size={18} />}
        wide
        footer={
          <>
            <button className="btn btn--ghost" onClick={() => { setFormOpen(false); setEditing(null); }}>
              取消
            </button>
            <button className="btn btn--primary" type="submit" form="coalForm" disabled={saveMut.isPending}>
              {saveMut.isPending ? <span className="spinner" /> : <Icon name="save" size={15} />}
              {editing ? '保存修改' : '添加煤种'}
            </button>
          </>
        }
      >
        <CoalForm
          key={editing?.id ?? 'new'}
          coal={editing}
          formId="coalForm"
          submitting={saveMut.isPending}
          onSubmit={(d) => saveMut.mutate(d)}
          onCancel={() => { setFormOpen(false); setEditing(null); }}
        />
      </Drawer>

      {/* Detail drawer */}
      <Drawer
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail?.name ?? ''}
        subtitle={detail ? `${detail.type} · ${detail.supplier || '未标注产地'}` : ''}
        icon={<Icon name="database" size={18} />}
        footer={
          <button className="btn btn--primary" onClick={() => { if (detail) { setEditing(detail); setDetail(null); setFormOpen(true); } }}>
            <Icon name="edit" size={15} /> 编辑此煤种
          </button>
        }
      >
        {detail && (
          <div>
            {COAL_FIELDS.filter((f) => f.key !== 'name').map((f) => (
              <div key={f.key} className="kv">
                <span className="kv__k">{f.label}{f.unit ? ` (${f.unit})` : ''}</span>
                <span className="kv__v">{formatVal(detail[f.key])}</span>
              </div>
            ))}
          </div>
        )}
      </Drawer>

      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} onDone={invalidate} />

      <ConfirmDialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        onConfirm={() => confirm && delMut.mutate(confirm.ids)}
        title="删除煤种"
        danger
        confirmText="确认删除"
        message={<>确定删除 <b className="text-ink">{confirm?.label}</b>？此操作不可撤销。</>}
      />
    </div>
  );
}

function formatVal(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  if (typeof v === 'string' && v.length > 19 && v.includes('T')) return v.replace('T', ' ').slice(0, 19);
  return String(v);
}

function Pager({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (p: number) => void }) {
  const pages: number[] = [];
  const lo = Math.max(1, page - 2);
  const hi = Math.min(totalPages, page + 2);
  for (let i = lo; i <= hi; i++) pages.push(i);
  return (
    <div className="row gap-4">
      <button className="btn btn--sm btn--ghost btn-icon" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <Icon name="chevronLeft" size={15} />
      </button>
      {lo > 1 && (
        <>
          <button className="btn btn--sm btn--ghost" onClick={() => onPage(1)}>1</button>
          {lo > 2 && <span className="text-mute px-4">…</span>}
        </>
      )}
      {pages.map((p) => (
        <button key={p} className={`btn btn--sm ${p === page ? 'btn--primary' : 'btn--ghost'}`} onClick={() => onPage(p)}>
          {p}
        </button>
      ))}
      {hi < totalPages && (
        <>
          {hi < totalPages - 1 && <span className="text-mute px-4">…</span>}
          <button className="btn btn--sm btn--ghost" onClick={() => onPage(totalPages)}>{totalPages}</button>
        </>
      )}
      <button className="btn btn--sm btn--ghost btn-icon" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
        <Icon name="chevronRight" size={15} />
      </button>
    </div>
  );
}

function ImportModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<{ created_count: number; updated_count: number; skipped_count: number; errors: string[] } | null>(null);

  const mut = useMutation({
    mutationFn: (f: File) => uploadCoals(f),
    onSuccess: (r) => {
      setResult(r);
      toast.success('导入完成', r.message);
      onDone();
    },
    onError: (e: Error) => toast.error('导入失败', e.message),
  });

  return (
    <Modal
      open={open}
      onClose={() => { setFile(null); setResult(null); onClose(); }}
      title="批量导入煤种"
      subtitle="支持 CSV（演示模式）/ Excel（连接后端时）"
      icon={<Icon name="upload" size={18} />}
      footer={
        <>
          <button className="btn btn--ghost" onClick={() => { setFile(null); setResult(null); onClose(); }}>关闭</button>
          <button className="btn btn--primary" disabled={!file || mut.isPending} onClick={() => file && mut.mutate(file)}>
            {mut.isPending ? <span className="spinner" /> : <Icon name="upload" size={15} />} 开始导入
          </button>
        </>
      }
    >
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) setFile(f);
        }}
        style={{
          border: '1.5px dashed var(--line-strong)',
          borderRadius: 'var(--r-lg)',
          padding: '32px 20px',
          textAlign: 'center',
          cursor: 'pointer',
          background: 'var(--surface-inset)',
        }}
      >
        <Icon name="upload" size={28} className="text-ember" />
        <div className="fw-500 mt-8">{file ? file.name : '点击选择或拖拽文件到此处'}</div>
        <div className="text-xs text-mute mt-4">列顺序需与导入模板一致</div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: 'none' }}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>
      {result && (
        <div className="mt-16 col gap-8">
          <div className="row gap-10">
            <span className="pill pill--live">新增 {result.created_count}</span>
            <span className="pill pill--cyan">更新 {result.updated_count}</span>
            <span className="pill pill--mute">跳过 {result.skipped_count}</span>
          </div>
          {result.errors.length > 0 && (
            <div className="raw text-danger">{result.errors.join('\n')}</div>
          )}
        </div>
      )}
    </Modal>
  );
}
