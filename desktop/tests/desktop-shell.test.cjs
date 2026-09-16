const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { isAppUrl, isDownloadUrl, proxyRequest } = require('../protocol.cjs');
const { startBackend } = require('../backend.cjs');

test('only the stable app origin and its own blob downloads are accepted', () => {
  assert.equal(isAppUrl('cbos://app/optimization?x=1'), true);
  for (const url of ['https://app/', 'cbos://evil/', 'cbos://app.evil/', 'cbos://user@app/', 'cbos://app:99/', 'file:///secret', 'garbage']) {
    assert.equal(isAppUrl(url), false, url);
  }
  assert.equal(isDownloadUrl('blob:cbos://app/abc'), true);
  assert.equal(isDownloadUrl('blob:https://evil/abc'), false);
});

test('proxy preserves method and body, adds private auth, and rejects foreign hosts', async () => {
  const seen = [];
  const server = http.createServer(async (req, res) => {
    let body = ''; for await (const chunk of req) body += chunk;
    seen.push({ url: req.url, method: req.method, headers: req.headers, body });
    res.writeHead(200, { 'content-type': 'application/json' }); res.end('{"status":"ok"}');
  }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  try {
    const backend = { origin: `http://127.0.0.1:${server.address().port}`, token: 'private-token' };
    const response = await proxyRequest(new Request('cbos://app/api/coals?all=1', {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-cbos-token': 'forged' }, body: '{"name":"中文煤种"}',
    }), backend);
    assert.deepEqual(await response.json(), { status: 'ok' });
    assert.equal(seen[0].url, '/api/coals?all=1');
    assert.equal(seen[0].headers['x-cbos-token'], 'private-token');
    assert.equal(seen[0].body, '{"name":"中文煤种"}');
    assert.equal(response.headers.has('x-cbos-token'), false);
    assert.match(response.headers.get('content-security-policy'), /script-src 'self'/);
    assert.equal((await proxyRequest(new Request('cbos://evil/api'), backend)).status, 403);
    assert.equal(seen.length, 1);
  } finally { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
});

test('backend handshake resolves actual port and EOF stops the child', async () => {
  const backend = await startBackend({ command: process.execPath, args: ['-e',
    `console.log(JSON.stringify({type:'ready',port:43210})); process.stdin.resume(); process.stdin.on('end',()=>process.exit(0));`],
    dataDir: '/tmp/cbos-test', token: 'a'.repeat(64), timeoutMs: 3000,
  });
  assert.equal(backend.origin, 'http://127.0.0.1:43210');
  await backend.stop();
  assert.equal(backend.child.exitCode, 0);
});

test('invalid readiness and early backend exit fail instead of opening a broken UI', async () => {
  await assert.rejects(startBackend({ command: process.execPath, args: ['-e',
    `console.log(JSON.stringify({type:'ready',port:'5000'})); process.stdin.resume();`], timeoutMs: 2000 }), /port|端口/);
  await assert.rejects(startBackend({ command: process.execPath, args: ['-e', 'process.exit(7)'], timeoutMs: 2000 }), /7/);
});

test('startup timeout terminates a child that never becomes ready', async () => {
  await assert.rejects(startBackend({ command: process.execPath, args: ['-e', 'setInterval(()=>{},1000)'], timeoutMs: 100 }), /timeout|超时/);
});
