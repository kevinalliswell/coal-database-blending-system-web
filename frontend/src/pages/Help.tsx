import { useEffect } from 'react';
import { useSearchParams, useLocation, Link } from 'react-router-dom';
import manual from '../../../docs/USER_GUIDE.md?raw';
import conversion from '../../../docs/ASSAY_CONVERSION.md?raw';
import api from '../../../docs/API_REFERENCE.md?raw';
import contract from '../../../docs/DATA_BASIS_CONTRACT.md?raw';
import catalog from '../../../docs/CATALOG_IMPORT_API.md?raw';
import replacement from '../../../docs/REPLACEMENT_V2.md?raw';
import { getDocumentHeadings, Markdown } from '../components/docs/Markdown';
import './support.css';

const docs: Record<string, [string, string]> = {
  'USER_GUIDE.md': ['操作手册', manual],
  'ASSAY_CONVERSION.md': ['煤质换算说明', conversion],
  'REPLACEMENT_V2.md': ['置换比模型说明', replacement],
  'DATA_BASIS_CONTRACT.md': ['数据定义', contract],
  'CATALOG_IMPORT_API.md': ['导入接口', catalog],
  'API_REFERENCE.md': ['API 接口', api],
};

export default function Help() {
  const [params] = useSearchParams();
  const { hash } = useLocation();
  const selected = params.get('document') || 'USER_GUIDE.md';
  const document = Object.prototype.hasOwnProperty.call(docs, selected) ? docs[selected] : undefined;
  const headings = document ? getDocumentHeadings(document[1]).filter(heading => heading.level === 2) : [];
  useEffect(() => {
    if (!hash) return;
    try { window.document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView({ block: 'start' }); }
    catch { /* Invalid fragments do not prevent reading the document. */ }
  }, [selected, hash]);

  return <div className="page support-page help-page">
    <header className="page__head"><div>
      <p className="eyebrow">CBOS · 操作指南</p>
      <h1 className="page__title">使用帮助</h1>
      <p className="page__lead">从录入煤质到查看计算结果，按工作顺序找到所需说明。</p>
    </div><span className="support-badge">可离线阅读</span></header>
    <div className="help-layout">
      <aside className="help-sidebar">
        <nav aria-label="帮助文档">
          <Link className={`help-manual-link${selected === 'USER_GUIDE.md' ? ' is-selected' : ''}`} aria-current={selected === 'USER_GUIDE.md' ? 'page' : undefined} to="/help">操作手册<span>日常使用从这里开始</span></Link>
          <details className="help-advanced" open={selected !== 'USER_GUIDE.md' && Boolean(document)}>
            <summary>高级参考</summary>
            <p>供需要核对公式或进行系统对接时查阅。</p>
            {Object.entries(docs).filter(([key]) => key !== 'USER_GUIDE.md').map(([key, [title]]) => <Link key={key} className={selected === key ? 'is-selected' : undefined} aria-current={selected === key ? 'page' : undefined} to={`/help?document=${key}`}>{title}</Link>)}
          </details>
        </nav>
        {headings.length > 0 && <nav className="help-toc" aria-label="本页目录"><h2>本页目录</h2><ol>{headings.map(heading => <li key={heading.id}><a href={`#${encodeURIComponent(heading.id)}`}>{heading.text}</a></li>)}</ol></nav>}
      </aside>
      <article className="panel help-article" aria-label={document?.[0] || '未收录的帮助文档'} key={selected}>
        {document ? <div className="doc-content"><Markdown text={document[1]} /></div> : <div className="help-unavailable"><h2>暂未收录这份文档</h2><p role="alert">本版本离线帮助未收录“{selected}”。</p><Link className="btn btn--primary" to="/help">返回操作手册</Link></div>}
      </article>
    </div>
  </div>;
}
