import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { StaticRouter } from 'react-router-dom/server.js';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const cacheDir = await mkdtemp(join(tmpdir(), 'cbos-support-pages-'));
const server = await createServer({ configFile: false, cacheDir, root: fileURLToPath(new URL('../', import.meta.url)), server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true, include: [] }, appType: 'custom' });
after(async () => {
  try { await server.close(); } finally { await rm(cacheDir, { recursive: true, force: true }); }
});
const { default: Help } = await server.ssrLoadModule('/src/pages/Help.tsx');
const { default: About } = await server.ssrLoadModule('/src/pages/About.tsx');
const help = location => renderToStaticMarkup(createElement(StaticRouter, { location }, createElement(Help)));

test('help starts with user instructions, functional chapter anchors and folded technical references', () => {
  const html = help('/help');
  assert.match(html, /新安装的煤库为空/);
  assert.match(html, /本页目录/);
  assert.match(html, /<table>/);
  assert.match(html, /<details class="help-advanced">/);
  assert.doesNotMatch(html, /UPGRADE_2\.0|升级与恢复|flask --app/);
  const anchors = [...html.matchAll(/href="#([^"]+)"/g)].map(match => decodeURIComponent(match[1]));
  assert.ok(anchors.length >= 6);
  for (const id of anchors) assert.ok(html.includes(`id="${id}"`), `missing section for ${id}`);
});

test('technical document selection opens advanced references and unknown documents are explicit', () => {
  const technical = help('/help?document=ASSAY_CONVERSION.md');
  assert.match(technical, /<details class="help-advanced" open="">/);
  assert.match(technical, /aria-current="page"[^>]*>煤质换算说明/);
  const unknown = help('/help?document=UPGRADE_2.0.md');
  assert.match(unknown, /role="alert"[^>]*>本版本离线帮助未收录/);
  assert.doesNotMatch(unknown, /新安装的煤库为空/);
});

test('about renders API-backed version and readable metadata without a changelog', () => {
  const client = new QueryClient();
  client.setQueryData(['system-info'], { version: '2.0.0', build_commit: 'a'.repeat(40), build_time: '2026-09-20T05:00:00Z', mode: 'desktop', storage_mode: 'sqlite' });
  const html = renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(StaticRouter, { location: '/about' }, createElement(About))));
  assert.match(html, /<strong>v2\.0\.0<\/strong>/);
  assert.match(html, /<dt>运行方式<\/dt><dd>Windows 离线桌面版<\/dd>/);
  assert.match(html, /<dt>数据存储<\/dt><dd>SQLite 数据库<\/dd>/);
  assert.match(html, /<code>a{40}<\/code>/);
  assert.doesNotMatch(html, /更新记录|CHANGELOG|build_commit|storage_mode/);
  assert.match(html, /<details class="about-model">/);
  client.clear();
});
