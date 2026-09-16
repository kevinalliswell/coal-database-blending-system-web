# Windows 离线桌面版

桌面版内置 Chromium、Python 和计算依赖，使用与网站相同的 Flask/NSGA-II 服务。煤种、配比计算、置换比、Excel 导入导出及历史记录均在本机处理；运行不需要联网或另装 Python、Node、数据库服务器。

## 安装与使用

目标平台为 Windows 10/11 x64（本项目构建任务在 Windows Server 2022 x64 上验证）。选择 `CBOS-<版本>-windows-x64-setup.exe` 按当前用户安装，或解压 ZIP 后运行目录中的 `CBOS.exe`。ZIP 需要完整解压，不能只复制 EXE；解压版也把数据保存在用户目录。

首次启动自动创建独立本地数据库并载入示例煤种。示例数据基准为 unknown，需要显式选择“未确认数据试算”才能求解。用于正式输入校验前，应根据真实化验记录补齐基准信息，详见 [煤质基准契约](DATA_BASIS_CONTRACT.md)。

桌面菜单“文件 → 打开数据文件夹/日志文件夹”可查看实际路径。默认数据目录为 `%LOCALAPPDATA%\CBOS`：

- `coal_system.db`：煤种和计算历史。
- `backups\`：数据库结构升级前自动生成的 SQLite 备份。
- `logs\desktop.log`：启动和计算服务错误日志。
- 浏览器存储：主题及混煤参数设置。

升级安装不会清除用户数据，卸载也保留数据目录。手工备份或恢复时先退出应用，复制或替换 `coal_system.db`。恢复较新版本的数据库需要使用支持其迁移版本的程序；程序不会盲目升级未知数据库结构。

已有网站数据可以通过煤种 Excel 导出/导入转入桌面。不要把没有迁移版本记录的旧 SQLite 文件直接覆盖桌面数据库；此类数据库先按基准契约文档核实和迁移。

## 开发与构建

Windows x64 构建机器需要 Python 3.11 和 Node.js 22。终端在仓库根目录：

```powershell
python -m pip install -r requirements-dev.txt -r desktop/requirements.txt
npm ci --prefix frontend
npm ci --prefix desktop
npm run build --prefix frontend -- --mode desktop
python desktop/scripts/build-backend.py
npm run dist:win --prefix desktop
```

产物在 `desktop/dist`。构建会从 `app/__version__.py` 同步版本号。PR 构建的文件属于该提交的桌面预览产物；不能据相同版本号推断它等同于现有网站 Release。

桌面 Vite mode 强制使用真实 API，移除 Google 字体链接，采用系统备用字体；普通网站构建保留原行为。PyInstaller 采用目录模式，迁移文件、示例 CSV、前端生产构建随程序打包，不包含开发数据库或 `.env`。

源码开发可先构建前端，再设置 `CBOS_PYTHON` 为 Python 可执行文件并在 `desktop` 执行 `npm start`。`CBOS_DESKTOP_DATA_DIR` 可指定测试专用绝对数据路径。

## 自动验证

[Windows desktop 工作流](../.github/workflows/windows-desktop.yml) 使用 Windows runner 构建并测试。它运行 Python 回归、前端测试、桌面启动和代理测试、冻结 Python 服务冒烟、打包后 Electron 窗口冒烟，并上传安装包、ZIP、SHA256 校验文件、截图和测试报告。

窗口冒烟使用临时中文路径中的数据库：通过界面进行三种无烟煤与三种烟煤混配、导出 Excel、导入中文 CSV、计算置换比，然后重启验证历史和设置保留。它使用真实计算服务，不以模拟结果替代。

```powershell
python -m pytest -q
node --test frontend/tests/*.test.mjs
npm test --prefix desktop
python desktop/scripts/smoke-backend.py --executable desktop/backend-dist/cbos-backend/cbos-backend.exe --output desktop/smoke-output/backend
$env:CBOS_ELECTRON_EXECUTABLE = (Resolve-Path 'desktop/dist/win-unpacked/CBOS.exe').Path
node desktop/scripts/smoke-electron.cjs
```

## 运行边界

窗口使用固定 `cbos://app` 来源，以保留跨重启的本地设置。主进程将请求转发至仅监听 `127.0.0.1` 的随机端口，并携带每次启动随机生成的令牌；令牌不暴露给界面。渲染器启用 sandbox/contextIsolation，关闭 Node 集成，限制外网请求、导航、新窗口和权限。

关闭应用后通过 stdin EOF 结束计算进程；异常情况下主进程还有强制退出兜底。数据库迁移先于窗口就绪执行，旧 schema 升级前使用 SQLite backup API 保存一致备份。

当前构建未配置 Windows 代码签名证书，安装文件没有发布者数字签名。Windows 可能显示未知发布者提示。组织分发前应使用组织证书签名，并在目标 Windows 10/11 环境进行安装验收。

技术依据：[Electron 安全指南](https://www.electronjs.org/docs/latest/tutorial/security)、[自定义协议](https://www.electronjs.org/docs/latest/api/protocol)、[PyInstaller 运行方式](https://pyinstaller.org/en/stable/operating-mode.html)、[electron-builder NSIS](https://www.electron.build/nsis/)。
