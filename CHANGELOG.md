# CHANGELOG


## v2.0.0 (2026-09-20)

### 新增

- Web 与 Windows 离线版统一的本地账号、四角色权限、用户管理、系统设置、帮助和关于页面。
- 煤种主档、到货批次、不可变化验修订；原值、单位、基准和报价的完整保留与结果快照。
- CSV/XLSX 与表格粘贴预览、列映射确认、用户绑定的一次性导入、全修订导出。
- 按混煤 / 理论置换比分别判断数据可用性，明确显示缺项、转换依赖与数据冲突。
- Windows x64 安装包与免安装 ZIP，本机每次启动登录、备份迁移和本机密码恢复。

### 变更

- 默认采用收到煤质量配比、收到基恒容低位热值、元/收到吨成本；系统设置管理质量口径、约束模板和算法预设。
- 支持逐指标 ad/ar/d/daf 路径换算、固定碳差减及恒容高低位换算，计算前统一工业分析闭合检查。
- 配料项引用化验修订 ID；同煤种不同批次可同时混配，同批次只采用一份修订。
- 帮助直接复用 docs/，版本来自单一来源；Release 改为显式固定 SHA 验收后统一发布。
- 发布明确校验私有/公开访问范围，仓库与镜像权限必须一致；私有发布支持认证下载，流程不自动扩大访问权限。

### 修复

- 消除缺失化验/炉况自动套用示例值的置换比计算；工程估算必须显式选择并保留来源。
- 消除不同低位热值换基不必要的氢依赖，统一热量单位系数与原始/派生数据溯源。
- 后端逐接口校验权限与 CSRF；改密、停用、角色修改撤销会话，保护最后一位有效管理员。
- 账号切换清理缓存，用户草稿与主题隔离；桌面 cookie 仅保存在主进程内存。
- 拒收跨账号、跨设置版本的迟到响应；CSV/XLSX 导出防止文本被作为公式执行，并保留可还原的原文。

### 不兼容变更

- 移除未确认数据试算与计算页基准选择；旧 selected_coal_ids 请求返回升级提示，不自动猜批次。
- 旧煤质写入、覆盖导入和删除接口停止使用，改为批次化验修订和归档。
- 理论置换比要求明确修订、单位和炉况；旧未经标定的高级修正不再隐式应用。

### 升级要求

- 升级前备份，按 docs/UPGRADE_2.0.md 执行初始化/迁移与首管理员创建，没有默认密码。
- 历史煤原值迁入历史批次，未知元数据保持未知，补齐相关数据后才能计算；旧历史不补写不存在的信息。
- 安装前核对 SHA256SUMS.txt、版本与完整构建 SHA。

### 已知限制

- Windows 资产未配置代码签名；本期提供 Windows x64 和 Linux amd64 镜像。
- 各部署账号与数据独立，不自动同步；恒压/未知热值仅可存档。
- 线性混合和理论模型不预测非线性燃烧作用，数值可行不代表现场工艺验证。


## v1.1.1 (2026-09-15)

### Bug Fixes

- Use explicit blast enthalpy and separate replacement heat terms
  ([`5953c67`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/5953c67238a48fc51aa3df4090a08461c63828d7))


## v1.1.0 (2026-09-15)

### Bug Fixes

- Accelerate constrained NSGA-II and expose effective controls
  ([`6e746e1`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/6e746e129943ff729d5d22cbcb20b0dcf074b3d5))

- Bind blending results and reports to immutable run inputs
  ([`9b43d47`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/9b43d47c1f5995389d138c831b82efacb1561882))

- Distinguish basis-checked blends from screening results
  ([`8586068`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/8586068535396565de1dbaa8810466e3b8fa9fc2))

- Label heuristic quality scores and missing assay bases clearly
  ([`5a88675`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/5a886759c494e018c51ee92690bb1bc425e4bffc))

- Preserve calculation mode and basis validation in run snapshots
  ([`4337b24`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/4337b247954c0c52570587c6af7b7ae82b591fa4))

- Preserve complete Pareto recommendations and final offspring
  ([`2d81b1f`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/2d81b1f6942e4f5bd488be7fdb4e8c1027105203))

- Validate coal data consistently and preserve full exports
  ([`88b78b8`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/88b78b88a35b8bcc4824924aa74fe51647958bca))

- Validate unique coal identities and optimization bounds
  ([`20fe6e3`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/20fe6e3bcb1170022d4df064c1392bd8b5164dd8))

### Chores

- Remove dead code and stale docs
  ([`89ee125`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/89ee125ee47cbeacfb29474cab1b9fb9939fbdc3))

Delete unreferenced compat shims and orphaned files confirmed via a full repo-wide grep + Docker/CI
  reference check, and sync the docs that described them:

