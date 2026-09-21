/* Number / value formatting helpers — instrument-grade, locale-aware. */

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`;
}

export function fixed(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return v.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function money(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `¥${fixed(v, digits)}`;
}

/** Relative time for declared instants; unknown-zone history stays absolute. */
export function timeAgo(dateStr: string | null | undefined, now = Date.now()): string {
  if (!dateStr) return '—';
  const t = parseDate(dateStr);
  if (t === null) return dateStr;
  const diff = Math.max(0, now - t) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`;
  return shortDate(dateStr).slice(0, 10);
}

/**
 * Parse only timestamps with an explicit zone, preserving that instant.
 * The API declares SQLite UTC with Z; legacy values without a zone are not
 * safe to convert, since their database session may have used local time.
 */
export function parseDate(s: string): number | null {
  const match = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})$/.exec(s);
  if (!match) return null;
  const iso = `${match[1]}T${match[2]}${match[3]}`;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
}

export function shortDate(s: string | null | undefined): string {
  if (!s) return '—';
  const timestamp = parseDate(s);
  if (timestamp === null) return s;
  const date = new Date(timestamp);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Keep the backend Excel template distinct from the demo CSV template. */
export function coalTemplateFilename(blob: Blob): string {
  return `煤种导入模板.${blob.type.includes('csv') ? 'csv' : 'xlsx'}`;
}

/** trigger a browser download from a Blob */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export function stamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(
    d.getMinutes()
  )}${p(d.getSeconds())}`;
}
