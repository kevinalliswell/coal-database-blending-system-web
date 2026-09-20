let csrfToken = '';
export function setCsrfToken(value: string) { csrfToken = value; }
export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) { super(message); }
}
async function request(url: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes((init.method || 'GET').toUpperCase()) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(url, { ...init, headers, credentials: 'same-origin' });
  if (response.status === 401 && !['/api/auth/login', '/api/auth/setup', '/api/auth/session'].includes(url)) window.dispatchEvent(new Event('cbos-session-expired'));
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.message || `请求失败（${response.status}）`, body);
  }
  return response;
}
export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const body = await (await request(url, init)).json();
  if (body.status === 'error') throw new ApiError(400, body.message || '请求失败', body);
  return body as T;
}
export async function apiData<T>(url: string, init?: RequestInit): Promise<T> { return (await api<{data:T}>(url, init)).data; }
export async function download(url: string, init?: RequestInit) { return (await request(url, init)).blob(); }
