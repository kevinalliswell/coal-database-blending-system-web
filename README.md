# coal-database-blending-system-web

煤种数据库管理及配煤优化 Flask Web 项目。当前仓库基于历史遗留代码整理而来，保留原有煤种管理、智能混煤优化、置换比计算和报表导出能力，同时补齐标准 Flask 应用工厂结构、SQLAlchemy、Flask-Migrate、运行入口和 GitHub 项目基础文件。

## 项目特点

- 保留原有业务代码和前端页面，不用示例代码替换真实逻辑
- 新增标准 `app/` 包，采用 Flask 应用工厂模式
- 默认使用 SQLite/SQLAlchemy 管理煤种数据，CSV 仅作为初始种子和导入文件格式
- 同步接入 Flask-SQLAlchemy 和 Flask-Migrate，支持本地自动建表和后续迁移管理
- 提供 `run.py` 和 `wsgi.py`，兼容本地开发与 Gunicorn 部署

## 技术栈

- Flask 3.0.0
- Flask-SQLAlchemy 3.1.1
- Flask-Migrate 4.0.5
- Flask-Cors 4.0.0
- SQLAlchemy 2.0.23
- pandas / numpy / scipy / openpyxl
- PyMySQL

## 当前目录结构

```text
.
├── app/                     # 标准 Flask 应用包
│   ├── __init__.py          # 应用工厂
│   ├── config.py            # 配置管理
│   ├── extensions.py        # Flask 扩展实例
│   ├── models/              # SQLAlchemy 模型
│   ├── routes/              # 蓝图注册与页面路由
│   ├── services/            # SQLite 煤种服务与历史服务兼容导出
│   └── utils/               # 历史工具兼容导出
├── backend/                 # 业务路由、算法服务和工具实现
├── data/                    # 样例数据与运行数据目录
├── static/                  # 静态资源
├── templates/               # 页面模板
├── run.py                   # 本地开发入口
├── wsgi.py                  # WSGI 入口
├── requirements.txt
├── .env.example
└── .gitignore
```

## 快速开始

### 1. 创建并激活虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

默认使用 `sqlite` 数据模式，数据库文件位于 `data/coal_system.db`。首次访问接口时会自动建表，并在煤种表为空时从 `data/test_coal_datas.csv` 初始化种子数据。也可以通过 `DATABASE_URL` 指向其他 SQLAlchemy 数据库连接。

### 4. 启动项目

```bash
python run.py
```

启动后访问：

- 首页：`http://127.0.0.1:5000/`
- 煤种管理：`http://127.0.0.1:5000/coal_management`
- 智能混煤：`http://127.0.0.1:5000/smart_blending`
- 置换比计算：`http://127.0.0.1:5000/replacement_ratio`
- 健康检查：`http://127.0.0.1:5000/health`

## Flask 工厂与扩展

项目入口统一使用：

```python
from app import create_app

app = create_app()
```

已经接入的扩展：

- `Flask-SQLAlchemy`
- `Flask-Migrate`
- `Flask-Cors`

## 数据库迁移

当前仓库已经包含迁移目录和基线迁移脚本。新环境启动前可执行：

```bash
flask --app run.py db upgrade
```

当 ORM 模型发生结构性变更时，再生成新的迁移脚本：

```bash
flask --app run.py db migrate -m "describe schema change"
flask --app run.py db upgrade
```

说明：

- 默认运行模式为 SQLite，煤种管理和智能混煤接口均通过 ORM 读取同一份数据
- CSV 文件不再作为运行时存储，只保留为初始化种子和批量导入来源

## 主要接口

- `GET /api/coals`
- `GET /api/coals/<coal_id>`
- `POST /api/coals`
- `PUT /api/coals/<coal_id>`
- `DELETE /api/coals/<coal_id>`
- `POST /api/coals/upload`
- `POST /api/optimization`
- `GET /api/optimization/history`
- `POST /api/calculate_theory_ratio`
- `POST /api/calculate_actual_ratio`
- `POST /api/optimization/export/current`

## 运行与部署

### 本地开发

```bash
python run.py
```

### Gunicorn

```bash
gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app
```

## 注意事项

- 不要提交 `.env`、虚拟环境、缓存文件和数据库文件
- `data/uploads/`、`data/history/` 属于运行时产物，已加入 `.gitignore`
- `backend/` 当前承载业务路由、算法服务和通用工具，`app/` 负责应用工厂、模型、配置和蓝图装配

## 后续建议

- 补充更多浏览器端流程测试，覆盖煤种 CRUD、导入导出、智能混煤、置换比和历史详情弹窗
- 持续收敛 `backend/` 与 `app/` 的兼容层边界，优先减少重复入口和过期说明
- 按实际部署环境补充数据库备份、迁移回滚和运行监控说明
