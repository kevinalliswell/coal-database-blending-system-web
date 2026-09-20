import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/format.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } });
const { coalTemplateFilename } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('real Excel template retains its .xlsx extension for opening and re-importing', () => {
  const template = new Blob(['PK'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  assert.equal(coalTemplateFilename(template), '煤种导入模板.xlsx');
});

test('demo CSV template retains its .csv extension', () => {
  const template = new Blob(['煤种名称'], { type: 'text/csv;charset=utf-8' });
  assert.equal(coalTemplateFilename(template), '煤种导入模板.csv');
});
