import type {
  ActualRatioRequest,
  ActualRatioResponse,
  Coal,
  CoalDraft,
  CoalListResponse,
  HealthInfo,
  OptimizationHistoryDetail,
  OptimizationHistoryItem,
  OptimizationRequest,
  OptimizationResponse,
  ReplacementHistoryDetail,
  ReplacementHistoryItem,
  TheoryRatioRequest,
  TheoryRatioResponse,
} from './types';
import * as mock from './mock/engine';

/** Mock mode is on by default in dev; set VITE_USE_MOCK=false to hit real Flask API. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.status === 'error') {
    throw new ApiError(res.status, body.message || `请求失败 (${res.status})`);
  }
  return body as T;
}

async function blob(url: string, init?: RequestInit): Promise<Blob> {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: `导出失败 (${res.status})` }));
    throw new ApiError(res.status, body.message || '导出失败');
  }
  return res.blob();
}

/* ---------------- Health ---------------- */
export async function getHealth(): Promise<HealthInfo> {
  if (USE_MOCK) {
    await delay(150);
    return mock.mockHealth();
  }
  return j<HealthInfo>('/health');
}

/* ---------------- Coals ---------------- */
export interface CoalQuery {
  page?: number;
  page_size?: number;
  search?: string;
  type?: string;
}

export async function listCoals(q: CoalQuery = {}): Promise<CoalListResponse> {
  const page = q.page ?? 1;
  const page_size = q.page_size ?? 10;
  const search = q.search ?? '';
  const type = q.type ?? '';
  if (USE_MOCK) {
    await delay(180);
    return mock.mockListCoals({ page, page_size, search, type }) as CoalListResponse;
  }
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(page_size),
    search,
    type,
  });
  return j<CoalListResponse>(`/api/coals?${params}`);
}

export async function getCoal(id: number): Promise<Coal> {
  if (USE_MOCK) {
    const c = mock.mockGetCoal(id);
    if (!c) throw new ApiError(404, '煤种不存在');
    return c;
  }
  const r = await j<{ data: Coal }>(`/api/coals/${id}`);
  return r.data;
}

export async function coalTypes(): Promise<string[]> {
  if (USE_MOCK) return mock.mockCoalTypes();
  const r = await j<{ data: string[] }>('/api/coals/types');
  return r.data;
}

export async function createCoal(d: CoalDraft): Promise<Coal> {
  if (USE_MOCK) {
    await delay(160);
    try {
      return mock.mockCreateCoal(d);
    } catch (e) {
      const err = e as { status?: number; message?: string };
      throw new ApiError(err.status ?? 400, err.message ?? '添加失败');
    }
  }
  const r = await j<{ data: Coal }>('/api/coals', { method: 'POST', body: JSON.stringify(d) });
  return r.data;
}

export async function updateCoal(id: number, d: Partial<CoalDraft>): Promise<Coal> {
  if (USE_MOCK) {
    await delay(160);
    try {
      return mock.mockUpdateCoal(id, d);
    } catch (e) {
      const err = e as { status?: number; message?: string };
      throw new ApiError(err.status ?? 400, err.message ?? '更新失败');
    }
  }
  const r = await j<{ data: Coal }>(`/api/coals/${id}`, { method: 'PUT', body: JSON.stringify(d) });
  return r.data;
}

export async function deleteCoal(id: number): Promise<void> {
  if (USE_MOCK) {
    await delay(120);
    mock.mockDeleteCoal(id);
    return;
  }
  await j(`/api/coals/${id}`, { method: 'DELETE' });
}

export async function batchDeleteCoals(ids: number[]): Promise<number> {
  if (USE_MOCK) {
    await delay(160);
    return mock.mockBatchDelete(ids);
  }
  await j('/api/coals/batch_delete', { method: 'POST', body: JSON.stringify({ coal_ids: ids }) });
  return ids.length;
}

export async function uploadCoals(file: File) {
  if (USE_MOCK) {
    await delay(400);
    return mock.mockUpload(file);
  }
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/coals/upload', { method: 'POST', body: fd });
  const body = await res.json();
  if (!res.ok) throw new ApiError(res.status, body.message || '上传失败');
  return body;
}

