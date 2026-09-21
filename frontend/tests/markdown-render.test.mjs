import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'vite';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const cacheDir = await mkdtemp(join(tmpdir(), 'cbos-markdown-render-'));
const server = await createServer({ configFile: false, cacheDir, root: fileURLToPath(new URL('../', import.meta.url)), server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true, include: [] }, appType: 'custom' });
after(async () => {
  try { await server.close(); } finally { await rm(cacheDir, { recursive: true, force: true }); }
});
const { Markdown } = await server.ssrLoadModule('/src/components/docs/Markdown.tsx');
const render = text => renderToStaticMarkup(createElement(Markdown, { text }));
const document = '# 使用帮助\n\n## 导入数据\n\n第一行说明，\n仍属于同一段。\n\n| 字段 | 说明 |\n| --- | --- |\n| 基准 | **收到基** |\n\n- 下载模板\n- 预览确认\n\n1. 选择文件\n2. 提交数据\n\n```csv\n煤种,批次\n测试煤,001\n```\n';

test('LF, Windows CRLF and legacy CR render identical semantic Markdown', () => {
  const html = render(document);
  assert.equal(render(document.replaceAll('\n', '\r\n')), html);
  assert.equal(render(document.replaceAll('\n', '\r')), html);
  assert.match(html, /<h2[^>]*>使用帮助<\/h2>/);
  assert.match(html, /<h3[^>]*>导入数据<\/h3>/);
  assert.match(html, /<table>/);
  assert.equal((html.match(/<th(?:\s|>)/g) || []).length, 2);
  assert.equal((html.match(/<td(?:\s|>)/g) || []).length, 2);
  assert.match(html, /<strong>收到基<\/strong>/);
  assert.match(html, /<pre><code[^>]*>煤种,批次\n测试煤,001<\/code><\/pre>/);
});

test('paragraphs join soft line breaks and ordered/unordered lists remain separate', () => {
  const html = render(document);
  assert.match(html, /<p>第一行说明，\s仍属于同一段。<\/p>/);
  assert.match(html, /<ul><li>下载模板<\/li><li>预览确认<\/li><\/ul>/);
  assert.match(html, /<ol[^>]*><li>选择文件<\/li><li>提交数据<\/li><\/ol>/);
});

test('raw HTML and unsafe links cannot become executable markup', () => {
  const html = render('<img src=x onerror=alert(1)>\n\n[危险链接](javascript:alert)');
  assert.doesNotMatch(html, /<img|href="javascript:/);
  assert.match(html, /&lt;img/);
});

test('document headings create unique anchors and ignore fenced code', async () => {
  const { getDocumentHeadings } = await server.ssrLoadModule('/src/components/docs/Markdown.tsx');
  const text = '# 手册\r\n\r\n## 导入数据\r\n\r\n```text\r\n## 这不是标题\r\n```\r\n\r\n## 导入数据\r\n';
  const headings = getDocumentHeadings(text);
  assert.deepEqual(headings.map(({ id }) => id), ['手册', '导入数据', '导入数据-2']);
  const html = render(text);
  for (const heading of headings) assert.ok(html.includes(`id="${heading.id}"`));
  assert.doesNotMatch(html, /id="这不是标题"/);
});

test('links preserve in-document and bundled-document fragments', () => {
  const html = render('[本节](#导入数据) [公式](ASSAY_CONVERSION.md#换算)');
  assert.match(html, /href="#导入数据"/);
  assert.match(html, /href="\/help\?document=ASSAY_CONVERSION.md#换算"/);
});