- backend/app.py, backend/config.py: historical compat layers never imported anywhere;
  app.create_app() via run.py/wsgi.py is the only entry point in use. -
  backend/requirements_modular.txt: stale dependency list (Flask 2.3.3 era) superseded by
  requirements.txt; not referenced by Docker or CI. - backend/service/ustb_evaluation.py:
  zero-importer algorithm module. - static/images/*.png + the /images compat route in
  app/routes/pages.py (and its STATIC_IMAGES_DIR config): leftover from the removed Jinja/matplotlib
  report frontend, not linked from the current SPA. - GA_OPTIMIZATION_PLAN.md: V1 algorithm planning
  doc, already implemented and documented in docs/ARCHITECTURE.md section 6.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

### Continuous Integration

- Run regression tests for stacked fix pull requests
  ([`3865127`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/3865127e60103bb0ec1cff5f95d54f57b463edcc))

### Documentation

- Add Windows Server deployment guide
  ([`ee550b9`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/ee550b95397ab017ef672a016e41e6c2c629d58e))

### Features

- Require declared coal bases for verified blending
  ([`13fdc52`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/13fdc5222efacd903d89dbbf4055790a8e662833))


## v1.0.1 (2026-07-02)

### Bug Fixes

- Serve SPA assets on Windows
  ([`154bbda`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/154bbda6bb42d62c267f559970d1637b77e90ce2))

### Continuous Integration

- Drop pip cache from release workflow to fix failing post-step
  ([`389b191`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/389b1913032755c32208c9bb38d22ab70d2d343d))

The release job installs no pip dependencies (python-semantic-release manages its own environment),
  so `cache: pip` on setup-python had nothing to cache and its cache-save post-step failed the whole
  job — every release run showed red despite the release and artifacts succeeding. Removing the
  cache directive makes the pipeline report accurately.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Documentation

- Add architecture, deployment, and user guide; optimize API reference
  ([`a0fdf73`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/a0fdf736ad88709ef395e381dac05c8df1d836f1))

- docs/ARCHITECTURE.md: system architecture (SPA + Flask single container), tech stack, request
  flow, backend layering, data model, NSGA-II overview, frontend architecture, directory tree,
  design trade-offs (with a diagram). - docs/DEPLOYMENT.md: Docker/compose/GHCR, env vars,
  SQLite/MySQL + migrations, local dev, gunicorn + nginx, CI and the semantic-release pipeline. -
  docs/USER_GUIDE.md: per-page operator guide (dashboard, coal DB, smart blending, replacement
  ratio, history), theme toggle and demo mode. - docs/API_REFERENCE.md: rewritten and verified
  against the actual routes and model serializers; every /api endpoint with request/response
  contracts. - README.md: documentation index.

Verified against the codebase via an adversarial review pass.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>


## v1.0.0 (2026-07-01)

### Features

- Rebuild frontend as Vite/React SPA with dual-theme console
  ([`2ac8218`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/2ac8218f391890d3f0a87e95f92bc7d57572ecc3))

Replace the server-rendered Jinja/Bootstrap frontend with a Vite + React + TypeScript single-page
  app (frontend/): a dark "Furnace Console" and light "Foundry Daylight" theme with one-click
  toggle, TanStack Query data layer, ECharts visualizations (interactive Pareto frontier), and a
  mock engine for backend-free demos. Flask now serves the built SPA (frontend/dist) via a catch-all
  route; the /api surface is unchanged.

Adds a full-stack Dockerfile, docker-compose, and extends the release workflow to build the image,
  attach it to the GitHub Release, and push to GHCR.

BREAKING CHANGE: the old server-rendered pages (templates/, static/js, static/css) are removed; page
  routes now serve the single-page app instead of Jinja templates, so deployments must build
  frontend/dist or run the Docker image.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

### Breaking Changes

- The old server-rendered pages (templates/, static/js, static/css) are removed; page routes now
  serve the single-page app instead of Jinja templates, so deployments must build frontend/dist or
  run the Docker image.


## v0.2.0 (2026-06-29)

### Features

- Add version management, conventional changelog, and CI workflow
  ([#9](https://github.com/kevinalliswell/coal-database-blending-system-web/pull/9),
  [`5776d5f`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/5776d5ff0c67f366c49d7b9965114bd58ab0ffa6))

* feat: add version management, conventional changelog, and CI workflow

- Add app/__version__.py tracking the current version (0.1.4); expose it via app.__init__ so it is
  importable from the package - Add pyproject.toml with python-semantic-release v9 config: reads
  conventional commits (feat→minor, fix→patch, breaking→major) to determine the next version,
  updates __version__.py and CHANGELOG.md, commits the change, creates an annotated tag, and
  publishes a GitHub release — all automatically on every push to main - Replace hand-rolled
  release-on-main.yml bash script with the official
  python-semantic-release/python-semantic-release@v9 action - Add .github/workflows/ci.yml that runs
  the full test suite on every PR targeting main (Python 3.11, pip cache) - Add CHANGELOG.md with
  hand-authored history for v0.1.0–v0.1.4; future entries will be generated automatically

* fix(ci): install pytest via requirements-dev.txt

CI was failing with 'No module named pytest' because pytest is not in requirements.txt. Add
  requirements-dev.txt that pulls in all prod deps plus pytest, and point the CI workflow at it.

---------

Co-authored-by: Claude <noreply@anthropic.com>


## v0.1.4 (2026-06-12)


## v0.1.3 (2026-06-10)


## v0.1.2 (2026-06-10)


## v0.1.1 (2026-04-25)


## v0.1.0 (2026-04-24)

### Bug Fixes

- Restore merged cell borders in export report
  ([`bff6159`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/bff6159222dcaf1fc88c2acdef2355c829cbfbf4))

- Sanitize optimization API JSON responses
  ([`dcffda3`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/dcffda3b7ac290f91c998c737b5f1e99ce918937))

### Chores

- Add PR template and release workflow
  ([`ad91219`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/ad91219e75a2b340a990240f851b9d0bf73ebb6e))

### Documentation

- Add API reference guide
  ([`b22f1f8`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/b22f1f8b335eb9001668e24b16815e32037f36a4))

- Add PCI GA optimization plan
  ([`a1edf9a`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/a1edf9a66ecd586676b6494e85b0af07f6d68340))

### Features

- Align PCI blending optimization with hard constraints
  ([`af8124f`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/af8124fa5ad97ccdb09bc0af92a967832931160d))

- Improve sharing copy and A4 export report layout
  ([`0d35268`](https://github.com/kevinalliswell/coal-database-blending-system-web/commit/0d352680a93adf497bcd3af58c690a419dbe5b13))
