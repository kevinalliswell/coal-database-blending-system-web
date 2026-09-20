import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../src/lib/sessionEvents.ts', import.meta.url), 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText;
const { createSessionNotifier } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`);

test('session changes notify peer tabs once without publishing identity or token', () => {
  const peers = new Set(); const sent = [];
  globalThis.BroadcastChannel = class {
    constructor(name) { this.name = name; peers.add(this); }
    postMessage(data) { sent.push(data); for (const peer of peers) if (peer !== this) peer.onmessage?.({ data }); }
    close() { peers.delete(this); }
  };
  let first = 0; let second = 0;
  const a = createSessionNotifier(() => first++); const b = createSessionNotifier(() => second++);
  a.notify();
  assert.equal(first, 0); assert.equal(second, 1);
  assert.equal(typeof sent[0], 'string'); assert.match(sent[0], /^[0-9a-f-]{36}$/);
  b.close(); a.notify(); assert.equal(second, 1); a.close(); assert.equal(peers.size, 0);
});

test('storage events provide a secret-free fallback and listeners are cleaned up', () => {
  globalThis.BroadcastChannel = undefined; globalThis.window = new EventTarget();
  const writes = []; globalThis.localStorage = { setItem: (...args) => writes.push(args) };
  let refreshes = 0; const notifier = createSessionNotifier(() => refreshes++);
  notifier.notify(); assert.match(writes[0][1], /^[0-9a-f-]{36}$/);
  const event = new Event('storage'); Object.assign(event, { key: writes[0][0], newValue: writes[0][1] });
  window.dispatchEvent(event); assert.equal(refreshes, 1);
  notifier.close(); window.dispatchEvent(event); assert.equal(refreshes, 1);
});
