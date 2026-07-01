# 部署文档

**煤粉数据库管理及配煤优化控制台**（GitHub 仓库 `coal-database-blending-system-web`，当前版本 `v1.0.0`）的部署与运维指南。

- 架构总览：[./ARCHITECTURE.md](./ARCHITECTURE.md)
- 接口说明：[./API_REFERENCE.md](./API_REFERENCE.md)
- 使用手册：[./USER_GUIDE.md](./USER_GUIDE.md)
- 项目说明：[../README.md](../README.md)
- 前端说明：[../frontend/README.md](../frontend/README.md)

> 生产形态为**全栈单容器**：Vite + React + TypeScript 单页应用（源码 `frontend/`）在镜像内构建为静态产物，交由 Flask + Gunicorn 一体托管。`app/routes/pages.py` 用 catch-all 路由托管 `frontend/dist`（history 模式回退 `index.html`），`/api/*` 提供 JSON 接口，`/health` 提供健康检查。旧的 Jinja/Bootstrap 服务端页面已整体移除。

---

## 1. 部署方式总览

| 方式 | 适用场景 | 前端 | 后端 | 数据 |
| --- | --- | --- | --- | --- |
| Docker 单镜像 | 生产 / 演示 / 一键起 | 镜像内构建，Flask 托管 | Gunicorn | SQLite（默认，卷持久化）或外部 MySQL |
| 本地一体运行 | 无 Docker 的生产/预演 | `npm run build` 产出 `frontend/dist`，Flask 托管 | `python run.py` 或 Gunicorn | SQLite / MySQL |
| 前后端分离开发 | 日常开发 | `npm run dev`（Vite，端口 5173） | 可选（演示模式无需后端） | 演示模式内置合成数据；真实模式走 Flask |

