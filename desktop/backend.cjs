const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');

function startBackend({ command, args = [], dataDir, token = '', log = () => {}, timeoutMs = 90000 }) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, CBOS_DESKTOP_DATA_DIR: dataDir || '', CBOS_DESKTOP_TOKEN: token,
        PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
    });
    let ready = false;
    let settled = false;
    let stopping = false;
    let stopPromise;
    const lines = createInterface({ input: child.stdout });
    const closePromise = new Promise(done => child.once('close', done));
    const fail = error => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      lines.close();
      child.kill();
      reject(error);
    };
    const timer = setTimeout(() => fail(new Error('计算服务启动超时 (timeout)')), timeoutMs);
    child.stderr.on('data', chunk => log(token ? chunk.toString('utf8').replaceAll(token, '[redacted]') : chunk.toString('utf8')));
    child.stdin.on('error', error => { if (!stopping) log(`backend stdin: ${error.message}`); });
    child.once('error', fail);
    child.once('exit', (code, signal) => {
      if (!ready) fail(new Error(`计算服务提前退出 (${code ?? signal})`));
    });
    lines.on('line', line => {
      if (settled) return;
      let message;
      try { message = JSON.parse(line); } catch { return; }
      if (message.type !== 'ready') return;
      if (!Number.isInteger(message.port) || message.port < 1 || message.port > 65535) {
        fail(new Error('计算服务返回了无效端口 (port)')); return;
      }
      ready = true;
      settled = true;
      clearTimeout(timer);
      resolve({
        child, token, origin: `http://127.0.0.1:${message.port}`,
        get stopping() { return stopping; },
        stop() {
          if (stopPromise) return stopPromise;
          stopping = true;
          stopPromise = (async () => {
            child.stdin.end();
            const killer = setTimeout(() => child.kill(), 5000);
            await closePromise;
            clearTimeout(killer);
            lines.close();
          })();
          return stopPromise;
        },
      });
    });
  });
}
module.exports = { startBackend };
