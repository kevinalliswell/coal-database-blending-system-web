import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiData } from '../lib/http';
import './support.css';

interface SystemInfo { version: string; build_commit: string; build_time: string; mode: string; storage_mode: string }
function displayTime(value?: string) {
  if (!value || value === 'unknown') return '未记录（开发构建）';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false });
}

export default function About() {
  const info = useQuery({ queryKey: ['system-info'], queryFn: () => apiData<SystemInfo>('/api/system/info') });
  const data = info.data;
  return <div className="page support-page about-page">
    <header className="page__head"><div><p className="eyebrow">CBOS · 系统信息</p><h1 className="page__title">关于 CBOS</h1></div></header>
    <section className="panel about-brand" aria-labelledby="about-product">
      <div className="about-brand__identity"><div className="about-mark"><img src="/furnace.svg" alt="" /></div><div><p className="about-wordmark">CBOS</p><h2 id="about-product">煤质数据库与配煤优化系统</h2><p className="about-tagline">管理煤质数据，比较配煤方案，保留计算依据。</p></div></div>
      <div className="about-version"><span>当前版本</span><strong>{data ? `v${data.version}` : info.isPending ? '读取中…' : '暂不可用'}</strong></div>
    </section>
    <section className="panel about-info" aria-labelledby="about-info-title">
      <div className="support-section-head"><h2 id="about-info-title">运行信息</h2><p>联系管理员排查问题时，可提供下方版本与构建信息。</p></div>
      {info.isPending ? <p role="status" className="about-loading">正在读取系统信息…</p> : info.isError ? <div className="about-error"><p role="alert">系统信息读取失败：{info.error.message}</p><button className="btn" onClick={() => void info.refetch()}>重新读取</button></div> : data && <dl className="about-metadata">
        <div><dt>运行方式</dt><dd>{data.mode === 'desktop' ? 'Windows 离线桌面版' : 'Web 网页版'}</dd></div>
        <div><dt>数据存储</dt><dd>{data.storage_mode === 'sqlite' ? 'SQLite 数据库' : data.storage_mode === 'mysql' ? 'MySQL 数据库' : data.storage_mode}</dd></div>
        <div><dt>构建时间（本地时间）</dt><dd>{displayTime(data.build_time)}</dd></div>
        <div className="about-metadata__commit"><dt>构建标识</dt><dd><code>{data.build_commit === 'unknown' ? '未记录（开发构建）' : data.build_commit}</code></dd></div>
      </dl>}
    </section>
    <section className="panel about-purpose" aria-labelledby="about-purpose-title">
      <div className="support-section-head"><h2 id="about-purpose-title">数据与计算</h2><p>从原始化验报告到历史结果，保留每一步的采用值与来源。</p></div>
      <ul className="about-capabilities"><li><strong>煤质记录</strong><span>按煤种、到货批次与化验修订整理原始数据。</span></li><li><strong>配煤与置换比</strong><span>统一计算口径，对比指标、成本与候选方案。</span></li><li><strong>历史追溯</strong><span>回查当时的输入、配比与设置。</span></li></ul>
      <details className="about-model"><summary>计算方法与适用范围</summary><p>混煤计算先检查约束是否可行，再以最低成本可行解为起点，通过 NSGA-II 比较成本、热值和工艺偏离程度不同的候选方案。</p><p>混煤采用线性模型，理论置换比采用干基热量与物料模型。结果用于方案比较，不预测煤种相互作用或实际高炉效果；数值可行仍需结合现场工艺验证。计算输入、模型常量及主动选用的工程估算随结果保存。</p></details>
      <div className="about-footer"><p>网页版与离线桌面版的账号和数据分别保存在各自部署中。</p><Link className="btn" to="/help">查看使用帮助</Link></div>
    </section>
  </div>;
}
