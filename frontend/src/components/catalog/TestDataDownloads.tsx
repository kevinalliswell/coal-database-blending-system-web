import { useState } from 'react';
import { download } from '../../lib/http';
import { downloadBlob } from '../../lib/format';

export function TestDataDownloads() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function save(format: 'xlsx' | 'csv') {
    setBusy(true); setError('');
    try {
      const file = await download(`/api/catalog/test-data?format=${format}`);
      downloadBlob(file, `CBOS六煤测试数据_非生产.${format}`);
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  return <section className="catalog-test-data" aria-label="六煤测试数据下载">
    <div className="catalog-actions"><strong>六煤测试数据</strong>
      <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => void save('xlsx')}>下载测试表 XLSX</button>
      <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => void save('csv')}>下载测试表 CSV</button>
    </div>
    <p className="catalog-note">含 3 种无烟煤和 3 种烟煤，指标与基准完整。仅供练习，非生产数据。下载后选择文件、预览并确认导入，才会写入煤库。</p>
    {error && <p role="alert" className="catalog-error">{error}</p>}
  </section>;
}
