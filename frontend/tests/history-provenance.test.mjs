import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/historyProvenance.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } });
const { historyProvenance } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);

test('completed history uses its saved definitions and retains original/adopted values', () => {
  const result = historyProvenance({ input_snapshot: {
    schema_version: 2, ratio_basis: 'ar', heat_type: 'net_v', formula_version: 'CBOS-assay-2.0',
    settings: { version: 7 }, operator: { username: 'operator' },
    assays: [{ id: 11, label: '煤A / 批次B / 修订1', report_number: 'R-01',
      raw: { ash_content: { value: 10, unit: '%', basis: 'd' } },
      eligibility: { blending: { values: { ash_content: 9.2, fixed_carbon: 69 }, trace: ['干基转收到基'] } },
    }],
  }, result: { data_validation: { ratio_basis: 'd' } } });
  assert.equal(result.basis, '收到基 ar');
  assert.equal(result.heat, '恒容低位 Qnet,v');
  assert.equal(result.price, '元/收到吨');
  assert.deepEqual(result.metadata.find(([key]) => key === '设置版本'), ['设置版本', '7']);
  assert.equal(result.assays[0].rows[0].rawValue, '10');
  assert.equal(result.assays[0].rows[0].adoptedValue, '9.2');
  assert.equal(result.assays[0].rows[1].source, '标准差减派生');
  assert.deepEqual(result.assays[0].trace, ['干基转收到基']);
});

test('legacy missing snapshots never borrow current defaults', () => {
  const result = historyProvenance({ data_validation: { status: 'verified' } });
  assert.equal(result.basis, '未记录');
  assert.equal(result.heat, '未记录');
  assert.equal(result.price, '未记录');
  assert.equal(result.assays.length, 0);
  assert.match(result.units, /卡定义未记录/);
});

test('legacy saved ratio may be displayed while absent heat and actor stay unrecorded', () => {
  const result = historyProvenance({ result: { data_validation: { ratio_basis: 'd' } } });
  assert.equal(result.basis, '干基 d');
  assert.equal(result.price, '元/干吨');
  assert.equal(result.heat, '未记录');
  assert.deepEqual(result.metadata.find(([key]) => key === '操作者'), ['操作者', '未记录']);
});
