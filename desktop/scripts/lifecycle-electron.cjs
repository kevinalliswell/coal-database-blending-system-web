// Installed/portable Windows lifecycle acceptance. Fixture credentials remain in
// RUNNER_TEMP; only the password-free report and exported workbook are artifacts.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { randomBytes } = require('node:crypto');
const { parseArgs } = require('node:util');

let options, application, page, fixture, output;
const secrets = [];
const rendererErrors = [];
const redact = value => secrets.reduce((text, secret) => text.split(secret).join('[REDACTED]'), String(value));
const windowsPath = value => path.resolve(value).toLowerCase();
const containsPath = (parent, child) => {
  const relative = path.relative(windowsPath(parent), windowsPath(child));
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
};

function configuration() {
  const { values } = parseArgs({ strict: true, allowPositionals: false, options: {
    stage: { type: 'string' }, executable: { type: 'string' }, version: { type: 'string' },
    sha: { type: 'string' }, output: { type: 'string' }, fixture: { type: 'string' },
  } });
  if (values.output) output = path.resolve(values.output);
  assert.equal(process.platform, 'win32', 'Lifecycle acceptance requires Windows');
  assert.equal(process.arch, 'x64', 'Lifecycle acceptance requires Windows x64');
  assert.equal(process.env.RUNNER_ENVIRONMENT, 'github-hosted', 'Lifecycle acceptance requires a disposable GitHub-hosted runner');
  for (const key of ['stage', 'executable', 'version', 'sha', 'output', 'fixture']) {
    assert.ok(values[key], `Missing --${key}`);
  }
  assert.ok(['baseline', 'upgrade', 'zip'].includes(values.stage), 'Unknown lifecycle stage');
  assert.match(values.sha, /^[0-9a-f]{40}$/i, '--sha must be a full commit SHA');
  assert.match(values.version, /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/, 'Invalid expected version');
  assert.ok(process.env.LOCALAPPDATA && process.env.SYSTEMROOT && process.env.RUNNER_TEMP, 'Windows runner directories are required');
  const executable = fs.realpathSync(path.resolve(values.executable));
  assert.ok(fs.statSync(executable).isFile() && /\.exe$/i.test(executable), 'Packaged executable must be an existing .exe');
  const fixturePath = path.resolve(values.fixture);
  // Resolve existing parents so a junction cannot put the credentials in artifacts.
  const fixtureParent = fs.realpathSync(path.dirname(fixturePath));
  const runnerTemp = fs.realpathSync(process.env.RUNNER_TEMP);
  assert.ok(containsPath(runnerTemp, fixtureParent), 'Fixture must remain under RUNNER_TEMP');
  if (fs.existsSync(fixturePath)) assert.equal(fs.lstatSync(fixturePath).isSymbolicLink(), false, 'Fixture must not be a symlink');
  fs.mkdirSync(output, { recursive: true });
  const realOutput = fs.realpathSync(output);
  assert.ok(!containsPath(realOutput, path.join(fixtureParent, path.basename(fixturePath))), 'Fixture must not be inside the uploaded output directory');
  const dataDir = path.resolve(process.env.LOCALAPPDATA, 'CBOS');
  assert.ok(!containsPath(dataDir, realOutput) && !containsPath(realOutput, dataDir), 'Acceptance output must be separate from application data');
  assert.ok(!containsPath(dataDir, fixturePath), 'Fixture must be separate from application data');
  return { ...values, executable, fixture: path.join(fixtureParent, path.basename(fixturePath)), dataDir };
}

function childEnvironment() {
  const env = { ...process.env };
  const remove = new Set(['PATH', 'CBOS_DESKTOP_DATA_DIR', 'CBOS_BUILD_SHA', 'CBOS_BUILD_TIME', 'ELECTRON_RUN_AS_NODE']);
  for (const key of Object.keys(env)) if (remove.has(key.toUpperCase())) delete env[key];
  env.PATH = path.join(process.env.SYSTEMROOT, 'System32');
  return env;
}

async function api(url, body, method = body === undefined ? 'GET' : 'POST') {
  assert.ok(url.startsWith('/api/'), 'Only same-origin application APIs are permitted');
  assert.ok(options.stage === 'baseline' || method === 'GET', 'Upgrade and ZIP stages must not write business data');
  return page.evaluate(async ({ url, body, method }) => {
    const sessionResponse = await fetch('/api/auth/session');
    if (!sessionResponse.ok) throw new Error(`Session read failed (${sessionResponse.status})`);
    const session = await sessionResponse.json();
    const response = await fetch(url, { method, headers: {
      'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token,
    }, body: body === undefined ? undefined : JSON.stringify(body) });
    const result = await response.json();
    // Do not echo request data or server bodies: they could contain credentials.
    if (!response.ok || result.status === 'error') throw new Error(`API ${method} ${url} failed (${response.status})`);
    return result;
  }, { url, body, method });
}

