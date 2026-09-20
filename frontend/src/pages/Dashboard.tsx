import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { listAssays, getSettings, basisLabel, heatLabel } from '../lib/v2';
import { useSession, ROLE_LABELS } from '../lib/session';
export default function Dashboard() {
  const assays = useQuery({queryKey: ['assays'], queryFn: listAssays});
  const settings = useQuery({queryKey: ['settings'], queryFn: getSettings});
  const {user} = useSession();
  const latest = [...(assays.data || []).reduce((map, row) => { if ((map.get(row.batch_id)?.revision || 0) < row.revision) map.set(row.batch_id, row); return map; }, new Map<number, NonNullable<typeof assays.data>[number]>()).values()].filter(a => !a.archived);
  const eligible = latest.filter(a => a.eligibility.blending.eligible);
  return <div className="page"><header className="page__head"><div><p className="eyebrow">CBOS · 数据与计算总览</p><h1 className="page__title">煤质与配煤工作台</h1><p className="page__lead">{user.display_name || user.username} · {ROLE_LABELS[user.role]} · {settings.data?.organization || '本部署独立保存账号和数据'}</p></div></header>{assays.isError ? <p role="alert">{assays.error.message}</p> : <div className="v2-grid"><section className="panel v2-card"><h2>在用批次</h2><strong className="readout__value">{assays.isPending ? '…' : latest.length}</strong></section><section className="panel v2-card"><h2>可用于混煤</h2><strong className="readout__value text-mint">{assays.isPending ? '…' : eligible.length}</strong><p>按每批次最新化验修订统计</p></section><section className="panel v2-card"><h2>待补充或待核对</h2><strong className="readout__value text-amber">{assays.isPending ? '…' : latest.length - eligible.length}</strong><p>原始记录仍完整保留</p></section></div>}<section className="panel v2-card"><h2>当前计算口径</h2>{settings.data && <p>{basisLabel(settings.data.ratio_basis)}配比 · {heatLabel(settings.data.heat_type)} · {settings.data.heat_unit} · 元/{settings.data.ratio_basis === 'ar' ? '收到' : '干'}吨</p>}<p>化验报告可按原始单位和基准录入，计算前按各指标所需的水分、灰分和氢数据统一换算。未满足相关条件的记录会说明缺项。</p><div className="v2-actions"><Link className="btn btn--primary" to="/coals">管理煤种与批次</Link><Link className="btn" to="/blending">开始混煤计算</Link><Link className="btn" to="/help">查看录入指南</Link></div></section><section className="panel v2-card"><h2>工作顺序</h2><ol><li>建立煤种与到货批次，按化验报告录入各指标。</li><li>查看“原值 / 计算采用值”和缺项说明；新增修订补齐数据。</li><li>选择批次修订，确认工艺约束和比例边界后求解。</li><li>在历史中查看本次记录与配置快照，导出结果供工艺评估。</li></ol></section></div>;
}
