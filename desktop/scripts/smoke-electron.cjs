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
  await page.getByText('服务在线', {exact: true}).waitFor();
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
  assert.deepEqual((await api('/api/catalog')).data, []);
  assert.deepEqual((await api('/api/assays')).data, []);
  // Packaged Windows check: checkout CRLF must still render semantic Markdown.
  await page.locator('nav a[href="/help"]').click();
  const manual = page.getByRole('article', {name: '操作手册', exact: true});
  await manual.getByRole('heading', {name: '操作手册', level: 2, exact: true}).waitFor();
  await manual.getByRole('heading', {name: '录入煤种与化验', level: 3, exact: true}).waitFor();
  const recordTable = manual.getByRole('table').filter({has: page.getByRole('columnheader', {name: '记录', exact: true})});
  assert.equal(await recordTable.count(), 1);
  assert.equal(await recordTable.getByRole('columnheader').count(), 3);
  await recordTable.getByRole('cell', {name: '化验修订', exact: true}).waitFor();
  assert.ok(await manual.getByRole('list').count() > 0, 'Markdown lists must render as lists');
  assert.equal(await manual.locator('pre').count(), 0, 'The manual must not become one raw code block');
  await page.locator('nav a[href="/about"]').click();
  await page.getByRole('heading', {name: '关于 CBOS', exact: true}).waitFor();
  await page.getByRole('heading', {name: '运行信息', exact: true}).waitFor();
  assert.equal(await page.getByText(/更新记录|更新日志|CHANGELOG/).count(), 0);
  // Exercise the responsive drawer in Chromium even though the native desktop
  // window has a larger minimum width. Initial focus must wait for visibility.
  const desktopViewport = await page.evaluate(() => ({width: innerWidth, height: innerHeight}));
  await page.setViewportSize({width: 390, height: 844});
  await page.getByRole('button', {name: '打开导航菜单', exact: true}).click();
  await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === '关于 CBOS');
  assert.equal(await page.locator('main.main').evaluate(element => element.inert), true);
  await page.getByRole('button', {name: '关闭菜单', exact: true}).focus();
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), 'CBOS 工作台');
  await page.keyboard.press('Shift+Tab');
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), '关闭菜单');
  await page.keyboard.press('Escape');
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), '打开导航菜单');
  assert.equal(await page.locator('main.main').evaluate(element => element.inert), false);
  await page.setViewportSize(desktopViewport);
  assert.equal(await page.locator('nav a[href="/coals"]').innerText(), '煤质数据库');
  await page.locator('nav a[href="/coals"]').click();
  await page.getByText('需要练习数据？下载六煤测试表', {exact: true}).click();
  await saveDownload(page.getByRole('button', {name: '下载测试表 XLSX', exact: true}), '六煤测试数据.xlsx');
  await page.getByRole('button', {name: '文件 / 粘贴导入', exact: true}).click();
  await page.locator('input[type="file"]').setInputFiles(path.join(output, '六煤测试数据.xlsx'));
  await page.getByRole('button', {name: '解析并预览', exact: true}).click();
  const sixImported = page.waitForResponse(r => r.url().endsWith('/api/catalog/import/commit'));
  await page.getByRole('button', {name: '确认导入 6 份记录', exact: true}).click();
  assert.equal((await (await sixImported).json()).data.created_revisions, 6);
  const assays = (await api('/api/assays')).data;
  assert.equal(assays.length, 6);
  assert.deepEqual(assays.map(a => a.coal_type), ['无烟煤', '无烟煤', '无烟煤', '烟煤', '烟煤', '烟煤']);
  assert.ok(assays.every(a => a.eligibility.blending.eligible && a.eligibility.theory.eligible));
  await page.locator('nav a[href="/"]').click();
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
  await page.getByRole('button', {name: '实际置换比', exact: true}).click();
  await page.getByLabel('煤、焦炭耗量的共同质量基准', {exact: true}).selectOption('d');
  for (const [label, value] of Object.entries({'高炉编号': 'SMOKE-BF', '调整前统计期间': 'before',
    '调整后统计期间': 'after', '调整前焦比': 400, '调整后焦比': 370, '调整前煤比': 150, '调整后煤比': 180})) {
    await page.getByLabel(label, {exact: true}).fill(String(value));
  }
  const actualResponse = page.waitForResponse(r => r.url().endsWith('/api/calculate_actual_ratio'));
  await page.getByRole('button', {name: '开始计算', exact: true}).click();
  const actualRatio = await (await actualResponse).json();
  assert.equal(actualRatio.ratio, 1);
  assert.equal(actualRatio.input_snapshot.schema_version, 2);
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
    checks: ['first admin UI', 'restart login', 'private session', 'fresh database empty', 'Help semantic headings/tables/lists', 'About without changelog', 'responsive navigation focus/trap/Escape', 'downloaded six-coal XLSX UI import', '3 anthracite + 3 bituminous UI solve',
      'immutable input snapshot', 'Excel blob export', 'XLSX template download', 'clipboard text',
      'Chinese CSV multipart preview/commit', 'assay-backed replacement ratio', 'actual replacement ratio', 'history after restart',
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
