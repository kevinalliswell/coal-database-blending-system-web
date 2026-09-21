import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/format.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } });
const moduleUrl = `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`;

function inTimezone(timezone, assertions) {
  execFileSync(process.execPath, ['--input-type=module'], { input: `
    import assert from 'node:assert/strict';
    import { parseDate, shortDate, timeAgo } from '${moduleUrl}';
    ${assertions}
  `, env: { ...process.env, TZ: timezone }, stdio: 'pipe' });
}

for (const timezone of ['Asia/Shanghai', 'UTC']) {
  test(`${timezone}: explicitly UTC history is recent, not eight hours old`, () => {
    inTimezone(timezone, `
      const now = Date.parse('2026-09-20T10:00:30Z');
      assert.equal(timeAgo('2026-09-20T10:00:00Z', now), '刚刚');
      assert.equal(timeAgo('2026-09-20T09:58:00.123456Z', now), '2 分钟前');
      assert.equal(parseDate('2026-09-20 10:00:00Z'), Date.parse('2026-09-20T10:00:00Z'));
    `);
  });

  test(`${timezone}: history timestamps display in the viewer's local date and time`, () => {
    const expected = timezone === 'Asia/Shanghai' ? '2026-09-21 02:03:04' : '2026-09-20 18:03:04';
    inTimezone(timezone, `
      assert.equal(shortDate('2026-09-20T18:03:04Z'), '${expected}');
      assert.equal(shortDate('2026-09-20T18:03:04.987654Z'), '${expected}');
      assert.equal(timeAgo('2026-09-20T18:03:04Z', Date.parse('2026-11-01T00:00:00Z')), '${expected.slice(0, 10)}');
    `);
  });

  test(`${timezone}: explicit Z and offsets retain their actual instant`, () => {
    const expected = timezone === 'Asia/Shanghai' ? '2026-09-20 18:00:00' : '2026-09-20 10:00:00';
    inTimezone(timezone, `
      const instant = Date.parse('2026-09-20T10:00:00Z');
      for (const source of ['2026-09-20T10:00:00Z', '2026-09-20T18:00:00+08:00', '2026-09-20T06:00:00-04:00']) {
        assert.equal(parseDate(source), instant);
        assert.equal(shortDate(source), '${expected}');
        assert.equal(timeAgo(source, instant + 120000), '2 分钟前');
      }
    `);
  });

  test(`${timezone}: unsupported date strings are not guessed and epoch zero is valid`, () => {
    inTimezone(timezone, `
      for (const value of ['2026-09-20 10:00:00', '2026-09-20T10:00:00.123456', '09/20/2026 10:00:00', '2026-09-20', 'not a date']) {
        assert.equal(parseDate(value), null);
        assert.equal(shortDate(value), value);
        assert.equal(timeAgo(value), value);
      }
      assert.equal(shortDate(null), '—');
      assert.equal(timeAgo(undefined), '—');
      assert.equal(parseDate('1970-01-01T00:00:00Z'), 0);
      assert.equal(timeAgo('1970-01-01T00:00:00Z', 30000), '刚刚');
    `);
  });
}
