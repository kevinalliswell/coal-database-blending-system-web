import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/mock/seed.ts', import.meta.url), 'utf8');
const javascript = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText;
const {seedCoals} = await import(`data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`);

test('a new demo store also starts without any preloaded coal data', () => {
  assert.deepEqual(seedCoals(), []);
});
