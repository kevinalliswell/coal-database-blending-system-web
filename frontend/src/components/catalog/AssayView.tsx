import type { Assay, Eligibility } from '../../lib/v2';
import { basisLabel, heatLabel } from '../../lib/v2';
import { metricLabel } from './fields';

export function EligibilityView({ eligibility }: { eligibility: Assay['eligibility'] }) {
  return <div className="catalog-eligibility">{(['blending', 'theory'] as const).map(kind => {
    const result: Eligibility = eligibility[kind];
    return <section className="catalog-qualification" key={kind}>
      <h3>{kind === 'blending' ? '混煤优化' : '理论置换比'} <span className={`catalog-status ${result.eligible ? 'is-ready' : ''}`}>{result.eligible ? '可计算' : '待补充 / 确认'}</span></h3>
      {result.issues.length > 0 && <ul className="catalog-issues">{result.issues.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul>}
      <details><summary>查看换算值与过程（按当前系统设置）</summary>
        {Object.keys(result.values).length > 0 ? <dl className="catalog-values">{Object.entries(result.values).map(([key, value]) => <div key={key}><dt>{metricLabel(key)}</dt><dd>{Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 6 })}{key === 'calorific_value' ? ' kcal/kg' : key === 'price' ? ' CNY/t' : key === 'hgi' ? '' : ' %'}</dd></div>)}</dl> : <p>尚无可用换算值。</p>}
        <ol className="catalog-trace">{result.trace.map((entry, index) => <li key={index}>{typeof entry === 'string' ? entry : JSON.stringify(entry)}</li>)}</ol>
      </details>
    </section>;
  })}</div>;
}

export function AssayView({ assay }: { assay: Assay }) {
  return <div className="catalog-assay-view">
    <div className="catalog-record-meta"><span>修订 R{assay.revision} · #{assay.id}</span><span>报告：{assay.report_number || '未填写'}</span><span>采样：{assay.sampled_at || '未记录'}</span></div>
    {assay.notes && <p className="catalog-note">{assay.notes}</p>}
    <div className="catalog-table-wrap"><table className="catalog-table"><caption>化验报告原值</caption><thead><tr><th>指标</th><th>原值</th><th>单位</th><th>原始基准 / 定义</th></tr></thead><tbody>
      {Object.entries(assay.raw).map(([key, metric]) => <tr key={key}><th scope="row">{metricLabel(key)}</th><td>{metric.value ?? '未录入'}</td><td>{metric.unit === 'unknown' ? '未确认' : metric.unit}</td><td>{basisLabel(metric.basis)}{key === 'calorific_value' && <> · {heatLabel(metric.heat_type || 'unknown')}</>}{key === 'hydrogen_content' && <> · {metric.hydrogen_includes_moisture == null ? '水中氢定义未确认' : metric.hydrogen_includes_moisture ? '包含水中氢' : '不含水中氢'}</>}</td></tr>)}
      {Object.keys(assay.raw).length === 0 && <tr><td colSpan={4}>尚未填写指标，记录已保留。</td></tr>}
    </tbody></table></div>
    <EligibilityView eligibility={assay.eligibility} />
  </div>;
}