async function launch(setup) {
  const { _electron: electron } = require('playwright');
  application = await electron.launch({ executablePath: options.executable, args: [], env: childEnvironment(), timeout: 120000 });
  const identity = await application.evaluate(({ app }) => ({
    packaged: app.isPackaged, version: app.getVersion(), executable: app.getPath('exe'),
    userData: app.getPath('userData'), platform: process.platform, arch: process.arch,
  }));
  assert.equal(identity.packaged, true, 'Must launch the packaged application');
  assert.equal(identity.platform, 'win32');
  assert.equal(identity.arch, 'x64');
  assert.equal(identity.version, options.version, 'Electron version mismatch');
  assert.equal(windowsPath(fs.realpathSync(identity.executable)), windowsPath(options.executable), 'Unexpected running executable');
  assert.equal(windowsPath(identity.userData), windowsPath(options.dataDir), 'Application must use default LOCALAPPDATA/CBOS');
  page = await application.firstWindow({ timeout: 120000 });
  page.setDefaultTimeout(45000);
  page.on('pageerror', error => rendererErrors.push(redact(error.message)));
  page.on('console', message => { if (message.type() === 'error') rendererErrors.push(redact(message.text())); });
  await page.waitForURL('cbos://app/', { timeout: 120000 });
  const session = await api('/api/auth/session');
  assert.equal(session.setup_required, setup, setup ? 'Baseline must create the first admin' : 'Upgrade/restart must retain the existing administrator');
  assert.equal(session.user, null, 'A new application process must require login');
  await page.getByRole('heading', { name: setup ? '创建首个管理员' : '登录 CBOS', exact: true }).waitFor();
  await page.getByLabel('账号', { exact: true }).fill(fixture.credentials.username);
  await page.getByLabel('密码', { exact: true }).fill(fixture.credentials.password);
  if (setup) await page.getByLabel('确认密码', { exact: true }).fill(fixture.credentials.password);
  await page.getByRole('button', { name: setup ? '创建并登录' : '登录', exact: true }).click();
  // Compatible with both v2.0.0 "服务在线 · sqlite" and later simplified copy.
  await page.getByText(/^服务在线(?: · sqlite)?$/, { exact: true }).waitFor();
  const loggedIn = await api('/api/auth/session');
  assert.equal(loggedIn.user.username, fixture.credentials.username);
  assert.equal(loggedIn.user.role, 'admin');
  assert.equal(loggedIn.user.active, true);
  const build = (await api('/api/system/info')).data;
  assert.equal(build.version, options.version, 'Bundled backend version mismatch');
  assert.equal(build.build_commit, options.sha, 'Bundled backend commit mismatch');
  assert.equal(build.mode, 'desktop');
  assert.equal(build.storage_mode, 'sqlite');
  assert.equal(await page.evaluate(() => typeof window.require), 'undefined');
  return build;
}

async function closeApplication() {
  if (!application) return;
  const current = application;
  const child = current.process();
  await current.close();
  application = null;
  page = null;
  assert.equal(child.exitCode, 0, 'Application must exit cleanly before the next lifecycle stage');
}

function rawAssay(index) {
  // Same mixed report bases as tests/test_v2_optimization.py; entirely synthetic.
  return {
    total_moisture: { value: 8 + index, basis: 'ar', unit: '%' },
    ash_content: { value: 10 + index, basis: 'd', unit: '%' },
    volatile_matter: { value: index < 3 ? 9 + index : 32 + index, basis: 'daf', unit: '%' },
    total_sulfur: { value: .5 + .03 * index, basis: 'd', unit: '%' },
    calorific_value: { value: 29 - .4 * index, basis: 'ar', unit: 'MJ/kg', heat_type: 'net_v' },
    price: { value: 950 - 50 * index, basis: 'ar', unit: 'CNY/t' },
  };
}

function assayRecord(assay) {
  // Preserve stored identity and original values, not recalculated eligibility.
  const { eligibility, ...stored } = assay;
  return stored;
}

function catalogRecord(coal) {
  return { ...coal, batches: coal.batches.map(batch => ({
    ...batch, latest_assay: batch.latest_assay ? assayRecord(batch.latest_assay) : null,
  })) };
}

async function captureBusinessData() {
  const catalog = (await api('/api/catalog?page_size=0&include_archived=true')).data.map(catalogRecord);
  const assays = (await api('/api/assays?page_size=0&include_archived=true')).data.map(assayRecord);
  const users = (await api('/api/users')).data;
  const settings = (await api('/api/settings')).data;
  const summaries = (await api('/api/optimization/history')).data;
  const history = [];
  for (const summary of summaries) {
    const detail = (await api(`/api/optimization/history/${summary.id}`)).data;
    // Only response date formatting changed between versions (UTC gained Z).
    // Persisted requests/results, including every internal timestamp, stay exact.
    const { date, ...stored } = detail;
    history.push(stored);
  }
  history.sort((a, b) => a.id - b.id);
  return { catalog, assays, users, settings, history };
}

