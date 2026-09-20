// Real desktop, local users, SQLite, six-assay solve and browser downloads.
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
let application, page;
async function launch(setup) {
  const packaged = process.env.CBOS_ELECTRON_EXECUTABLE;
  const env = { ...process.env, CBOS_DESKTOP_DATA_DIR: dataDir };
  delete env.ELECTRON_RUN_AS_NODE;
  delete env.CBOS_BUILD_SHA;
  delete env.CBOS_BUILD_TIME;
  if (packaged && process.platform === 'win32') {
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
  await page.getByRole('heading', {name: setup ? '创建首个管理员' : '登录 CBOS', exact: true}).waitFor();
  await page.getByLabel('账号', {exact: true}).fill('desktopadmin');
  await page.getByLabel('密码', {exact: true}).fill('Smoke-password-2026!');
  if (setup) await page.getByLabel('确认密码', {exact: true}).fill('Smoke-password-2026!');
  await page.getByRole('button', {name: setup ? '创建并登录' : '登录', exact: true}).click();
  await page.getByText('服务在线 · sqlite', {exact: true}).waitFor();
  assert.equal(await page.getByText('演示数据', {exact: true}).count(), 0);
  assert.equal(await page.evaluate(() => typeof window.require), 'undefined');
  assert.equal(await page.evaluate(() => document.cookie.includes('cbos_session')), false);
}
const api = (url, body, method) => page.evaluate(async ({url, body, method}) => {
  const session = await (await fetch('/api/auth/session')).json();
  const response = await fetch(url, {method: method || (body ? 'POST' : 'GET'),
    headers: {'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token},
    body: body ? JSON.stringify(body) : undefined});
  const value = await response.json();
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${JSON.stringify(value)}`);
  return value;
}, {url, body, method});
async function saveDownload(button, filename) {
  const file = path.join(output, filename);
  await application.evaluate(({session}, file) => {
    globalThis.downloadCompleted = new Promise(resolve => {
      session.defaultSession.once('will-download', (_event, item) => {
        item.setSavePath(file);
        item.once('done', (_event, state) => resolve({state, filename: item.getFilename()}));
      });
    });
  }, file);
  await button.click();
  const saved = await application.evaluate(() => globalThis.downloadCompleted);
  assert.equal(saved.state, 'completed');
  assert.match(saved.filename, /\.xlsx$/);
  assert.equal(fs.readFileSync(file).subarray(0, 2).toString(), 'PK');
  return saved;
}
(async () => {
  await launch(true);
  const build = (await api('/api/system/info')).data;
  const legacy = (await api('/api/assays')).data;
  assert.equal(legacy.length, 8);
  assert.ok(legacy.every(a => !a.eligibility.blending.eligible));
  const assays = [];
  for (let i = 0; i < 6; i++) {
    const coal = (await api('/api/catalog', {name: `桌面验收${i < 3 ? '无烟煤' : '烟煤'}-${i + 1}`, type: i < 3 ? '无烟煤' : '烟煤'})).data;
    const batch = (await api(`/api/catalog/${coal.id}/batches`, {code: '到货批次-001'})).data;
    const values = {ash_content: 10, volatile_matter: i < 3 ? 10 : 30,
      fixed_carbon: i < 3 ? 78 : 58, total_sulfur: .5, total_moisture: 2,
      price: 900 - i * 30, calorific_value: 7500 - i * 150, carbon_content: 78,
      hydrogen_content: 3, nitrogen_content: 1, sio2_content: 48};
    const raw = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, {value,
      unit: key === 'price' ? 'CNY/t' : key === 'calorific_value' ? 'kcal/kg' : '%',
      basis: key === 'sio2_content' ? 'ash' : 'ar'}]));
    raw.calorific_value.heat_type = 'net_v';
    raw.hydrogen_content.hydrogen_includes_moisture = false;
    const assay = (await api(`/api/batches/${batch.id}/assays`, {raw})).data;
    assert.ok(assay.eligibility.blending.eligible && assay.eligibility.theory.eligible, JSON.stringify(assay));
    assays.push(assay);
  }
  await page.screenshot({path: path.join(output, 'desktop-overview.png')});
  await page.getByRole('button', {name: '切换到亮色主题'}).click();
  await page.locator('nav a[href="/settings"]').click();
  await page.getByLabel('所属组织', {exact: true}).fill('桌面验收组织');
  await page.getByRole('button', {name: '保存设置', exact: true}).click();
  await page.getByText(/已保存 · 版本/).waitFor();
  const settings = (await api('/api/settings')).data;
  const session = await api('/api/auth/session');
  const cfg = {settingsVersion: settings.version, selectedIds: [], presetId: 'custom',
    constraints: {...settings.constraints, ratio_constraints: Object.fromEntries(assays.map(a => [a.id, {min: 5, max: 50}]))},
    gaParams: {...settings.ga_params, population_size: 50, max_generations: 60, early_stopping_patience: 20,
      tournament_size: 3, random_seed: 42}};
  const storageKey = `cbos_blending_v2_user_${session.user.id}`;
  await page.evaluate(({key, cfg}) => localStorage.setItem(key, JSON.stringify(cfg)), {key: storageKey, cfg});
  await page.locator('nav a[href="/blending"]').click();
  const old = page.locator('.coal-pick').filter({has: page.getByText(legacy[0].label, {exact: true})});
  await old.waitFor();
  assert.equal(await old.locator('input').isDisabled(), true);
  for (const assay of assays) await page.locator('.coal-pick').filter({has: page.getByText(assay.label, {exact: true})}).click();
  const solve = page.waitForResponse(r => r.url().endsWith('/api/optimization') && r.request().method() === 'POST', {timeout: 120000});
  await page.getByRole('button', {name: '开始优化求解'}).click();
  const result = await (await solve).json();
  assert.equal(result.status, 'success');
  assert.equal(result.result.data_validation.status, 'verified');
  assert.equal(result.result.recommended_solution.is_feasible, true);
  assert.equal(result.history_saved, true);
  assert.equal(result.input_snapshot.schema_version, 2);
  assert.equal(result.input_snapshot.assays.length, 6);
  await page.getByRole('button', {name: '导出报告'}).waitFor();
  await page.screenshot({path: path.join(output, 'desktop-blending.png'), fullPage: true});
  await saveDownload(page.getByRole('button', {name: '导出报告'}), '混煤报告.xlsx');
  await page.getByRole('button', {name: '复制分享'}).click();
  await page.getByText('已复制分享文本', {exact: true}).waitFor();
  const shareText = await application.evaluate(({clipboard}) => clipboard.readText());
  assert.match(shareText, /仅作配煤评估参考/);

  await page.locator('nav a[href="/coals"]').click();
  await saveDownload(page.getByRole('button', {name: /导入模板/, exact: false}), '批次化验模板.xlsx');
  await page.getByRole('button', {name: '文件 / 粘贴导入', exact: true}).click();
  const csv = '\uFEFF煤种名称,煤种类型,批次编号,ash_content.value,ash_content.unit,ash_content.basis\n桌面回归烟煤,烟煤,批次一,12,%,unknown\n';
  await page.locator('input[type="file"]').setInputFiles({name: '中文煤种.csv', mimeType: 'text/csv', buffer: Buffer.from(csv)});
  await page.getByRole('button', {name: '解析并预览', exact: true}).click();
  await page.getByRole('heading', {name: '1. 核对列映射', exact: true}).waitFor();
  const checks = page.getByLabel('已核对，缺失定义保留未知');
  for (let i = 0; i < await checks.count(); i++) await checks.nth(i).check();
  await page.getByRole('button', {name: '重新预览', exact: true}).click();
  const commitButton = page.getByRole('button', {name: '确认导入 1 份记录', exact: true});
  await commitButton.waitFor();
  const imported = page.waitForResponse(r => r.url().endsWith('/api/catalog/import/commit'));
  await commitButton.click();
  assert.equal((await (await imported).json()).data.created_revisions, 1);

  await page.locator('nav a[href="/replacement"]').click();
  await page.getByLabel('化验修订', {exact: true}).selectOption(String(assays[0].id));
  for (const [label, value] of Object.entries({'煤粉分解热': 921.096, '加热至模型温度的物理热': 1884.06,
    '元素碳 C（干基）': 86, '灰分 A（干基）': 11, 'SiO₂（灰中含量）': 52,
    '煤气利用率 ηCO': 44.44, '炉渣碱度': 1.15, '炉渣热焓': 1800, '鼓风热焓': 1534})) {
    await page.getByLabel(label, {exact: true}).fill(String(value));
  }
  await page.getByLabel('焦炭、炉况和热耗来源说明', {exact: true}).fill('桌面端自动验收输入');
  const theory = page.waitForResponse(r => r.url().endsWith('/api/calculate_theory_ratio'));
  await page.getByRole('button', {name: '开始计算', exact: true}).click();
  const ratio = await (await theory).json();
  assert.ok(Number.isFinite(ratio.ratio) && ratio.ratio > 0, JSON.stringify(ratio));
  assert.equal(ratio.input_snapshot.schema_version, 2);
  const historyCount = (await api('/api/optimization/history')).data.length;
  assert.ok(historyCount > 0);
  await application.close(); application = null;

  await launch(false);
  assert.equal(await page.evaluate(id => localStorage.getItem(`cbos_theme_user_${id}`), session.user.id), 'light');
  assert.equal(JSON.parse(await page.evaluate(key => localStorage.getItem(key), storageKey)).selectedIds.length, 6);
  assert.equal((await api('/api/optimization/history')).data.length, historyCount);
  assert.equal((await api('/api/settings')).data.organization, '桌面验收组织');
  assert.ok((await api('/api/assays')).data.some(a => a.coal_name === '桌面回归烟煤'));
  assert.deepEqual(errors, []);
  await application.close(); application = null;
  fs.writeFileSync(path.join(output, 'electron-smoke.json'), JSON.stringify({passed: true,
    version: build.version, build_commit: build.build_commit,
    platform: process.platform, arch: process.arch, packaged: Boolean(process.env.CBOS_ELECTRON_EXECUTABLE),
    six_coal_result: result.result.recommended_solution, ratio: ratio.ratio,
    checks: ['first admin UI', 'restart login', 'private session', 'legacy unknown disabled', '3 anthracite + 3 bituminous UI solve',
      'immutable input snapshot', 'Excel blob export', 'XLSX template download', 'clipboard text',
      'Chinese CSV multipart preview/commit', 'assay-backed replacement ratio', 'history after restart',
      'theme/draft/settings after restart', 'renderer isolation'], renderer_errors: errors}, null, 2));
  console.log(JSON.stringify({passed: true, output}));
})().catch(async error => {
  console.error(error);
  if (page && !page.isClosed()) await page.screenshot({path: path.join(output, 'failure.png')}).catch(() => {});
  fs.writeFileSync(path.join(output, 'failure.txt'), error.stack || String(error));
  process.exitCode = 1;
}).finally(async () => {
  if (application) await application.close().catch(() => {});
  const logs = path.join(dataDir, 'logs', 'desktop.log');
  if (fs.existsSync(logs)) fs.copyFileSync(logs, path.join(output, 'desktop.log'));
  fs.rmSync(dataDir, {recursive: true, force: true, maxRetries: 10, retryDelay: 300});
});
