import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

// Reuse the project's TypeScript compiler; no browser/test framework dependency.
const source = await readFile(new URL('../src/lib/blendingResult.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } });
const { captureRequest, matchesRequest, buildExportPayload, dataValidationLabel } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
);

const request = () => ({ selected_coal_ids: [1, 6], optimization_target: '多目标Pareto最优',
  constraints: { sulfur_max: 0.8, ratio_constraints: { 1: { min: 5, max: 50 } } },
  ga_params: { population_size: 200 } });

test('editing bounds, coal selection, or GA parameters invalidates a completed request', () => {
  for (const edit of [
    (r) => { r.constraints.sulfur_max = 0.1; },
    (r) => { r.constraints.ratio_constraints[1].max = 20; },
    (r) => { r.selected_coal_ids.push(7); },
    (r) => { r.ga_params.population_size = 900; },
  ]) {
    const current = request();
    const submitted = captureRequest(current);
    assert.equal(matchesRequest(submitted, current), true);
    edit(current);
    assert.equal(matchesRequest(submitted, current), false);
    assert.deepEqual(submitted, request());
  }
});

test('a late completion remains stale after editing the pending request', () => {
  const current = request();
  const inFlight = captureRequest(current);
  current.constraints.sulfur_max = 0.1;
  assert.equal(matchesRequest(inFlight, current), false);
  assert.equal(matchesRequest(null, current), false);
});

test('export uses the selected candidate and the completed run constraints', () => {
  const submitted = request();
  const response = { status: 'success', result: { total_price: 900, optimal_ratios: [0.5, 0.5] },
    constraints: { sulfur_max: 0.8, ash_max: 20 } };
  const selected = { solution_id: 'pareto_2', coal_names: ['A', 'B'], optimal_ratios: [0.2, 0.8],
    total_price: 700, total_heat: 6600, quality_penalty: 0.15, is_feasible: true,
    active_constraints: ['硫上限'], constraint_violations: [] };
  const exported = buildExportPayload(response, submitted, selected);
  assert.equal(exported.result.total_price, 700);
  assert.deepEqual(exported.result.optimal_ratios, [0.2, 0.8]);
  assert.deepEqual(exported.result.blending_ratio, { A: 0.2, B: 0.8 });
  assert.equal(exported.result.fitness_value, 0.15);
  assert.deepEqual(exported.result.active_constraints, ['硫上限']);
  assert.deepEqual(exported.constraints, { sulfur_max: 0.8, ash_max: 20 });
  assert.equal(response.result.total_price, 900);
  assert.equal(buildExportPayload({ ...response, constraints: undefined }, submitted, selected).constraints.sulfur_max, 0.8);
});

test('screening is explicitly unconfirmed even when an older response has no validation metadata', () => {
  assert.match(dataValidationLabel(undefined, 'screening'), /基准未确认.*仅用于筛选/);
  assert.match(dataValidationLabel({ status: 'unverified' }, 'verified'), /仅用于筛选/);
  assert.match(dataValidationLabel({ status: 'verified' }, 'verified'), /基准检查通过/);
  assert.match(dataValidationLabel(undefined, 'verified'), /基准验证未记录/);
});

test('changing calculation mode or ratio basis invalidates a completed run', () => {
  const current = { ...request(), calculation_mode: 'verified', ratio_basis: 'ad' };
  const submitted = captureRequest(current);
  current.calculation_mode = 'screening';
  assert.equal(matchesRequest(submitted, current), false);
  current.calculation_mode = 'verified';
  current.ratio_basis = 'ar';
  assert.equal(matchesRequest(submitted, current), false);
});

test('screening export preserves the restriction when legacy/demo responses omit metadata', () => {
  const submitted = { ...request(), calculation_mode: 'screening', ratio_basis: 'unknown' };
  const selected = { solution_id: 'p1', coal_names: ['A'], optimal_ratios: [1], quality_penalty: 0, is_feasible: true };
  const exported = buildExportPayload({ status: 'success', result: {} }, submitted, selected);
  assert.equal(exported.result.data_validation.status, 'unverified');
  assert.equal(exported.result.data_validation.ratio_basis, 'unknown');
});
