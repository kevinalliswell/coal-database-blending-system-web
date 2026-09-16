// Runs the real desktop window against the real local backend. No network service
// or mocks; a disposable directory contains all test data and exported files.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const desktop = path.resolve(__dirname, '..');
const output = path.resolve(process.env.CBOS_SMOKE_OUTPUT || path.join(desktop, 'smoke-output'));
fs.mkdirSync(output, { recursive: true });
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'CBOS-桌面回归-'));
const errors = [];
let application;
let page;

async function launch() {
  const packaged = process.env.CBOS_ELECTRON_EXECUTABLE;
  const env = { ...process.env, CBOS_DESKTOP_DATA_DIR: dataDir };
  delete env.ELECTRON_RUN_AS_NODE;
  if (packaged && process.platform === 'win32') {
    // process.env is case-insensitive on Windows; its plain-object copy is not.
    const systemRoot = process.env.SYSTEMROOT;
    assert.ok(systemRoot, 'Windows system directory must be present');
    for (const key of Object.keys(env)) if (key.toUpperCase() === 'PATH') delete env[key];
    env.PATH = path.join(systemRoot, 'System32');
  }
  application = await electron.launch({ executablePath: packaged || require('electron'),
    args: packaged ? [] : [desktop], env, timeout: 120000 });
  page = await application.firstWindow({ timeout: 120000 });
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.waitForURL('cbos://app/', { timeout: 120000 });
  await page.getByText('服务在线 · sqlite', { exact: true }).waitFor();
  assert.equal(await page.getByText('演示数据', { exact: true }).count(), 0);
  assert.equal(await page.evaluate(() => typeof window.require), 'undefined');
}
const api = (url) => page.evaluate(async url => {
  const response = await fetch(url); if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}, url);