export async function exportCoals(coalIds: number[] | null): Promise<Blob> {
  if (USE_MOCK) {
    await delay(200);
    return mock.mockExportCsv(coalIds);
  }
  return blob('/api/coals/export', {
    method: 'POST',
    body: JSON.stringify(coalIds ? { coal_ids: coalIds, export_all: false } : { export_all: true }),
  });
}

export async function downloadTemplate(): Promise<Blob> {
  if (USE_MOCK) return mock.mockTemplateCsv();
  return blob('/api/coals/template');
}

/* ---------------- Optimization ---------------- */
export async function runOptimization(req: OptimizationRequest): Promise<OptimizationResponse> {
  if (USE_MOCK) {
    await delay(1100 + Math.random() * 900);
    try {
      return await mock.mockOptimize(req);
    } catch (e) {
      const err = e as { status?: number; message?: string };
      throw new ApiError(err.status ?? 500, err.message ?? '优化失败');
    }
  }
  return j<OptimizationResponse>('/api/optimization', { method: 'POST', body: JSON.stringify(req) });
}

export async function optHistory(): Promise<OptimizationHistoryItem[]> {
  if (USE_MOCK) {
    await delay(160);
    return mock.mockOptHistory();
  }
  const r = await j<{ data: OptimizationHistoryItem[] }>('/api/optimization/history');
  return r.data;
}

export async function optHistoryDetail(id: number): Promise<OptimizationHistoryDetail> {
  if (USE_MOCK) {
    const d = mock.mockOptHistoryDetail(id);
    if (!d) throw new ApiError(404, '历史记录不存在');
    return d;
  }
  const r = await j<{ data: OptimizationHistoryDetail }>(`/api/optimization/history/${id}`);
  return r.data;
}

export async function exportCurrentReport(payload: OptimizationResponse): Promise<Blob> {
  if (USE_MOCK) {
    await delay(200);
    return new Blob([JSON.stringify(payload.result, null, 2)], { type: 'application/json' });
  }
  return blob('/api/optimization/export/current', { method: 'POST', body: JSON.stringify(payload) });
}

export async function exportHistoryReport(id: number): Promise<Blob> {
  if (USE_MOCK) {
    const d = mock.mockOptHistoryDetail(id);
    return new Blob([JSON.stringify(d?.result_payload ?? {}, null, 2)], { type: 'application/json' });
  }
  return blob(`/api/optimization/export/${id}`);
}

/* ---------------- Replacement ratio ---------------- */
export async function calcTheoryRatio(req: TheoryRatioRequest): Promise<TheoryRatioResponse> {
  if (USE_MOCK) {
    await delay(500);
    return mock.mockTheoryRatio(req);
  }
  return j<TheoryRatioResponse>('/api/calculate_theory_ratio', { method: 'POST', body: JSON.stringify(req) });
}

export async function calcActualRatio(req: ActualRatioRequest): Promise<ActualRatioResponse> {
  if (USE_MOCK) {
    await delay(500);
    try {
      return mock.mockActualRatio(req);
    } catch (e) {
      const err = e as { status?: number; message?: string };
      throw new ApiError(err.status ?? 500, err.message ?? '计算失败');
    }
  }
  return j<ActualRatioResponse>('/api/calculate_actual_ratio', { method: 'POST', body: JSON.stringify(req) });
}

export async function repHistory(): Promise<ReplacementHistoryItem[]> {
  if (USE_MOCK) {
    await delay(160);
    return mock.mockRepHistory();
  }
  const r = await j<{ data: ReplacementHistoryItem[] }>('/api/replacement_ratio/history');
  return r.data;
}

export async function repHistoryDetail(id: number): Promise<ReplacementHistoryDetail> {
  if (USE_MOCK) {
    const d = mock.mockRepHistoryDetail(id);
    if (!d) throw new ApiError(404, '历史记录不存在');
    return d;
  }
  const r = await j<{ data: ReplacementHistoryDetail }>(`/api/replacement_ratio/history/${id}`);
  return r.data;
}

export { ApiError };
