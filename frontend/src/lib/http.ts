let csrfToken = '';
let sessionGeneration = 0;
export function setCsrfToken(value: string) {
  if (value !== csrfToken) sessionGeneration++;
  csrfToken = value;
}
export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) { super(message); }
}
async function request(url: string, init: RequestInit = {}) {
  const generation = sessionGeneration;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  // Pin reads as well as writes to the identity shown by this browser tab.
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(url, { ...init, headers, credentials: 'same-origin' });
  assertCurrentSession(generation);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    assertCurrentSession(generation);
    const expired = response.status === 401 && !['/api/auth/login', '/api/auth/setup', '/api/auth/session'].includes(url);
    const staleCsrf = response.status === 403 && body.code === 'csrf_failed' &&
      !['/api/auth/login', '/api/auth/setup', '/api/auth/session'].includes(url);
    if (expired || staleCsrf) window.dispatchEvent(new Event('cbos-session-expired'));
    throw new ApiError(response.status, body.message || `请求失败（${response.status}）`, body);
  }
  return { response, generation };
}
function assertCurrentSession(generation: number) {
  if (generation !== sessionGeneration) throw new ApiError(409, '登录会话已改变，请在当前账号下重试', { code: 'session_changed' });
}
export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const { response, generation } = await request(url, init);
  const body = await response.json();
  assertCurrentSession(generation);
  if (body.status === 'error') throw new ApiError(400, body.message || '请求失败', body);
  return body as T;
}
export async function apiData<T>(url: string, init?: RequestInit): Promise<T> { return (await api<{data:T}>(url, init)).data; }
/** One user submission: refresh anonymous CSRF first, then send credentials once. */
export async function authenticate<T>(action: 'login' | 'setup', credentials: { username: string; password: string }): Promise<T> {
  const session = await api<{ csrf_token: string }>('/api/auth/session');
  setCsrfToken(session.csrf_token);
  return api<T>(`/api/auth/${action}`, { method: 'POST', body: JSON.stringify(credentials) });
}
export async function download(url: string, init?: RequestInit) {
  const { response, generation } = await request(url, init);
  const value = await response.blob();
  assertCurrentSession(generation);
  return value;
}
