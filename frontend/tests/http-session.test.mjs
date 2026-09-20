import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

const compile = (source) => `data:text/javascript;base64,${Buffer.from(ts.transpileModule(source,
  { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText).toString('base64')}`;
const httpUrl = compile(await readFile(new URL('../src/lib/http.ts', import.meta.url), 'utf8'));
const { api, setCsrfToken, authenticate } = await import(httpUrl);
const v2 = await readFile(new URL('../src/lib/v2.ts', import.meta.url), 'utf8');
const { listAssays } = await import(compile(v2.replace("'./http'", JSON.stringify(httpUrl))));
globalThis.window = new EventTarget();

test('JSON writes include current CSRF and credentials; multipart keeps its boundary', async () => {
  setCsrfToken('csrf-1'); const requests = [];
  globalThis.fetch = async (_url, init) => { requests.push(init); return Response.json({ status: 'success' }); };
  await api('/api/catalog', { method: 'POST', body: '{}' });
  assert.equal(requests[0].headers.get('X-CSRF-Token'), 'csrf-1');
  assert.equal(requests[0].headers.get('Content-Type'), 'application/json');
  assert.equal(requests[0].credentials, 'same-origin');
  await api('/api/catalog/import/preview', { method: 'POST', body: new FormData() });
  assert.equal(requests[1].headers.get('Content-Type'), null);
  assert.equal(requests[1].headers.get('X-CSRF-Token'), 'csrf-1');
  await api('/api/catalog');
  assert.equal(requests[2].headers.get('X-CSRF-Token'), 'csrf-1');
});

test('assay response must match the version used to label its adopted values', async () => {
  globalThis.fetch = async () => Response.json({ status: 'success', settings_version: 8, data: [{ id: 12 }] });
  assert.deepEqual(await listAssays(8), [{ id: 12 }]);
  await assert.rejects(listAssays(7), error => error.status === 409 && error.details.code === 'settings_changed');
  globalThis.fetch = async () => Response.json({ status: 'success', data: [{ id: 12 }] });
  await assert.rejects(listAssays(8), /设置.*版本/);
});

test('a stale 401 from the previous login must not expire the new session', async () => {
  setCsrfToken('old-session'); let respond; let expired = 0;
  window.addEventListener('cbos-session-expired', () => expired++);
  globalThis.fetch = () => new Promise(resolve => { respond = resolve; });
  const pending = api('/api/catalog');
  setCsrfToken('new-session');
  respond(Response.json({ message: 'previous session expired' }, { status: 401 }));
  await assert.rejects(pending);
  assert.equal(expired, 0);
});

test('a delayed successful response from another login cannot update current UI', async () => {
  setCsrfToken('user-a'); let respond;
  globalThis.fetch = () => new Promise(resolve => { respond = resolve; });
  const pending = api('/api/optimization', { method: 'POST', body: '{}' });
  setCsrfToken('user-b');
  respond(Response.json({ status: 'success', result: 'user-a-result' }));
  await assert.rejects(pending, error => error.details?.code === 'session_changed');
});

test('session changes while a JSON body is still downloading also invalidate it', async () => {
  setCsrfToken('body-user-a'); let finishBody; let started;
  const bodyStarted = new Promise(resolve => { started = resolve; });
  globalThis.fetch = async () => ({ ok: true, status: 200, json: () => {
    started(); return new Promise(resolve => { finishBody = resolve; });
  } });
  const pending = api('/api/catalog');
  await bodyStarted;
  setCsrfToken('body-user-b'); finishBody({ status: 'success', data: ['old-user-data'] });
  await assert.rejects(pending, error => error.details?.code === 'session_changed');
});

test('current-session 401 still requests reauthentication and preserves the status', async () => {
  setCsrfToken('current-session'); let expired = 0;
  window.addEventListener('cbos-session-expired', () => { expired++; setCsrfToken(''); }, { once: true });
  globalThis.fetch = async () => Response.json({ message: '请先登录' }, { status: 401 });
  await assert.rejects(api('/api/catalog'), error => error.status === 401);
  assert.equal(expired, 1);
});

test('CSRF mismatch requests a fresh session and never replays the write', async () => {
  setCsrfToken('stale-cookie-identity'); let expired = 0; let calls = 0;
  window.addEventListener('cbos-session-expired', () => expired++, { once: true });
  globalThis.fetch = async () => { calls++; return Response.json({ message: '会话校验失败', code: 'csrf_failed' }, { status: 403 }); };
  await assert.rejects(api('/api/catalog', { method: 'POST', body: '{}' }), error => error.status === 403);
  assert.equal(expired, 1); assert.equal(calls, 1);
});

test('a rejected login keeps its explicit error without expiring the login form', async () => {
  setCsrfToken('pre-login-token'); let expired = 0; let calls = 0;
  const listener = () => expired++;
  window.addEventListener('cbos-session-expired', listener);
  globalThis.fetch = async () => { calls++; return Response.json({ code: 'csrf_failed' }, { status: 403 }); };
  await assert.rejects(api('/api/auth/login', { method: 'POST', body: '{}' }));
  assert.equal(expired, 0); assert.equal(calls, 1);
  window.removeEventListener('cbos-session-expired', listener);
});

test('one explicit login submission refreshes stale anonymous CSRF before its single POST', async () => {
  setCsrfToken('token-from-first-tab'); const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push({ url, ...init });
    if (url === '/api/auth/session') return Response.json({ csrf_token: 'shared-cookie-token', user: null });
    assert.equal(init.headers.get('X-CSRF-Token'), 'shared-cookie-token');
    return Response.json({ status: 'success', user: { username: 'viewer' } });
  };
  assert.equal((await authenticate('login', { username: 'viewer', password: 'sample-password' })).status, 'success');
  assert.deepEqual(requests.map(r => r.url), ['/api/auth/session', '/api/auth/login']);
  assert.equal(requests.filter(r => r.method === 'POST').length, 1);
});
