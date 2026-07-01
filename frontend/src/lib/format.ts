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

/** relative time in Chinese, from an ISO / "YYYY-MM-DD HH:mm:ss" string */
export function timeAgo(dateStr: string | null | undefined, now = Date.now()): string {
  if (!dateStr) return '—';
  const t = parseDate(dateStr);
  if (!t) return dateStr;
  const diff = Math.max(0, now - t) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`;
  return dateStr.slice(0, 10);
}

export function parseDate(s: string): number | null {
  if (!s) return null;
  const iso = s.includes('T') ? s : s.replace(' ', 'T');
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
}

export function shortDate(s: string | null | undefined): string {
  if (!s) return '—';
  return s.replace('T', ' ').slice(0, 19);
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
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