async function createBaseline() {
  const initial = await captureBusinessData();
  assert.equal(initial.users.length, 1, 'Baseline should contain only its new administrator');
  assert.equal(initial.history.length, 0, 'Baseline must not reuse another acceptance run');
  const viewerPassword = `Readonly-${randomBytes(24).toString('base64url')}`;
  secrets.push(viewerPassword);
  const viewer = (await api('/api/users', { username: 'lifecycleviewer', password: viewerPassword,
    display_name: '生命周期验收只读账号', role: 'viewer' })).data;
  assert.equal(viewer.role, 'viewer');
  const assays = [];
  for (let index = 0; index < 6; index++) {
    const coal = (await api('/api/catalog', { name: `生命周期验收-${index < 3 ? '无烟煤' : '烟煤'}-${index + 1}`,
      type: index < 3 ? '无烟煤' : '烟煤', supplier: '合成验收数据，非生产' })).data;
    const batch = (await api(`/api/catalog/${coal.id}/batches`, { code: 'LIFECYCLE-B1' })).data;
    const assay = (await api(`/api/batches/${batch.id}/assays`, { raw: rawAssay(index), notes: '安装升级验收，非生产' })).data;
    assert.equal(assay.eligibility.blending.eligible, true);
    assays.push(assay);
  }
  const request = { settings_version: initial.settings.version,
    components: assays.map(assay => ({ assay_revision_id: assay.id, min_ratio: 5, max_ratio: 60 })),
    constraints: { heat_min: 5800, heat_max: 7800, volatile_min: 0, fixed_carbon_min: 0 },
    ga_params: { population_size: 24, max_generations: 8, tournament_size: 3, random_seed: 37 } };
  const result = await api('/api/optimization', request);
  assert.equal(result.status, 'success');
  assert.equal(result.history_saved, true);
  assert.equal(result.result.recommended_solution.is_feasible, true);
  assert.equal(result.input_snapshot.schema_version, 2);
  assert.equal(result.input_snapshot.assays.length, 6);
  assert.equal(result.result.data_validation.status, 'verified');
  const original = assays[0];
  const revision = (await api(`/api/batches/${original.batch_id}/assays`, {
    raw: { ...original.raw, price: { value: 1234, basis: 'ar', unit: 'CNY/t' } }, notes: '计算后新增报价修订',
  })).data;
  assert.equal(revision.revision, original.revision + 1);
  await api('/api/settings', { ...initial.settings, organization: 'Windows 生命周期持久化验收组织' }, 'PUT');
  fixture.business = await captureBusinessData();
  assert.equal(fixture.business.history.length, 1);
  assert.equal(fixture.business.assays.find(assay => assay.id === original.id).raw.price.value, 950);
  assert.equal(fixture.business.assays.find(assay => assay.id === revision.id).raw.price.value, 1234);
  const savedRequest = fixture.business.history[0].request_payload;
  // The API fills omitted defaults before persisting the effective request.
  assert.equal(savedRequest.settings_version, request.settings_version);
  assert.deepEqual(savedRequest.components, request.components);
  for (const [key, value] of Object.entries(request.constraints)) assert.equal(savedRequest.constraints[key], value);
  for (const [key, value] of Object.entries(request.ga_params)) assert.equal(savedRequest.ga_params[key], value);
  assert.deepEqual(fixture.business.history[0].result_payload.input_snapshot, result.input_snapshot);
  assert.equal(result.input_snapshot.assays.find(assay => assay.id === original.id).raw.price.value, 950);
  // Preserve every pre-existing v2.0.0 seed as well as the seven new revisions.
  for (const old of initial.assays) assert.deepEqual(fixture.business.assays.find(assay => assay.id === old.id), old);
  for (const old of initial.catalog) assert.deepEqual(fixture.business.catalog.find(coal => coal.id === old.id), old);
  fixture.identities = { administrator_id: fixture.business.users.find(user => user.role === 'admin').id,
    viewer_id: viewer.id, original_assay_ids: assays.map(assay => assay.id), revised_assay_id: revision.id,
    original_price: 950, revised_price: 1234, history_id: fixture.business.history[0].id,
    preexisting_coal_count: initial.catalog.length, preexisting_assay_count: initial.assays.length };
  fs.writeFileSync(options.fixture, JSON.stringify(fixture, null, 2), { mode: 0o600 });
}

