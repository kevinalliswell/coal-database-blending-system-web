import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getHealth, optHistory, repHistory } from '../lib/api';
import { qk } from '../lib/query';
import { Icon, type IconName } from '../components/ui/Icon';
import { StatPanel, EmptyState } from '../components/ui/bits';
import { fixed, num, timeAgo } from '../lib/format';

interface Feature {
  to: string;
  icon: IconName;
  eyebrow: string;
  title: string;
  desc: string;
  tone: 'ember' | 'cyan';
}
const FEATURES: Feature[] = [
  {
    to: '/coals',
    icon: 'database',
    eyebrow: 'DATABASE',
    title: '煤种数据库',
    desc: '维护煤种工业分析与元素指标，支持导入导出、批量维护与检索。',
    tone: 'cyan',
  },
  {
    to: '/blending',
    icon: 'beaker',
    eyebrow: 'OPTIMIZE',
    title: '智能混煤优化',
    desc: '选煤 → 定约束 → NSGA-II 求解，得到多目标 Pareto 候选与推荐配比。',
    tone: 'ember',
  },
  {
    to: '/replacement',
    icon: 'scale',
    eyebrow: 'CALCULATE',
    title: '置换比计算',
    desc: '理论置换比与实际生产置换比，支持基础与生产因素修正两种模式。',
    tone: 'cyan',
  },
];

