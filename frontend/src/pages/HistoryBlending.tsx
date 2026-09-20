import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { optHistory, optHistoryDetail } from '../lib/api';
import { qk } from '../lib/query';
import { dataValidationLabel } from '../lib/blendingResult';
import { historyProvenance } from '../lib/historyProvenance';
import { Icon } from '../components/ui/Icon';
import { EmptyState, SkeletonRows, StatPanel, StatusPill } from '../components/ui/bits';
import { QueryError } from '../components/ui/QueryError';
import { Drawer } from '../components/ui/Overlay';
import { RatioDonut } from '../components/blending/charts';
import { fixed, num, shortDate } from '../lib/format';
import { useDebounced } from '../hooks/useDebounced';

type Feas = 'all' | 'feasible' | 'infeasible';
const PAGE = 8;

export default function HistoryBlending() {
  const hist = useQuery({ queryKey: qk.optHistory, queryFn: optHistory });
  const [q, setQ] = useState('');
  const search = useDebounced(q, 200);
  const [feas, setFeas] = useState<Feas>('all');
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);

  const rows = hist.data ?? [];
  const filtered = useMemo(
    () =>
      rows.filter(
        (r) =>
          (feas === 'all' || (feas === 'feasible' ? r.constraints_satisfied : !r.constraints_satisfied)) &&
          (!search || r.coal_names.some((n) => n.includes(search)))
      ),
    [rows, feas, search]
  );
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const pageRows = filtered.slice((page - 1) * PAGE, page * PAGE);

  const feasibleCount = rows.filter((r) => r.constraints_satisfied).length;

  return (
    <div className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">混煤优化历史</h1>
          <p className="page__lead">回看每一次混煤优化的推荐配比、关键指标与可行性判断。各次计算口径见详情，不同口径的价格与热值不能直接比较。</p>
        </div>
      </div>

      <div className="grid grid--4 mb-20">
        <StatPanel label="历史记录" value={num(rows.length)} icon="history" tone="cyan" />
        <StatPanel label="可行方案" value={num(feasibleCount)} icon="checkCircle" tone="ember" />
        <StatPanel label="未满足数值约束" value={num(rows.length - feasibleCount)} icon="chart" tone="cyan" />
        <StatPanel label="最近运行" value={rows[0] ? shortDate(rows[0].date).slice(5, 16) : '—'} icon="activity" tone="ember" />
      </div>

      <div className="panel">
        <div className="panel__body" style={{ paddingBottom: 0 }}>
          <div className="row gap-12 wrap between">
            <div className="input-adorn" style={{ width: 260, maxWidth: '100%' }}>
              <span className="tico"><Icon name="search" size={15} /></span>
              <input className="input" placeholder="搜索煤种名称" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
            </div>
            <div className="segmented">
              {(['all', 'feasible', 'infeasible'] as Feas[]).map((f) => (
                <button key={f} className={`segmented__item${feas === f ? ' is-active' : ''}`} onClick={() => { setFeas(f); setPage(1); }}>
                  {f === 'all' ? '全部' : f === 'feasible' ? '可行' : '不可行'}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="panel__body">
          {hist.isError ? (
            <QueryError message="历史记录读取失败" onRetry={() => void hist.refetch()} />
          ) : hist.isLoading ? (
            <SkeletonRows rows={6} cols={6} />
          ) : filtered.length === 0 ? (
            <EmptyState icon="history" title={rows.length ? "没有匹配的记录" : "暂无历史记录"} sub="运行一次混煤优化后，记录会显示在这里。" />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>煤种与配比</th>
                    <th className="num">吨煤成本</th>
                    <th className="num">热值 kcal/kg</th>
                    <th className="num">硫分</th>
                    <th>数学可行性</th>
                    <th style={{ width: 80 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((r) => (
                    <tr key={r.id}>
                      <td className="mono text-sm nowrap">{shortDate(r.date)}</td>
                      <td>
                        <div className="row gap-4 wrap">
                          {r.ratio_items.slice(0, 3).map((it) => (
                            <span key={it.coal_name} className="tag" style={{ maxWidth: 160 }}>
                              <span className="truncate" style={{ maxWidth: 110 }}>{it.coal_name}</span>
                              <span className="text-ember">{fixed(it.ratio_percent, 0)}%</span>
                            </span>
                          ))}
                          {r.ratio_items.length > 3 && <span className="tag">+{r.ratio_items.length - 3}</span>}
                        </div>
                      </td>
                      <td className="num text-ember">{r.total_price === null ? '—' : `¥${fixed(r.total_price, 1)}`}</td>
                      <td className="num">{num(r.total_heat)}</td>
                      <td className="num">{fixed(r.total_sulfur, 2)}</td>
                      <td>{r.constraints_satisfied ? <StatusPill tone="mint">数值可行</StatusPill> : <StatusPill tone="danger">不可行</StatusPill>}</td>
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

      <DetailDrawer id={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}

function DetailDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const detail = useQuery({
    queryKey: qk.optHistoryDetail(id ?? -1),
    queryFn: () => optHistoryDetail(id!),
    enabled: id !== null,
  });
  const [showRaw, setShowRaw] = useState(false);
  const d = detail.data;
  const historicalResult = d && ('result' in d.result_payload ? d.result_payload.result : d.result_payload);
  const provenance = historyProvenance(d?.result_payload);
  const unverified = historicalResult?.data_validation?.status === 'unverified' || d?.request_payload?.calculation_mode === 'screening';

  return (
    <Drawer open={id !== null} onClose={onClose} title="优化历史详情" subtitle={d ? shortDate(d.date) : ''} icon={<Icon name="beaker" size={18} />} wide>
      {detail.isError ? (
        <QueryError message="详情读取失败" onRetry={() => void detail.refetch()} />
      ) : detail.isLoading || !d ? (
        <SkeletonRows rows={8} cols={2} />
      ) : (
        <div className="col gap-18">
          <div className={`verdict ${unverified ? 'verdict--warn' : d.constraints_satisfied ? 'verdict--ok' : 'verdict--bad'}`} style={{ padding: '12px 14px' }}>
            <span className="verdict__icon" style={{ width: 38, height: 38 }}>
              <Icon name={unverified ? 'alert' : d.constraints_satisfied ? 'checkCircle' : 'xCircle'} size={20} />
            </span>
            <div>
              <div className="fw-600 text-sm">{dataValidationLabel(historicalResult?.data_validation, d.request_payload?.calculation_mode)}</div>
              <div className="text-xs text-mute">{d.constraints_satisfied ? '数值约束满足' : '存在数值约束冲突'}；{unverified ? '仅用于筛选，不可直接用于生产。' : '不代表现场工艺验证。'}</div>
              {(historicalResult?.data_validation?.warnings ?? []).map((warning, index) => <div className="text-xs text-mute" key={index}>{warning}</div>)}
              <div className="text-xs text-mute">目标 {historicalResult?.optimization_target ?? '多目标Pareto最优'}</div>
            </div>
          </div>

          {d.optimal_ratios.length > 0 && (
            <div>
              <div className="eyebrow mb-8">推荐配比</div>
              <RatioDonut names={d.coal_names} ratios={d.optimal_ratios} />
              <div className="col gap-6 mt-8">
                {d.ratio_items.map((it) => (
                  <div key={it.coal_name} className="row between text-sm">
                    <span className="truncate" style={{ maxWidth: 260 }}>{it.coal_name}</span>
                    <span className="mono fw-500">{fixed(it.ratio_percent, 1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="eyebrow mb-8">关键指标</div>
            {[
              ['吨煤成本', d.total_price === null ? '—' : `${fixed(d.total_price, 1)} ${provenance.price === '未记录' ? '元/吨（基准未记录）' : provenance.price}`],
              ['综合热值', `${num(d.total_heat)} kcal/kg · ${provenance.heat}`],
              ['灰分', `${fixed(d.total_ash, 2)} %`],
              ['挥发分', `${fixed(d.total_volatile, 2)} %`],
              ['固定碳', `${fixed(d.total_fixed_carbon, 2)} %`],
              ['硫分', `${fixed(d.total_sulfur, 3)} %`],
              ['迭代次数', num(d.iterations)],
              ['计算耗时', `${fixed(d.time_taken, 2)} s`],
              ['质量偏离分', fixed(d.fitness_value, 4)],
            ].map(([k, v]) => (
              <div key={k} className="kv">
                <span className="kv__k">{k}</span>
                <span className="kv__v">{v}</span>
              </div>
            ))}
          </div>

          <div>
            <div className="eyebrow mb-8">本次保存的计算口径</div>
            {provenance.metadata.map(([key, value]) => (
              <div key={key} className="kv"><span className="kv__k">{key}</span><span className="kv__v">{value}</span></div>
            ))}
          </div>

          <div>
            <div className="eyebrow mb-8">化验原值与计算采用值</div>
            {provenance.assays.length === 0 ? (
              <p className="text-sm text-mute">原始化验及采用值快照未记录；不以当前资料或默认设置补写旧历史。</p>
            ) : provenance.assays.map((assay) => (
              <details key={assay.id} className="mb-12">
                <summary className="fw-600 text-sm">{assay.label} · 化验修订 #{assay.id}</summary>
                <p className="text-xs text-mute">报告编号：{assay.report} · 采样时间：{assay.sampledAt}</p>
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead><tr><th>指标</th><th>原始值 / 定义</th><th>计算采用值 / 定义</th><th>来源</th></tr></thead>
                    <tbody>{assay.rows.map((row) => (
                      <tr key={row.field}>
                        <td>{row.label}</td>
                        <td><div className="mono">{row.rawValue}</div><div className="text-xs text-mute">{row.rawDefinition}</div></td>
                        <td><div className="mono">{row.adoptedValue}</div><div className="text-xs text-mute">{row.adoptedDefinition}</div></td>
                        <td className="text-xs">{row.source}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
                <div className="text-xs text-mute mt-8">换算记录</div>
                {assay.trace.length ? <ul className="text-xs">{assay.trace.map((line, index) => <li key={index}>{line}</li>)}</ul> : <p className="text-xs text-mute">未记录</p>}
              </details>
            ))}
          </div>

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
