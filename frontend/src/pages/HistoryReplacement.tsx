import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { repHistory, repHistoryDetail } from '../lib/api';
import { qk } from '../lib/query';
import { Icon } from '../components/ui/Icon';
import { EmptyState, SkeletonRows, StatPanel, StatusPill } from '../components/ui/bits';
import { QueryError } from '../components/ui/QueryError';
import { Drawer } from '../components/ui/Overlay';
import { fixed, shortDate, num } from '../lib/format';
import { useDebounced } from '../hooks/useDebounced';

type ModeFilter = 'all' | 'theory' | 'basic' | 'advanced';
const PAGE = 10;

export default function HistoryReplacement() {
  const hist = useQuery({ queryKey: qk.repHistory, queryFn: repHistory });
  const [q, setQ] = useState('');
  const search = useDebounced(q, 200);
  const [mode, setMode] = useState<ModeFilter>('all');
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);

  const rows = hist.data ?? [];
  const filtered = useMemo(
    () =>
      rows.filter(
        (r) => (mode === 'all' || r.calculation_mode === mode) && (!search || r.parameter_summary.includes(search))
      ),
    [rows, mode, search]
  );
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const pageRows = filtered.slice((page - 1) * PAGE, page * PAGE);

  const theoryCount = rows.filter((r) => r.calculation_type === 'theory').length;
  const actualCount = rows.filter((r) => r.calculation_type === 'actual').length;

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">置换比计算历史</h1>
          <p className="page__lead">回看理论与实际置换比的计算参数与结果。</p>
        </div>
      </div>

      <div className="grid grid--4 mb-20">
        <StatPanel label="历史记录" value={num(rows.length)} icon="history" tone="cyan" />
        <StatPanel label="理论置换比" value={num(theoryCount)} icon="beaker" tone="ember" />
        <StatPanel label="实际置换比" value={num(actualCount)} icon="scale" tone="cyan" />
        <StatPanel label="最近结果" value={rows[0] ? fixed(rows[0].ratio_value, 4) : '—'} icon="target" tone="ember" />
      </div>

      <div className="panel">
        <div className="panel__body" style={{ paddingBottom: 0 }}>
          <div className="row gap-12 wrap between">
            <div className="input-adorn" style={{ width: 260, maxWidth: '100%' }}>
              <span className="tico"><Icon name="search" size={15} /></span>
              <input className="input" placeholder="搜索参数摘要" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
            </div>
            <div className="segmented">
              {(['all', 'theory', 'basic', 'advanced'] as ModeFilter[]).map((m) => (
                <button key={m} className={`segmented__item${mode === m ? ' is-active' : ''}`} onClick={() => { setMode(m); setPage(1); }}>
                  {m === 'all' ? '全部' : m === 'theory' ? '理论' : m === 'basic' ? '基础' : '修正'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="panel__body">
          {hist.isError ? (
            <QueryError message="历史记录读取失败" onRetry={() => void hist.refetch()} />
          ) : hist.isLoading ? (
            <SkeletonRows rows={6} cols={5} />
          ) : filtered.length === 0 ? (
            <EmptyState icon="history" title={rows.length ? "没有匹配的记录" : "暂无历史记录"} sub="进行一次置换比计算后，记录会显示在这里。" />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>类型</th>
                    <th>模式</th>
                    <th className="num">置换比</th>
                    <th>参数摘要</th>
                    <th style={{ width: 80 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((r) => (
                    <tr key={r.id}>
                      <td className="mono text-sm nowrap">{shortDate(r.date)}</td>
                      <td>
                        {r.calculation_type === 'theory' ? <StatusPill tone="ember">理论</StatusPill> : <StatusPill tone="cyan">实际</StatusPill>}
                      </td>
                      <td className="text-sm">{r.calculation_mode === 'theory' ? '理论模型' : r.calculation_mode === 'basic' ? '基础' : '生产修正'}</td>
                      <td className="num text-ember fw-600">{fixed(r.ratio_value, 4)}</td>
                      <td className="text-sm text-mute truncate" style={{ maxWidth: 320 }}>{r.parameter_summary}</td>
                      <td>
                        <button className="btn btn--sm btn--ghost" onClick={() => setOpenId(r.id)}>
                          <Icon name="eye" size={14} /> 详情
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {filtered.length > PAGE && (
          <div className="panel__head" style={{ borderTop: '1px solid var(--line)', borderBottom: 'none' }}>
            <span className="text-sm text-mute mono">共 {filtered.length} 条</span>
            <div className="row gap-4">
              <button className="btn btn--sm btn--ghost btn-icon" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}><Icon name="chevronLeft" size={15} /></button>
              <span className="pill">{page} / {totalPages}</span>
              <button className="btn btn--sm btn--ghost btn-icon" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}><Icon name="chevronRight" size={15} /></button>
            </div>
          </div>
        )}
      </div>

      <RepDetailDrawer id={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}

function RepDetailDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const detail = useQuery({
    queryKey: qk.repHistoryDetail(id ?? -1),
    queryFn: () => repHistoryDetail(id!),
    enabled: id !== null,
  });
  const [showRaw, setShowRaw] = useState(false);
  const d = detail.data;
  const details = (d?.result_payload?.details as Record<string, number> | undefined) ?? null;

  return (
    <Drawer open={id !== null} onClose={onClose} title="置换比计算详情" subtitle={d ? shortDate(d.date) : ''} icon={<Icon name="scale" size={18} />}>
      {detail.isError ? (
        <QueryError message="详情读取失败" onRetry={() => void detail.refetch()} />
      ) : detail.isLoading || !d ? (
        <SkeletonRows rows={8} cols={2} />
      ) : (
        <div className="col gap-18">
          <div style={{ textAlign: 'center', padding: '10px 0' }}>
            <div className="readout__label">{d.calculation_type === 'theory' ? '理论置换比' : '实际置换比'}</div>
            <div className="readout__value is-ember" style={{ fontSize: 44, marginTop: 6 }}>{fixed(d.ratio_value, 4)}</div>
            <div className="row gap-8 center mt-8">
              {d.calculation_type === 'theory' ? <StatusPill tone="ember">理论</StatusPill> : <StatusPill tone="cyan">实际</StatusPill>}
              <span className="pill pill--mute">{d.calculation_mode}</span>
            </div>
          </div>

          <div>
            <div className="eyebrow mb-8">参数摘要</div>
            <div className="text-sm text-soft">{d.parameter_summary}</div>
          </div>

          {details && (
            <div>
              <div className="eyebrow mb-8">计算明细</div>
              {Object.entries(details).map(([k, v]) => (
                <div key={k} className="kv">
                  <span className="kv__k">{k}</span>
                  <span className="kv__v">{typeof v === 'number' ? fixed(v, 6) : String(v)}</span>
                </div>
              ))}
            </div>
          )}

          <div>
            <button className="btn btn--ghost btn--sm" onClick={() => setShowRaw((s) => !s)}>
              <Icon name={showRaw ? 'chevronUp' : 'chevronDown'} size={14} /> {showRaw ? '收起原始数据' : '查看原始请求/结果'}
            </button>
            {showRaw && (
              <div className="col gap-10 mt-10">
                <div>
                  <div className="text-xs text-mute mb-4">请求快照</div>
                  <pre className="raw">{JSON.stringify(d.request_payload, null, 2)}</pre>
                </div>
                <div>
                  <div className="text-xs text-mute mb-4">结果快照</div>
                  <pre className="raw">{JSON.stringify(d.result_payload, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}
