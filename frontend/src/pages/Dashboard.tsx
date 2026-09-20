import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { optHistory, repHistory } from '../lib/api';
import { listAssays, getSettings, heatLabel } from '../lib/v2';
import { useSession } from '../lib/session';
import { qk } from '../lib/query';
import { fixed, timeAgo } from '../lib/format';
import { Icon, type IconName } from '../components/ui/Icon';
import { EmptyState, StatPanel, StatusPill } from '../components/ui/bits';
import '../styles/dashboard.css';

const FEATURES: {to: string; icon: IconName; title: string; description: string; tone: string}[] = [
  {to: '/coals', icon: 'database', title: '煤质数据库', description: '录入到货批次与化验报告，查看数据是否满足计算要求。', tone: 'cyan'},
  {to: '/blending', icon: 'beaker', title: '智能混煤', description: '选择煤种批次、设置配比范围，比较成本与质量候选方案。', tone: 'ember'},
  {to: '/replacement', icon: 'scale', title: '置换比计算', description: '结合煤质和现场参数，计算理论或实际生产置换比。', tone: 'cyan'},
];

export default function Dashboard() {
  const {user, can} = useSession();
  const settings = useQuery({queryKey: ['settings'], queryFn: getSettings});
  const assays = useQuery({queryKey: ['assays', settings.data?.version], queryFn: () => listAssays(settings.data!.version), enabled: settings.data !== undefined});
  const opt = useQuery({queryKey: qk.optHistory, queryFn: optHistory});
  const rep = useQuery({queryKey: qk.repHistory, queryFn: repHistory});
  const latest = [...(assays.data || []).reduce((map, row) => {
    if ((map.get(row.batch_id)?.revision || 0) < row.revision) map.set(row.batch_id, row);
    return map;
  }, new Map<number, NonNullable<typeof assays.data>[number]>()).values()].filter(row => !row.archived);
  const eligible = latest.filter(row => row.eligibility.blending.eligible);
  const awaiting = latest.filter(row => !row.eligibility.blending.eligible);
  const empty = assays.isSuccess && latest.length === 0;
  const ready = assays.isSuccess && !settings.isError;
  const error = settings.error || assays.error;
  const activity = [
    ...(opt.data || []).map(item => ({key: `blend-${item.id}`, date: item.date, to: '/history/blending', icon: 'beaker' as IconName,
      title: item.coal_names.slice(0, 2).join(' / ') || '混煤计算',
      detail: `${item.coal_names.length} 项配料 · ${item.constraints_satisfied ? '数值约束满足' : '查看约束检查'}`})),
    ...(rep.data || []).map(item => ({key: `ratio-${item.id}`, date: item.date, to: '/history/replacement', icon: 'scale' as IconName,
      title: item.calculation_type === 'theory' ? '理论置换比' : '实际置换比', detail: `置换比 ${fixed(item.ratio_value, 4)}`})),
  ].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);
  return <div className="page dashboard">
    <header className="dashboard__welcome">
      <div><p className="eyebrow">CBOS · {settings.data?.organization || '煤质与配煤优化'}</p><h1 className="page__title">工作台</h1><p className="page__lead">{user.display_name || user.username}，从煤质数据到配煤方案，在这里开始。</p></div>
      <Link className="btn btn--ghost" to="/help"><Icon name="info" size={16} />使用指南</Link>
    </header>

    <section className="dashboard__stats" aria-label="数据概览">
      <StatPanel label="在用批次" value={ready ? latest.length : '—'} icon="database" tone="cyan" hint="每批次取最新化验" />
      <StatPanel label="可用于混煤" value={ready ? eligible.length : '—'} icon="checkCircle" tone="cyan" hint="数据完整且校验通过" />
      <StatPanel label="待完善数据" value={ready ? awaiting.length : '—'} icon="edit" tone="ember" hint="补充后即可参与计算" />
      <StatPanel label="计算记录" value={opt.isSuccess && rep.isSuccess ? opt.data.length + rep.data.length : '—'} icon="history" tone="ember" hint="混煤与置换比计算" />
    </section>
    {error && <div className="dashboard__notice" role="alert"><Icon name="alert" size={18} /><span>{error.message}</span><button className="btn btn--sm" onClick={() => {void settings.refetch(); void assays.refetch();}}>重新读取</button></div>}

    <section className="panel panel--forge dashboard__start">
      <div className="dashboard__start-copy"><span className="eyebrow">{empty ? '开始使用' : '配煤工作区'}</span>
        <h2>{empty ? '从第一批煤质数据开始' : '把可靠的数据，变成可比较的方案'}</h2>
        <p>{empty ? (can('data_write') ? '新煤库为空。可录入实际化验报告，或从煤质数据库下载测试煤表，导入后体验完整计算流程。' : '当前还没有煤质记录。数据维护员录入批次化验后，即可在这里查看和使用。') : '先确认批次化验，再设置配比和工艺范围。每次计算都会保留使用的数据与结果。'}</p>
        <div className="dashboard__actions"><Link className="btn btn--primary" to={can('calculate') && !empty ? '/blending' : '/coals'}><Icon name={can('calculate') && !empty ? 'play' : 'database'} size={16} />{can('calculate') && !empty ? '开始混煤计算' : can('data_write') ? '录入煤质数据' : '查看煤质数据'}</Link><Link className="btn btn--ghost" to={empty ? '/help' : '/history/blending'}>{empty ? '查看录入示例' : '查看计算记录'}<Icon name="arrowRight" size={15} /></Link></div>
      </div>
      <ol className="dashboard__steps" aria-label="使用步骤"><li><span>01</span><div><strong>准备煤质</strong><p>录入或导入批次化验</p></div></li><li><span>02</span><div><strong>选择与计算</strong><p>确认指标、配比和约束</p></div></li><li><span>03</span><div><strong>比较方案</strong><p>查看结果并导出报告</p></div></li></ol>
    </section>

    <section className="dashboard__features" aria-label="常用功能">{FEATURES.map(feature => <Link className={`panel feature-card dashboard__feature is-${feature.tone}`} key={feature.to} to={feature.to}>
      <span className="dashboard__feature-icon"><Icon name={feature.icon} size={22} /></span><div><h2>{feature.title}</h2><p>{feature.description}</p></div><Icon name="arrowRight" size={18} />
    </Link>)}</section>

    <section className="dashboard__bottom">
      <div className="panel"><div className="panel__head"><h2 className="panel__title"><Icon name="activity" size={17} />最近计算</h2><Link className="dashboard__text-link" to="/history/blending">查看历史<Icon name="arrowRight" size={14} /></Link></div>
        <div className="panel__body">{opt.isError || rep.isError ? <p className="text-danger" role="alert">计算记录读取失败，请到历史页面重试。</p> : opt.isPending || rep.isPending ? <p className="text-mute" role="status">正在读取计算记录…</p> : activity.length === 0 ? <EmptyState icon="history" title="还没有计算记录" sub="完成一次计算后，这里会显示最近结果。" /> : <div className="dashboard__activity">{activity.map(item => <Link key={item.key} to={item.to} className="dashboard__activity-row"><span className="dashboard__activity-icon"><Icon name={item.icon} size={18} /></span><div><strong>{item.title}</strong><p>{item.detail}</p></div><time title={item.date}>{timeAgo(item.date)}</time></Link>)}</div>}</div>
      </div>
      <div className="panel"><div className="panel__head"><h2 className="panel__title"><Icon name="sliders" size={17} />当前计算口径</h2>{can('admin') && <Link className="dashboard__text-link" to="/settings">设置<Icon name="chevronRight" size={14} /></Link>}</div>
        <div className="panel__body dashboard__basis">{settings.data ? <><dl><div><dt>配比质量</dt><dd>{settings.data.ratio_basis === 'ar' ? '收到煤质量' : '干煤质量'}</dd></div><div><dt>目标热值</dt><dd>{heatLabel(settings.data.heat_type)}</dd></div><div><dt>热值单位</dt><dd className="mono">{settings.data.heat_unit}</dd></div><div><dt>成本口径</dt><dd>元 / {settings.data.ratio_basis === 'ar' ? '收到' : '干'}吨</dd></div></dl><p>按化验报告原值录入，计算前由系统统一换算。</p></> : <p role="status">{settings.isError ? '计算口径读取失败' : '正在读取计算口径…'}</p>}
          {ready && <StatusPill tone={awaiting.length ? 'warn' : 'mute'}>{awaiting.length ? `${awaiting.length} 个批次需要完善数据` : empty ? '等待录入第一批数据' : '在用批次数据已就绪'}</StatusPill>}
        </div>
      </div>
    </section>
  </div>;
}
