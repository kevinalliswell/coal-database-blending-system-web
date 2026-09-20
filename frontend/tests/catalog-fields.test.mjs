import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../src/components/catalog/fields.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { rawFromDraft, draftFromRaw } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
test('partial input preserves zero and never turns blanks into zero', () => {
  assert.deepEqual(rawFromDraft({ ash_content: { value: '0', unit: '%', basis: 'unknown' }, price: { value: '', unit: 'CNY/t', basis: 'ar' } }),
    { ash_content: { value: 0, unit: '%', basis: 'unknown' } });
});
test('raw editor copies heat and hydrogen definitions without inventing them', () => {
  const raw = { calorific_value: { value: 24.3, unit: 'MJ/kg', basis: 'ar', heat_type: 'net_p' }, hydrogen_content: { value: 4.2, unit: '%', basis: 'ad', hydrogen_includes_moisture: false } };
  assert.deepEqual(rawFromDraft(draftFromRaw(raw)), raw);
});
test('invalid numeric edits cannot be silently saved as null', () => {
  for (const value of ['NaN', 'Infinity', '-Infinity', 'abc']) {
    assert.throws(() => rawFromDraft({ ash_content: { value, unit: '%', basis: 'd' } }));
  }
});