三种方式共用同一套后端配置（见 [环境变量表](#3-环境变量表)），区别只在于前端如何提供以及是否连接真实后端。

---

## 2. Docker 部署

镜像为多阶段构建（见 [`../Dockerfile`](../Dockerfile)）：`node:20-slim` 构建 SPA → `python:3.11-slim` 运行 Gunicorn。容器监听 **5000** 端口，工作目录 `/app`，运行期数据落在 `/app/data`。

### 2.1 docker compose（推荐）

[`../docker-compose.yml`](../docker-compose.yml) 已声明端口映射、环境变量与持久化卷：

```bash
docker compose up --build
```

启动后访问 `http://localhost:5000`。默认配置：

- `FLASK_CONFIG=production`、`DATA_STORAGE_MODE=sqlite`
- 命名卷 `cbos-data` 挂载到 `/app/data`，持久化 SQLite 与上传文件
- `restart: unless-stopped`

> 生产务必覆盖 `SECRET_KEY`（compose 中默认值为 `change-me-in-production`，仅用于本地）。切换外部数据库时，取消 compose 内 `DATABASE_URL` 一行的注释。

### 2.2 直接运行 GHCR 镜像

发布流水线会把镜像推送到 GHCR：

```bash
docker run -d --name cbos-web \
  -p 5000:5000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -v cbos-data:/app/data \
  ghcr.io/kevinalliswell/coal-database-blending-system-web:1.0.0
```

`:latest` 指向最新发布版本；生产建议固定到具体版本号（如 `:1.0.0`）以保证可复现。

### 2.3 从 Release 资产离线导入

每个 Release 附带打包好的镜像 `cbos-web-<版本>-docker-image.tar.gz`（内网/离线环境适用）：

```bash
docker load < cbos-web-1.0.0-docker-image.tar.gz
# 加载后镜像名即 ghcr.io/kevinalliswell/coal-database-blending-system-web:1.0.0
docker run -d --name cbos-web -p 5000:5000 \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -v cbos-data:/app/data \
  ghcr.io/kevinalliswell/coal-database-blending-system-web:1.0.0
```

### 2.4 端口、卷与健康检查

| 项 | 值 | 说明 |
| --- | --- | --- |
| 端口 | `5000` | 容器内 Gunicorn 监听 `0.0.0.0:5000`，`EXPOSE 5000` |
| 持久化卷 | `/app/data` | SQLite 数据库、`uploads/`、`history/` 等运行期产物 |
| 健康检查 | `HEALTHCHECK` | `--interval=30s --timeout=5s --start-period=20s --retries=3`，探测 `http://127.0.0.1:5000/health`，返回 200 视为健康 |
| 启动命令 | `gunicorn -w 2 -b 0.0.0.0:5000 --timeout 180 wsgi:app` | 2 个 worker，请求超时 180s（NSGA-II 优化耗时较长） |

`/health` 返回 JSON，包含 `status`、`app`、`storage_mode`、`coal_count`，可用于负载均衡探活与运维巡检。

---

## 3. 环境变量表

后端配置见 [`../app/config.py`](../app/config.py)，通过环境变量（或项目根 `.env`，由 `python-dotenv` 加载）注入。

### 3.1 后端环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `FLASK_CONFIG` | `default`（= `development`） | 配置档：`development` / `production`。镜像内固定为 `production` |
| `DATA_STORAGE_MODE` | `sqlite` | 数据模式，`sqlite` / `database` 均启用数据库；镜像内固定为 `sqlite` |
| `DATABASE_URL` | 空 → 默认 SQLite `data/coal_system.db` | SQLAlchemy 连接串；设置后覆盖默认 SQLite（见 [数据库](#4-数据库)） |
| `SECRET_KEY` | `change-me-in-production` | Flask 会话/签名密钥，**生产必须覆盖为随机值** |
| `HOST` | `0.0.0.0` | `python run.py` 监听地址（Gunicorn 由 `-b` 指定，不读此项） |
| `PORT` | `5000` | 服务端口 |
| `MAX_CONTENT_LENGTH` | `16 * 1024 * 1024`（16 MB，代码内固定） | 上传体积上限，用于导入 CSV/Excel；非环境变量，如需调整改 `config.py` |

> 说明：`MAX_CONTENT_LENGTH`、`ALLOWED_EXTENSIONS`（`csv`/`xlsx`/`xls`）、`UPLOAD_FOLDER`、`SPA_DIST_DIR` 等在 `config.py` 中为常量，随代码固定，不通过环境变量配置。

### 3.2 前端构建期变量（Vite）

前端变量在**构建时**注入，见 [`../frontend/vite.config.ts`](../frontend/vite.config.ts) 与 `frontend/.env*`：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_USE_MOCK` | 开发 `true` / 生产 `false` | 演示模式开关。`true` 时使用内置合成引擎（NSGA-II 与置换比），**无需后端**；`false` 直连同源 `/api` |
| `VITE_API_TARGET` | `http://127.0.0.1:5000` | 仅 Vite dev server 使用：将 `/api` 与 `/health` 代理到该地址 |

`.env` 存放共享项（`VITE_API_TARGET`），`.env.development` 设 `VITE_USE_MOCK=true`，`.env.production` 设 `VITE_USE_MOCK=false`。Docker 镜像执行 `npm run build`，自动采用 `.env.production`（演示模式关闭，同源直连 `/api`）。

---

## 4. 数据库

### 4.1 默认 SQLite 与自动播种

- 默认连接串 `sqlite:///data/coal_system.db`（由 `config.py` 依据 `DATA_STORAGE_MODE`/`DATABASE_URL` 推导）。
- 首次请求时触发 `before_request` 钩子（`app/__init__.py` → `ensure_coal_data_initialized`）：执行 `db.create_all()` 自动建表；若表为空且存在 `data/test_coal_datas.csv`，则从该 CSV 自动播种煤种数据。
- 数据库文件位于 `/app/data`（容器）或项目 `data/`（本地），需随卷持久化。

### 4.2 切换 MySQL

镜像已内置 `PyMySQL==1.1.0`。设置 `DATABASE_URL` 即可切换：

```bash
DATABASE_URL="mysql+pymysql://user:pass@db-host:3306/cbos?charset=utf8mb4"
```

compose 示例（取消注释并按需修改）：

```yaml
environment:
  DATABASE_URL: mysql+pymysql://user:pass@db:3306/cbos
```

切换后首次请求同样会 `create_all()` 建表并按需播种（目标库须已存在、账号有建表权限）。

### 4.3 Flask-Migrate 迁移

仓库使用 Flask-Migrate（Alembic），迁移脚本在 `migrations/versions/`（已含初始化 schema 与优化历史表两个版本）。常规命令：

```bash
# 应用全部迁移到最新版本
flask db upgrade

# 变更模型后生成新迁移
flask db migrate -m "描述本次变更"

# 回退一个版本
flask db downgrade -1
```

> 运行 `flask` 命令需设置 `FLASK_APP=wsgi:app`（或 `run.py`）。日常 SQLite 场景下自动建表已足够；跨版本升级或使用 MySQL 时，推荐用迁移管理 schema 演进。

### 4.4 持久化与备份

- **SQLite**：备份即拷贝卷内 `data/coal_system.db`。示例：
  ```bash
  docker cp cbos-web:/app/data/coal_system.db ./backup-$(date +%F).db
  ```
  同时建议备份 `data/uploads/` 与 `data/history/`。
- **MySQL**：使用 `mysqldump` 常规备份，与容器卷解耦。
- 升级镜像前务必先备份卷数据。

---

## 5. 本地开发部署

### 5.1 后端（venv）

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # 开发另加：pip install -r requirements-dev.txt
python run.py                    # 默认 http://127.0.0.1:5000
```

`run.py` 读取 `HOST`/`PORT`/`DEBUG`，`development` 档下开启调试与热重载。

### 5.2 前端（演示模式，无需后端）

```bash
cd frontend
npm install
npm run dev                      # http://127.0.0.1:5173，VITE_USE_MOCK=true
```

演示模式下前端使用内置合成 NSGA-II 与置换比引擎，可脱离后端独立预览全部页面与双主题（暗色 Furnace Console / 亮色 Foundry Daylight）。

### 5.3 一体运行（前端构建 + Flask 托管）

想在本地复现生产的同源单端口形态：

```bash
cd frontend
npm install
npm run build                    # 产出 frontend/dist（.env.production：关演示、直连 /api）
cd ..
python run.py                    # Flask 托管 dist，http://127.0.0.1:5000
```

此时前后端同源，`/api/*` 走真实后端，其余路径回退 SPA。

> **Windows 排障（rollup 原生模块）**：若 `npm run dev`/`npm run build` 报 `Cannot find module @rollup/rollup-win32-x64-msvc` 之类错误，属 npm optional deps 已知问题（[npm/cli#4828](https://github.com/npm/cli/issues/4828)）。执行 `rm -rf node_modules package-lock.json && npm install` 重装即可。

---

## 6. 生产建议

### 6.1 Gunicorn

镜像默认：`gunicorn -w 2 -b 0.0.0.0:5000 --timeout 180 wsgi:app`。

- `-w`：worker 数，经验值 `2 * CPU + 1`，按机器与并发调整。
- `--timeout 180`：NSGA-II 多目标优化耗时较长，超时不宜过短。
- 入口为 [`../wsgi.py`](../wsgi.py) 的 `app`。自建部署示例：
  ```bash
  gunicorn -w 4 -b 0.0.0.0:5000 --timeout 180 wsgi:app
  ```

### 6.2 反向代理（Nginx）

置于 Nginx / 反向代理之后。由于 `/api` 与 SPA 静态资源**同源**由 Flask 托管，代理只需把全部流量转发到 5000（无需为 `/api` 单独拆分上游）：

```nginx
server {
    listen 80;
    server_name cbos.example.com;

    client_max_body_size 16m;   # 与后端 MAX_CONTENT_LENGTH 对齐

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;   # 与 Gunicorn --timeout 对齐
    }
}
```

单个 `location /` 已同时覆盖 `/api/*`、`/health` 与 SPA 页面（history 回退在 Flask 内完成）。

### 6.3 HTTPS

在 Nginx 层终止 TLS（如 Let's Encrypt / 企业证书），对外只暴露 443；上游明文转发到本机 5000。务必透传 `X-Forwarded-Proto`。

### 6.4 日志

- 后端日志级别 `INFO`（`config.py`），Gunicorn/Flask 日志输出到 stdout/stderr。
- 容器环境用 `docker logs cbos-web` 查看，或接入集中日志（`--log-driver`）。
- Nginx 访问/错误日志按站点单独归档。

---

## 7. CI 与自动发布流水线

### 7.1 PR 校验（`ci.yml`）

见 [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml)。对 `main` 的 Pull Request 触发：安装 `requirements-dev.txt` 后运行 `python -m pytest -q`。测试须通过方可合并。

### 7.2 合并 main 自动发布（`release-on-main.yml`）

见 [`../.github/workflows/release-on-main.yml`](../.github/workflows/release-on-main.yml)。推送到 `main` 时按序执行：

1. **定版**：Python Semantic Release（v9）依据 Conventional Commits 计算新版本，更新 `app/__version__.py`、写 `CHANGELOG.md`、打 tag、创建 GitHub Release。
2. **仅当产生新版本**（`released == 'true'`）时继续：
   - 登录 GHCR，`docker build` 全栈镜像并打 `:<版本>` 与 `:latest`；
   - `docker save | gzip` 生成 `cbos-web-<版本>-docker-image.tar.gz`，`gh release upload` 附到本次 Release；
   - `docker push` 两个 tag 到 `ghcr.io/kevinalliswell/coal-database-blending-system-web`。

> 若某次提交不触发版本变更（如仅 `docs:`/`chore:`），后续 Docker 步骤会整体跳过——**不产生新版本就不发镜像**。运维校验发布时，务必核对 Release 资产里 `cbos-web-<版本>-docker-image.tar.gz` 与 GHCR 上对应 tag **都已真实上传**，而非只看流水线绿灯。

### 7.3 Conventional Commits 与版本规则

定版配置见 [`../pyproject.toml`](../pyproject.toml)：

| 提交类型 | 版本影响（示例） |
| --- | --- |
| `fix:` | patch（`1.0.0` → `1.0.1`） |
| `feat:` | minor（`1.0.0` → `1.1.0`） |
| `BREAKING CHANGE:` / `feat!:` | major（`1.0.0` → `2.0.0`） |
| `docs:` / `chore:` / `refactor:` 等 | 通常不触发发布 |

- `major_on_zero = true`：即使处于 `0.x`，破坏性变更也会升 major。
- 发布提交为 `chore(release): v{version} [skip ci]`，并从 changelog 中排除。

---

## 8. 升级与回滚

### 8.1 升级

```bash
# 备份数据卷（见 4.4）
docker cp cbos-web:/app/data/coal_system.db ./backup-$(date +%F).db

# 拉取目标版本并重建（compose）
docker compose pull        # 或 docker pull ghcr.io/.../coal-database-blending-system-web:<新版本>
docker compose up -d

# 如涉及 schema 变更，执行迁移
docker compose exec cbos-web flask db upgrade
```

升级后用健康检查校验：

```bash
curl -fsS http://localhost:5000/health
# 期望：{"status":"ok", ...}，且 coal_count > 0
```

### 8.2 回滚

固定到上一个已知良好的版本 tag 重新部署：

```bash
docker run -d --name cbos-web -p 5000:5000 \
  -e SECRET_KEY=... -v cbos-data:/app/data \
  ghcr.io/kevinalliswell/coal-database-blending-system-web:<旧版本>
```

- 数据在命名卷中独立于镜像，回滚镜像本身不丢数据。
- 若旧版本先前执行过 `flask db upgrade`，回滚 schema 需相应 `flask db downgrade`；生产回滚前请评估迁移可逆性，并优先从备份恢复。
- 离线环境可用 [§2.3](#23-从-release-资产离线导入) 的 `docker load` 从旧 Release 资产恢复镜像。

---

> 更多背景见 [架构文档](./ARCHITECTURE.md) 与 [接口参考](./API_REFERENCE.md)；使用层面见 [用户指南](./USER_GUIDE.md)。
