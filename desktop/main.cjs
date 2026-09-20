const { app, BrowserWindow, Menu, dialog, protocol, session, shell } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { randomBytes } = require('node:crypto');
const { startBackend } = require('./backend.cjs');
const { APP_ORIGIN, isAppUrl, isDownloadUrl, proxyRequest } = require('./protocol.cjs');

app.setName('CBOS');
app.setAppUserModelId('com.coalblending.desktop');
const dataDir = path.resolve(process.env.CBOS_DESKTOP_DATA_DIR || path.join(
  process.platform === 'win32' ? (process.env.LOCALAPPDATA || app.getPath('appData')) : app.getPath('appData'), 'CBOS',
));
fs.mkdirSync(dataDir, { recursive: true });
app.setPath('userData', dataDir);
const logDir = path.join(dataDir, 'logs');
fs.mkdirSync(logDir, { recursive: true });
const logPath = path.join(logDir, 'desktop.log');
if (fs.existsSync(logPath) && fs.statSync(logPath).size > 2 * 1024 * 1024) {
  fs.renameSync(logPath, logPath + '.previous');
}
function log(message) {
  fs.appendFileSync(logPath, `${new Date().toISOString()} ${String(message).trim()}\n`);
}

protocol.registerSchemesAsPrivileged([{ scheme: 'cbos', privileges: {
  standard: true, secure: true, supportFetchAPI: true, corsEnabled: true,
} }]);

let window;
let backend;
let starting;
let quitting = false;
let stopped = false;
let exitCode = 0;

async function shutdown() {
  if (quitting) return;
  quitting = true;
  try {
    if (starting) await starting.catch(() => {});
    if (backend) await backend.stop();
    await session.defaultSession.flushStorageData();
  } catch (error) { log(error.stack || error); }
  stopped = true;
  app.exit(exitCode);
}

function fatal(error) {
  log(error.stack || error);
  if (quitting) return;
  exitCode = 1;
  dialog.showErrorBox('CBOS 无法运行', `本地计算服务未能正常运行。请关闭后重新启动。\n\n错误：${error.message}\n\n日志：${logPath}\n数据目录：${dataDir}`);
  void shutdown();
}

function configureSession() {
  const ses = session.defaultSession;
  ses.protocol.handle('cbos', async request => {
    try { return await proxyRequest(request, backend); }
    catch (error) {
      log(`request failed: ${error.message}`);
      return new Response(JSON.stringify({ status: 'error', message: '本地计算服务连接失败，请重启应用。' }), {
        status: 503, headers: { 'content-type': 'application/json; charset=utf-8' },
      });
    }
  });
  // No network dependencies in the offline build, even if a future UI asset
  // accidentally points to an external origin.
  ses.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*', 'ftp://*/*'] },
    (_details, callback) => callback({ cancel: true }));
  const canWriteClipboard = (contents, permission) => contents === window?.webContents &&
    isAppUrl(contents.getURL()) && permission === 'clipboard-sanitized-write';
  ses.setPermissionRequestHandler((contents, permission, callback) => callback(canWriteClipboard(contents, permission)));
  ses.setPermissionCheckHandler((contents, permission) => canWriteClipboard(contents, permission));
  ses.on('will-download', (event, item, contents) => {
    if (contents !== window?.webContents || !isDownloadUrl(item.getURL())) { event.preventDefault(); return; }
    item.setSaveDialogOptions({ title: '保存导出文件', defaultPath: path.join(app.getPath('downloads'), path.basename(item.getFilename())) });
    item.once('done', (_event, state) => {
      if (state === 'interrupted' && !quitting) void dialog.showMessageBox(window, { type: 'error', message: '文件保存失败，请重新导出。' });
    });
  });
}

function configureMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: '文件', submenu: [
      { label: '打开数据文件夹', click: () => shell.openPath(dataDir) },
      { label: '打开日志文件夹', click: () => shell.openPath(logDir) },
      { label: '数据备份说明', click: () => dialog.showMessageBox(window, { type: 'info', title: '备份本地数据',
        message: '退出应用后，复制整个数据文件夹到安全位置（包括 coal_system.db 与 .app-secret）。',
        detail: '数据库包含账号、设置、煤种、批次修订与计算历史。升级会保留本地数据，数据库结构升级前还会自动生成备份。恢复时先退出应用，再用同一份完整备份恢复数据目录。\n\n' + dataDir }) },
      { type: 'separator' }, { label: '退出', role: 'quit' },
    ] },
    { label: '编辑', submenu: [
      { label: '撤销', role: 'undo' }, { label: '重做', role: 'redo' }, { type: 'separator' },
      { label: '剪切', role: 'cut' }, { label: '复制', role: 'copy' }, { label: '粘贴', role: 'paste' },
      { label: '全选', role: 'selectAll' },
    ] },
    { label: '视图', submenu: [
      { label: '重新载入', role: 'reload' }, { type: 'separator' },
      { label: '放大', role: 'zoomIn' }, { label: '缩小', role: 'zoomOut' },
      { label: '实际大小', role: 'resetZoom' }, { label: '全屏', role: 'togglefullscreen' },
    ] },
    { label: '帮助', submenu: [{ label: '关于 CBOS', click: () => dialog.showMessageBox(window, {
      type: 'info', title: '关于 CBOS', message: `CBOS 离线桌面版 ${app.getVersion()}`,
      detail: '煤粉数据库管理及配煤优化控制台\n煤种、混煤优化、置换比和历史报告均在本机处理。\n示例与旧数据保留原值，补齐相关数据与基准后才可计算。',
    }) }] },
  ]));
}

async function launch() {
  log(`starting CBOS ${app.getVersion()} (${process.platform}/${process.arch})`);
  window = new BrowserWindow({ width: 1440, height: 940, minWidth: 1000, minHeight: 700,
    backgroundColor: '#0a0a0c', title: 'CBOS · 离线桌面版', show: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true,
      webSecurity: true, allowRunningInsecureContent: false, spellcheck: false },
  });
  window.once('ready-to-show', () => window.show());
  window.webContents.on('will-navigate', (event, url) => { if (!isAppUrl(url)) event.preventDefault(); });
  window.webContents.on('will-attach-webview', event => event.preventDefault());
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('render-process-gone', (_event, details) => fatal(new Error(`界面进程退出：${details.reason}`)));
  window.on('page-title-updated', event => event.preventDefault());
  window.on('closed', () => { window = null; });
  configureMenu();
  await window.loadFile(path.join(__dirname, 'loading.html'));
  const command = app.isPackaged
    ? path.join(process.resourcesPath, 'backend', process.platform === 'win32' ? 'cbos-backend.exe' : 'cbos-backend')
    : (process.env.CBOS_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'));
  const args = app.isPackaged ? [] : [path.join(__dirname, 'backend_entry.py')];
  starting = startBackend({ command, args, dataDir, token: randomBytes(32).toString('hex'), log });
  backend = await starting;
  backend.child.once('exit', (code, signal) => {
    if (!quitting && !backend.stopping) fatal(new Error(`计算服务意外退出 (${code ?? signal})`));
  });
  if (quitting) return;
  configureSession();
  await window.loadURL(APP_ORIGIN + '/');
  log('ready');
}

if (!app.requestSingleInstanceLock()) {
  app.exit(0);
} else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.show(); window.focus(); } });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', event => { if (!stopped) { event.preventDefault(); void shutdown(); } });
  app.whenReady().then(launch).catch(fatal);
}
