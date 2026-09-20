import { useSearchParams, Link } from 'react-router-dom';
import manual from '../../../docs/USER_GUIDE.md?raw';
import conversion from '../../../docs/ASSAY_CONVERSION.md?raw';
import upgrade from '../../../docs/UPGRADE_2.0.md?raw';
import api from '../../../docs/API_REFERENCE.md?raw';
import contract from '../../../docs/DATA_BASIS_CONTRACT.md?raw';
import catalog from '../../../docs/CATALOG_IMPORT_API.md?raw';
import { Markdown } from '../components/docs/Markdown';
const docs: Record<string, [string,string]> = {
  'USER_GUIDE.md':['用户手册',manual], 'ASSAY_CONVERSION.md':['换算公式',conversion],
  'UPGRADE_2.0.md':['升级与恢复',upgrade], 'API_REFERENCE.md':['API参考',api],
  'DATA_BASIS_CONTRACT.md':['基准契约',contract], 'CATALOG_IMPORT_API.md':['表格导入',catalog],
};
export default function Help() {
  const [params] = useSearchParams(); const selected = params.get('document') || 'USER_GUIDE.md';
  return <div className="page v2-help"><h1>使用帮助</h1><p className="text-mute">与本版本 docs/ 文档使用同一份内容，可离线阅读。</p><nav className="v2-actions">{Object.entries(docs).map(([key,[title]]) => <Link className="btn" key={key} to={`/help?document=${key}`}>{title}</Link>)}</nav><article className="panel v2-card"><Markdown text={(docs[selected] || docs['USER_GUIDE.md'])[1]} /></article></div>;
}
