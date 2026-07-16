# coal-database-blending-system-web

**煤粉数据库管理及配煤优化控制台** —— 面向钢厂高炉喷吹配煤（PCI）场景的煤种数据管理、多目标混煤优化与置换比计算系统。

前端已整体重构为 **Vite + React + TypeScript 单页应用**（源码 `frontend/`），后端沿用 **Flask + SQLAlchemy** 的 JSON API。生产由 Flask + Gunicorn 一体托管：`/api/*` 提供接口，其余路径回退到 SPA。

## 功能

- **煤种数据库**：工业分析与元素分析指标的增删改查、检索、批量导入/导出。
- **智能混煤优化**：NSGA-II 多目标 Pareto 优化，在工艺约束可行域内权衡成本、热值与质量风险，输出推荐配比与候选方案集。
- **置换比计算**：高炉喷吹煤的理论置换比与实际生产置换比（含生产因素修正）。
- **历史追溯**：混煤优化与置换比计算的历史记录与详情。

## 技术栈

**前端**：Vite 5 · React 18 · TypeScript · TanStack Query · React Router · ECharts；手写 CSS 设计系统（暗色 *Furnace Console* / 亮色 *Foundry Daylight* 双主题，可一键切换）。

**后端**：Flask 3 · Flask-SQLAlchemy · Flask-Migrate · Flask-Cors · SQLAlchemy 2 · pandas / numpy / scipy / openpyxl · Gunicorn。默认 SQLite，可用 `DATABASE_URL` 切换。

## 目录结构

```text
.
├── frontend/                # Vite + React 单页应用（新前端）
│   ├── src/                 # 页面、组件、设计系统、API 客户端与演示引擎
│   └── dist/                # 构建产物（由 Flask 生产托管，构建生成）
├── app/                     # Flask 应用工厂、配置、模型、蓝图（含 SPA 托管路由）
├── backend/                 # 业务路由、算法服务与工具实现
├── data/                    # 样例种子数据与运行期数据目录
├── migrations/              # 数据库迁移
├── static/                  # favicon 等静态资源
├── Dockerfile               # 全栈单镜像（构建 SPA + Python 运行时）
├── docker-compose.yml
├── run.py / wsgi.py         # 本地开发 / WSGI 入口
└── requirements.txt
```

## 快速开始

### 方式一：Docker（推荐）

```bash
docker compose up --build
# 或使用已发布镜像：
docker run -p 5000:5000 ghcr.io/kevinalliswell/coal-database-blending-system-web:latest
```

访问 `http://127.0.0.1:5000/`。每个 GitHub Release 也附带可离线导入的镜像资产
`cbos-web-<version>-docker-image.tar.gz`：

```bash
docker load < cbos-web-1.0.0-docker-image.tar.gz
```

### 方式二：本地开发（前后端分离）

后端：

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py            # http://127.0.0.1:5000
```

前端（另开终端，默认演示模式，内置合成数据，无需后端）：

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173
```

连接真实后端时，前端 `.env.production` 已默认 `VITE_USE_MOCK=false`；开发态如需连真后端，
将 `.env.development` 的 `VITE_USE_MOCK` 改为 `false` 即可，Vite 会把 `/api` 代理到 `:5000`。

### 方式三：本地一体运行（Flask 托管构建产物）

```bash
cd frontend && npm install && npm run build && cd ..
python run.py           # http://127.0.0.1:5000 直接返回构建后的 SPA
```

## 数据库迁移

```bash
flask --app run.py db upgrade
# 模型结构变更后：
flask --app run.py db migrate -m "describe change"
flask --app run.py db upgrade
```

首次访问接口时会自动建表，并在煤种表为空时从 `data/test_coal_datas.csv` 初始化种子数据。

## 主要接口（`/api` 前缀）

- `GET /api/coals` · `GET /api/coals/<id>` · `POST /api/coals` · `PUT /api/coals/<id>` · `DELETE /api/coals/<id>`
- `POST /api/coals/batch_delete` · `POST /api/coals/upload` · `POST /api/coals/export` · `GET /api/coals/template`
- `POST /api/optimization` · `GET /api/optimization/history` · `GET /api/optimization/history/<id>`
- `POST /api/calculate_theory_ratio` · `POST /api/calculate_actual_ratio`
- `GET /api/replacement_ratio/history` · `GET /api/replacement_ratio/history/<id>`
- `POST /api/optimization/export/current` · `GET /api/optimization/export/<id>` · `POST /api/replacement_ratio/export`
- `GET /health`

## 文档

- [架构与技术栈说明](docs/ARCHITECTURE.md) —— 系统架构、技术选型、数据流与设计取舍
- [API 接口文档](docs/API_REFERENCE.md) —— 全部 `/api` 端点的请求/响应契约
- [部署文档](docs/DEPLOYMENT.md) —— Docker、环境变量、数据库、CI/自动发布
- [用户手册](docs/USER_GUIDE.md) —— 面向配煤工程师的分页操作指引
- [前端说明](frontend/README.md) —— 前端技术栈、主题与开发方式

## 发布

`main` 分支合并后由 GitHub Actions（Python Semantic Release）按 Conventional Commits 自动定版、
打 tag 并创建 Release，同时构建全栈 Docker 镜像：推送到 GHCR 并将镜像 `tar.gz` 附加为 Release 资产。

## 注意事项

- 不要提交 `.env`（后端）、虚拟环境、`node_modules`、构建产物和数据库文件。
- `data/uploads/`、`data/history/` 属于运行期产物。
