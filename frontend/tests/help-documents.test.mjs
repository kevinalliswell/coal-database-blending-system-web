import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';

const help = await readFile(new URL('../src/pages/Help.tsx', import.meta.url), 'utf8');
const loaded = [...help.matchAll(/import \w+ from '\.\.\/\.\.\/\.\.\/docs\/([^']+)\?raw'/g)].map(match => match[1]);

test('every local link in offline help resolves to another bundled document', async () => {
  for (const name of loaded) {
    const content = await readFile(new URL(`../../docs/${name}`, import.meta.url), 'utf8');
    for (const [, target] of content.matchAll(/\]\((?:docs\/)?([A-Z0-9_.-]+\.md)\)/g)) {
      assert.ok(loaded.includes(target), `${name} links to ${target}, which is missing from offline help`);
    }
  }
});