(async () => {
  await launch();
  const coals = (await api('/api/coals?page_size=0')).data;
  assert.ok(coals.length >= 8);
  await page.screenshot({ path: path.join(output, 'desktop-overview.png') });
  await page.getByRole('button', { name: '切换到亮色主题' }).click();
  const cfg = { calculationMode: 'verified', ratioBasis: 'unknown', selectedIds: [],
    presetId: 'custom', constraints: { heat_min: 6500, heat_max: 7200, ash_min: 0, ash_max: 12,
      volatile_min: 18, volatile_max: 28, fixed_carbon_min: 60, fixed_carbon_max: 76,
      sulfur_min: 0, sulfur_max: 0.8, price_min: 0, price_max: 1000,
      ratio_constraints: Object.fromEntries([1, 2, 5, 6, 7, 8].map(id => [id, { min: 5, max: 50 }])) },
    gaParams: { population_size: 50, max_generations: 60, early_stopping_patience: 20,
      tournament_size: 3, random_seed: 42, mutation_rate: 0.2, crossover_rate: 0.85,
      adaptive_mutation: true, convergence_threshold: 1e-6, pareto_solution_limit: 20 } };
  await page.evaluate(cfg => localStorage.setItem('cbos_blending_v1', JSON.stringify(cfg)), cfg);
  await page.locator('nav a[href="/blending"]').click();
  await page.getByLabel('计算模式').selectOption('screening');
  for (const id of [1, 2, 5, 6, 7, 8]) {
    const name = coals.find(c => c.id === id).name;
    await page.locator('.coal-pick').filter({ has: page.getByText(name, { exact: true }) }).click();
  }
  const responsePromise = page.waitForResponse(r => r.url().endsWith('/api/optimization') && r.request().method() === 'POST', { timeout: 120000 });
  await page.getByRole('button', { name: '开始优化求解' }).click();
  const result = await (await responsePromise).json();
  assert.equal(result.status, 'success');
  assert.equal(result.result.data_validation.status, 'unverified');
  assert.equal(result.result.recommended_solution.is_feasible, true);
  assert.equal(result.history_saved, true);
  await page.getByRole('button', { name: '导出报告' }).waitFor();
  await page.screenshot({ path: path.join(output, 'desktop-blending.png'), fullPage: true });

  // Exercise the browser's real blob download and Electron's save mechanism.
  const exportPath = path.join(output, '混煤报告.xlsx');
  await application.evaluate(({ session }, file) => {
    globalThis.downloadCompleted = new Promise(resolve => {
      session.defaultSession.once('will-download', (_event, item) => {
        item.setSavePath(file);
        item.once('done', (_event, state) => resolve({ state, filename: item.getFilename() }));
      });
    });
  }, exportPath);
  await page.getByRole('button', { name: '导出报告' }).click();
  const saved = await application.evaluate(() => globalThis.downloadCompleted);
  assert.equal(saved.state, 'completed');
  assert.match(saved.filename, /\.xlsx$/);
  await page.getByRole('button', { name: '复制分享' }).click();
  await page.getByText('已复制分享文本', { exact: true }).waitFor();
  const shareText = await application.evaluate(({ clipboard }) => clipboard.readText());
  assert.match(shareText, /未确认|筛选|试算/);
  assert.equal(fs.readFileSync(exportPath).subarray(0, 2).toString(), 'PK');

  // Multipart uploads must survive the custom-protocol proxy unchanged.
  await page.locator('nav a[href="/coals"]').click();
  const templatePath = path.join(output, '煤种导入模板.xlsx');
  await application.evaluate(({ session }, file) => {
    globalThis.templateCompleted = new Promise(resolve => {
      session.defaultSession.once('will-download', (_event, item) => {
        item.setSavePath(file);
        item.once('done', (_event, state) => resolve({ state, filename: item.getFilename() }));
      });
    });
  }, templatePath);
  await page.getByRole('button', { name: '导入模板', exact: true }).click();
  const template = await application.evaluate(() => globalThis.templateCompleted);
  assert.equal(template.state, 'completed');
  assert.equal(template.filename, '煤种导入模板.xlsx');
  assert.equal(fs.readFileSync(templatePath).subarray(0, 2).toString(), 'PK');
  await page.getByRole('button', { name: '批量导入', exact: true }).click();
  const csv = '\uFEFF煤种名称,煤种类型,价格(元/吨),热值(kcal/kg),灰分(%),挥发分(%),固定碳(%),全硫(%)\n桌面回归烟煤,烟煤,750,6900,9,25,64,0.4\n';
  await page.locator('input[type="file"]').setInputFiles({ name: '中文煤种.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
  const importPromise = page.waitForResponse(r => r.url().endsWith('/api/coals/upload'));
  await page.getByRole('button', { name: '开始导入', exact: true }).click();
  assert.equal((await (await importPromise).json()).created_count, 1);
  await page.getByRole('button', { name: '关闭', exact: true }).last().click();

  await page.locator('nav a[href="/replacement"]').click();
  const ratioPromise = page.waitForResponse(r => r.url().endsWith('/api/calculate_theory_ratio'));
  await page.getByRole('button', { name: '开始计算', exact: true }).click();
  const ratio = await (await ratioPromise).json();
  assert.ok(Math.abs(ratio.ratio - 0.7467) < 0.0001);
  const historyCount = (await api('/api/optimization/history')).data.length;
  assert.ok(historyCount > 0);
  await application.close(); application = null;

  // Restart from the same user directory; verify SQLite and stable-origin storage.
  await launch();
  assert.equal(await page.evaluate(() => localStorage.getItem('cbos_theme')), 'light');
  assert.equal(JSON.parse(await page.evaluate(() => localStorage.getItem('cbos_blending_v1'))).selectedIds.length, 6);
  assert.equal((await api('/api/optimization/history')).data.length, historyCount);
  assert.ok((await api('/api/coals?page_size=0')).data.some(c => c.name === '桌面回归烟煤'));
  assert.deepEqual(errors, []);
  await application.close(); application = null;
  const report = { passed: true, platform: process.platform, arch: process.arch,
    packaged: Boolean(process.env.CBOS_ELECTRON_EXECUTABLE), coal_count: coals.length,
    six_coal_result: result.result.recommended_solution, ratio: ratio.ratio,
    checks: ['real SQLite API', 'six-coal UI solve', 'screening labels', 'Excel blob export', 'XLSX template filename', 'clipboard screening text',
      'Chinese CSV multipart import', 'replacement ratio', 'history after restart', 'theme/settings after restart', 'renderer isolation'],
    renderer_errors: errors };
  fs.writeFileSync(path.join(output, 'electron-smoke.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ passed: true, output }));
})().catch(async error => {
  console.error(error);
  if (page && !page.isClosed()) await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
  fs.writeFileSync(path.join(output, 'failure.txt'), error.stack || String(error));
  process.exitCode = 1;
}).finally(async () => {
  if (application) await application.close().catch(() => {});
  const logs = path.join(dataDir, 'logs', 'desktop.log');
  if (fs.existsSync(logs)) fs.copyFileSync(logs, path.join(output, 'desktop.log'));
  fs.rmSync(dataDir, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 });
});
