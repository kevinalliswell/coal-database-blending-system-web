const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { proxyRequest } = require('../protocol.cjs');

test('main process retains one private session per backend, forwards CSRF and revokes logout', async () => {
  const seen = [];
  const server = http.createServer(async (req, res) => {
    seen.push(req.headers);
    if (req.url === '/api/auth/login') res.setHeader('Set-Cookie', ['cbos_session=opaque-secret; HttpOnly; Path=/; SameSite=Lax', 'other=ignored']);
    if (req.url === '/api/auth/logout') res.setHeader('Set-Cookie', 'cbos_session=; Max-Age=0; Path=/');
    res.end('{}');
  }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  try {
    const backend = {origin: `http://127.0.0.1:${server.address().port}`, token: 'transport'};
    const login = await proxyRequest(new Request('cbos://app/api/auth/login', {method: 'POST', headers: {'X-CSRF-Token': 'csrf'}, body: '{}'}), backend);
    await login.text();
    assert.equal(login.headers.has('set-cookie'), false);
    assert.equal(seen[0]['x-csrf-token'], 'csrf');
    assert.equal(seen[0].origin, 'cbos://app');
    await (await proxyRequest(new Request('cbos://app/api/settings', {headers: {Cookie: 'cbos_session=forged'}}), backend)).text();
    assert.equal(seen[1].cookie, 'cbos_session=opaque-secret');
    await (await proxyRequest(new Request('cbos://app/api/settings'), {...backend})).text();
    assert.equal(seen[2].cookie, undefined);
    await (await proxyRequest(new Request('cbos://app/api/auth/logout', {method: 'POST'}), backend)).text();
    await (await proxyRequest(new Request('cbos://app/api/settings'), backend)).text();
    assert.equal(seen[4].cookie, undefined);
    const foreign = new Request('cbos://app/api/auth/setup', {method: 'POST'});
    Object.defineProperty(foreign, 'initiatorOrigin', {value: 'https://evil.example'});
    assert.equal((await proxyRequest(foreign, backend)).status, 403);
    assert.equal(seen.length, 5);
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
});
