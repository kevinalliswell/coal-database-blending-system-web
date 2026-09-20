import { useQuery } from '@tanstack/react-query';
import { apiData } from '../lib/http';
import { Markdown } from '../components/docs/Markdown';
import changelog from '../../../CHANGELOG.md?raw';
export default function About() {
  const info = useQuery({queryKey: ['system-info'], queryFn: () => apiData<Record<string, unknown>>('/api/system/info')});
  return <div className="page v2-help"><h1>关于 CBOS</h1><section className="panel v2-card"><h2>煤质数据库与配煤优化系统</h2><p>面向钢厂喷煤配料的信息管理与计算工具，提供煤种、到货批次、化验修订、统一基准换算、配煤多目标优化和置换比计算。</p>{info.isPending ? <p>正在读取版本…</p> : info.isError ? <p role="alert">{info.error.message}</p> : <dl>{Object.entries(info.data || {}).map(([key,value]) => <div key={key}><dt>{{version:'系统版本',build_commit:'构建提交',commit:'构建提交',runtime:'运行方式',mode:'运行方式',desktop_mode:'离线桌面模式'}[key] || key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>}<h2>算法范围</h2><p>线性规划预检与最低成本可行解用于建立可行起点；NSGA-II 搜索成本、热值和工艺偏离程度的 Pareto 候选。模型基于已声明质量口径的线性混合，不预测煤种相互作用、燃烧效率或高炉实际运行效果。数据校验通过不等于生产工艺验证通过。</p><p>理论置换比采用干基热量与物料模型；模型常量、输入与显式选用的工程估算随结果保存。</p></section><section className="panel v2-card"><h2>更新记录</h2><Markdown text={changelog} /></section></div>;
}