export default function Dashboard() {
  const health = useQuery({ queryKey: qk.health, queryFn: getHealth });
  const opt = useQuery({ queryKey: qk.optHistory, queryFn: optHistory });
  const rep = useQuery({ queryKey: qk.repHistory, queryFn: repHistory });

  const optRuns = opt.data ?? [];
  const repRuns = rep.data ?? [];
  const avgTime =
    optRuns.length > 0
      ? optRuns.reduce((a, b) => a + (b.time_taken ?? 0), 0) / optRuns.length
      : null;

  const activity = [
    ...optRuns.map((o) => ({
      kind: 'blend' as const,
      id: o.id,
      date: o.date,
      title: o.coal_names.slice(0, 3).join(' · ') + (o.coal_names.length > 3 ? ` +${o.coal_names.length - 3}` : ''),
      meta: `¥${fixed(o.total_price, 1)} · ${num(o.total_heat)} kcal`,
      ok: o.constraints_satisfied,
      to: '/history/blending',
    })),
    ...repRuns.map((r) => ({
      kind: 'ratio' as const,
      id: r.id,
      date: r.date,
      title: r.calculation_type === 'theory' ? '理论置换比' : '实际置换比',
      meta: `置换比 ${fixed(r.ratio_value, 4)} · ${r.calculation_mode}`,
      ok: true,
      to: '/history/replacement',
    })),
  ]
    .sort((a, b) => (a.date < b.date ? 1 : -1))
    .slice(0, 7);

  return (
    <div className="page">
      {/* hero */}
      <section className="panel panel--forge" style={{ overflow: 'hidden', marginBottom: 22 }}>
        <div style={{ padding: '30px 32px', position: 'relative' }}>
          <div className="eyebrow mb-8">煤粉数据库管理及配煤优化控制台 · PCI CONSOLE</div>
          <h1 className="page__title" style={{ fontSize: 34, maxWidth: 620 }}>
            从一份煤种数据出发，<span className="text-ember">配出最优喷吹煤</span>
          </h1>
          <p className="page__lead" style={{ maxWidth: 560 }}>
            统一维护煤种指标、运行多目标混煤优化、计算高炉置换比，并回看每一次决策的完整依据。
          </p>
          <div className="row gap-10 wrap mt-16">
            <Link to="/blending" className="btn btn--primary btn--lg">
              <Icon name="play" size={16} fill /> 开始智能混煤
            </Link>
            <Link to="/coals" className="btn btn--ghost btn--lg">
              <Icon name="database" size={16} /> 管理煤种数据
            </Link>
          </div>
        </div>
      </section>

      {/* readouts */}
      <section className="grid grid--stats mb-20">
        <StatPanel label="煤种总数" value={num(health.data?.coal_count)} icon="database" tone="cyan" hint="来自数据库煤种表" />
        <StatPanel label="混煤优化历史" value={num(optRuns.length)} icon="beaker" tone="ember" hint="已持久化推荐方案" />
        <StatPanel label="置换比历史" value={num(repRuns.length)} icon="scale" tone="cyan" hint="理论与实际计算记录" />
        <StatPanel
          label="平均求解耗时"
          value={avgTime === null ? '—' : fixed(avgTime, 2)}
          unit={avgTime === null ? undefined : '秒'}
          icon="gauge"
          tone="ember"
          hint="最近混煤运行统计"
        />
      </section>

      {/* features */}
      <section className="grid grid--3 mb-20">
        {FEATURES.map((f) => (
          <Link key={f.to} to={f.to} className="panel feature-card" style={{ padding: 22, display: 'block' }}>
            <div className="row between items-start mb-16">
              <span
                className="row center"
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 'var(--r)',
                  background: f.tone === 'cyan' ? 'var(--cyan-soft)' : 'var(--ember-soft)',
                  color: f.tone === 'cyan' ? 'var(--cyan-bright)' : 'var(--ember-glow)',
                  border: `1px solid ${f.tone === 'cyan' ? 'var(--cyan-line)' : 'var(--ember-line)'}`,
                }}
              >
                <Icon name={f.icon} size={22} />
              </span>
              <span className="eyebrow">{f.eyebrow}</span>
            </div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 18 }}>{f.title}</div>
            <p className="text-sm text-mute mt-8" style={{ minHeight: 40 }}>
              {f.desc}
            </p>
            <div className="row gap-6 mt-12" style={{ color: f.tone === 'cyan' ? 'var(--cyan-bright)' : 'var(--ember-glow)', fontSize: 13, fontWeight: 500 }}>
              进入 <Icon name="arrowRight" size={15} />
            </div>
          </Link>
        ))}
      </section>

      {/* activity + runtime */}
      <section className="grid" style={{ gridTemplateColumns: 'minmax(0,1fr) 320px' }}>
        <div className="panel">
          <div className="panel__head">
            <div className="panel__title">
              <span className="tico"><Icon name="activity" size={17} /></span> 最近活动
            </div>
            <Link to="/history/blending" className="text-sm text-mute row gap-4">
              全部历史 <Icon name="arrowRight" size={13} />
            </Link>
          </div>
          <div className="panel__body" style={{ paddingTop: 6 }}>
            {opt.isLoading || rep.isLoading ? (
              <div className="col gap-10">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="sk" style={{ height: 44 }} />
                ))}
              </div>
            ) : activity.length === 0 ? (
              <EmptyState icon="activity" title="暂无历史活动" sub="运行一次混煤优化或置换比计算后，这里会显示记录。" />
            ) : (
              <div className="col">
                {activity.map((a) => (
                  <Link
                    key={`${a.kind}-${a.id}`}
                    to={a.to}
                    className="row between activity-row"
                    style={{ padding: '12px 4px', borderBottom: '1px solid var(--line)', gap: 12 }}
                  >
                    <div className="row gap-12" style={{ minWidth: 0 }}>
                      <span
                        className="row center flex-none"
                        style={{
                          width: 34,
                          height: 34,
                          borderRadius: 'var(--r-sm)',
                          background: a.kind === 'blend' ? 'var(--ember-soft)' : 'var(--cyan-soft)',
                          color: a.kind === 'blend' ? 'var(--ember-glow)' : 'var(--cyan-bright)',
                        }}
                      >
                        <Icon name={a.kind === 'blend' ? 'beaker' : 'scale'} size={16} />
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <div className="truncate fw-500">{a.title}</div>
                        <div className="text-xs text-mute mono truncate">{a.meta}</div>
                      </div>
                    </div>
                    <div className="text-xs text-mute nowrap">{timeAgo(a.date)}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel__head">
            <div className="panel__title">
              <span className="tico"><Icon name="info" size={16} /></span> 运行信息
            </div>
          </div>
          <div className="panel__body col gap-14">
            <RuntimeRow label="应用" value={health.data?.app ?? '—'} />
            <RuntimeRow label="存储模式" value={health.data?.storage_mode ?? '—'} />
            <RuntimeRow label="煤种记录" value={num(health.data?.coal_count)} mono />
            <RuntimeRow label="服务状态" value={health.isSuccess ? '在线' : health.isError ? '离线' : '检查中'} tone={health.isSuccess ? 'mint' : undefined} />
            <div className="divider" />
            <Link to="/coals" className="btn btn--ghost btn--block">
              <Icon name="database" size={15} /> 检查煤种数据
            </Link>
            <Link to="/history/replacement" className="btn btn--ghost btn--block">
              <Icon name="history" size={15} /> 查看置换比历史
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function RuntimeRow({ label, value, mono, tone }: { label: string; value: string | number; mono?: boolean; tone?: 'mint' }) {
  return (
    <div className="row between">
      <span className="text-sm text-mute">{label}</span>
      <span className={`fw-500 ${mono ? 'mono' : ''} ${tone === 'mint' ? 'text-mint' : ''}`}>{value}</span>
    </div>
  );
}
