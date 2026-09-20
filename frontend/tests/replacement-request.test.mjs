import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/replacementRequest.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } });
const { buildTheoryRequest, buildActualRequest } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const settings = { version: 3 };
const assay = { id: 7, archived: false, eligibility: { theory: { eligible: true, issues: [] } } };
const theory = { coal_decomp: '220', coal_physical: '450', coke_carbon: '86', coke_ash: '11',
  coke_sio2: '52', eta_co: '44.44', slag_basicity: '1.15', slag_enthalpy: '1800', hot_blast: '1534' };
const actual = { initial_coke: '400', final_coke: '370', initial_coal: '150', final_coal: '180',
  mass_basis: 'd', furnace_id: 'BF-1', period_before: '2026-09-01/07', period_after: '2026-09-08/14' };

test('blank fields are missing, not zero or sample defaults', () => {
  assert.throws(() => buildTheoryRequest({}, assay, settings, false), /必填/);
  assert.throws(() => buildActualRequest({ ...actual, initial_coke: '' }, settings, false), /必填/);
  assert.throws(() => buildActualRequest({ ...actual, initial_coke: 'NaN' }, settings, false), /有限/);
});

test('theory uses revision identity and sends only explicit thermal fields', () => {
  const body = buildTheoryRequest(theory, assay, settings, false);
  assert.equal(body.assay_revision_id, 7);
  assert.equal(body.settings_version, 3);
  assert.deepEqual(body.coal_params, { decomposition_heat: 220, physical_heat: 450, heat_unit: 'kJ/kg' });
  assert.equal(body.coke_params.carbon_content, .86);
  assert.equal(body.coke_params.analysis_basis, 'd');
  assert.ok(Math.abs(body.blast_furnace_params.eta_co - .4444) < 1e-12);
  assert.equal(body.blast_furnace_params.hot_blast_enthalpy, 1534);
  assert.equal(body.allow_hot_blast_estimate, false);
});

test('temperature estimate must be deliberate and needs a temperature', () => {
  assert.throws(() => buildTheoryRequest(theory, assay, settings, true), /风温.*必填/);
  const body = buildTheoryRequest({ ...theory, wind_temp: '1180' }, assay, settings, true);
  assert.equal(body.allow_hot_blast_estimate, true);
  assert.equal(body.blast_furnace_params.wind_temperature, 1180);
  assert.equal(body.blast_furnace_params.hot_blast_enthalpy, undefined);
});

test('ineligible assay and missing settings cannot produce a request', () => {
  assert.throws(() => buildTheoryRequest(theory, undefined, settings, false), /化验/);
  assert.throws(() => buildTheoryRequest(theory, { ...assay, eligibility: { theory: { eligible: false, issues: [{ message: '缺少氢' }] } } }, settings, false), /缺少氢/);
  assert.throws(() => buildActualRequest(actual, undefined, false), /设置/);
});

test('uncorrected actual request omits K and explicit correction preserves its source', () => {
  const basic = buildActualRequest(actual, settings, false);
  assert.equal(basic.correction_mode, 'none');
  assert.equal(basic.production_data.adjustment_factor, undefined);
  assert.throws(() => buildActualRequest({ ...actual, adjustment: '3' }, settings, true), /来源/);
  const corrected = buildActualRequest({ ...actual, adjustment: '3', correction_source: '厂内记录A' }, settings, true);
  assert.equal(corrected.correction_mode, 'provided');
  assert.equal(corrected.production_data.adjustment_factor, 3);
  assert.equal(corrected.correction_source, '厂内记录A');
});

test('actual observations require an explicit mass basis and distinct periods', () => {
  assert.throws(() => buildActualRequest({ ...actual, mass_basis: '' }, settings, false), /基准/);
  assert.throws(() => buildActualRequest({ ...actual, period_after: actual.period_before }, settings, false), /期间/);
  assert.throws(() => buildActualRequest({ ...actual, final_coal: actual.initial_coal }, settings, false), /煤比变化/);
});