async function verifyPreserved() {
  const current = await captureBusinessData();
  assert.deepEqual(current, fixture.business, 'Stored users, original revisions, settings or immutable history changed');
  const session = await api('/api/auth/session');
  assert.equal(session.user.id, fixture.identities.administrator_id);
  assert.deepEqual(session.user, fixture.business.users.find(user => user.id === session.user.id));
  assert.equal(current.users.find(user => user.id === fixture.identities.viewer_id).role, 'viewer');
  assert.equal(current.assays.find(assay => assay.id === fixture.identities.original_assay_ids[0]).raw.price.value, fixture.identities.original_price);
  assert.equal(current.assays.find(assay => assay.id === fixture.identities.revised_assay_id).raw.price.value, fixture.identities.revised_price);
}

async function exportHistory() {
  const filename = path.join(output, 'preserved-history.xlsx');
  await application.evaluate(({ session }, filename) => {
    globalThis.lifecycleDownload = new Promise(resolve => {
      const timer = setTimeout(() => resolve({ state: 'timeout' }), 45000);
      session.defaultSession.once('will-download', (_event, item) => {
        item.setSavePath(filename);
        item.once('done', (_event, state) => { clearTimeout(timer); resolve({ state, filename: item.getFilename() }); });
      });
    });
  }, filename);
  await page.evaluate(async historyId => {
    const session = await (await fetch('/api/auth/session')).json();
    const response = await fetch(`/api/optimization/export/${historyId}`, { headers: { 'X-CSRF-Token': session.csrf_token } });
    if (!response.ok) throw new Error(`History export failed (${response.status})`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url; link.download = '生命周期历史报告.xlsx'; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }, fixture.identities.history_id);
  const saved = await application.evaluate(() => globalThis.lifecycleDownload);
  assert.equal(saved.state, 'completed', 'History workbook download did not complete');
  assert.match(saved.filename, /\.xlsx$/i);
  const contents = fs.readFileSync(filename);
  assert.ok(contents.length > 1000 && contents.subarray(0, 2).toString() === 'PK', 'History export must contain an XLSX workbook');
}

async function main() {
  options = configuration();
  if (options.stage === 'baseline') {
    fixture = { schema_version: 1, complete: false, baseline_version: options.version, baseline_sha: options.sha,
      credentials: { username: 'lifecycleadmin', password: `Lifecycle-${randomBytes(24).toString('base64url')}` } };
    secrets.push(fixture.credentials.password);
    // Refuse to silently overwrite an earlier fixture or repurpose an existing DB.
    fs.writeFileSync(options.fixture, JSON.stringify(fixture, null, 2), { flag: 'wx', mode: 0o600 });
  } else {
    try { fixture = JSON.parse(fs.readFileSync(options.fixture, 'utf8')); }
    catch { throw new Error('Lifecycle fixture could not be read as JSON'); }
    if (typeof fixture.credentials?.password === 'string') secrets.push(fixture.credentials.password);
    assert.equal(fixture.schema_version, 1, 'Unsupported lifecycle fixture');
    assert.equal(fixture.complete, true, 'Baseline fixture was not completed');
    assert.ok(fixture.credentials.password && fixture.business && fixture.identities, 'Incomplete lifecycle fixture');
  }
  const build = await launch(options.stage === 'baseline');
  if (options.stage === 'baseline') await createBaseline();
  await verifyPreserved();
  await exportHistory();
  await closeApplication();
  await launch(false);
  await verifyPreserved();
  assert.deepEqual(rendererErrors, [], 'Renderer errors occurred');
  await closeApplication();
  assert.deepEqual(rendererErrors, [], 'Renderer errors occurred while closing');
  if (options.stage === 'baseline') {
    fixture.complete = true;
    fs.writeFileSync(options.fixture, JSON.stringify(fixture, null, 2), { mode: 0o600 });
  }
  const report = { passed: true, stage: options.stage, version: build.version, build_commit: build.build_commit,
    platform: 'win32', arch: 'x64', packaged: true, login: true, restart_login: true,
    fixture_preserved: true, history_export: true, renderer_errors: [] };
  fs.writeFileSync(path.join(output, 'lifecycle-electron.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
}

main().catch(async error => {
  const message = redact(error.stack || error);
  console.error(message);
  process.exitCode = 1;
  if (output) {
    fs.mkdirSync(output, { recursive: true });
    fs.writeFileSync(path.join(output, 'failure.txt'), message + '\n');
    if (page && !page.isClosed()) {
      // Mask password controls even if a future UI changes their display style.
      await page.screenshot({ path: path.join(output, 'failure.png'), mask: [page.locator('input[type="password"]')] }).catch(() => {});
    }
  }
}).finally(async () => {
  if (application) await application.close().catch(() => {});
});
