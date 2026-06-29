# backend 兼容层说明

`backend/` 目录保留了项目原有业务模块，并继续承载部分已注册的路由、算法服务和工具函数。当前项目入口已经统一到 `app.create_app()`，本地运行请使用仓库根目录的 `run.py` 或 `wsgi.py`，不要再直接运行 `backend/app.py`。

## 当前职责

- `backend/routes/`：煤种管理、智能混煤、置换比和报表导出的 API 蓝图实现。
- `backend/service/`：智能混煤算法、置换比计算和评价服务。
- `backend/utils/`：上传文件读取、Excel 报告、参数校验等通用工具。
- `backend/config.py`：兼容导出 `app.config` 中的配置类。

`app/` 目录负责应用工厂、扩展初始化、SQLAlchemy 模型、迁移、页面路由和兼容导出。`app/routes/*.py` 会注册或转发这些业务蓝图。

## 数据存储

当前默认数据模式为 SQLite/SQLAlchemy：

- 煤种管理 CRUD 直接读写 SQLite 煤种表。
- 智能混煤优化通过 ORM 读取被选煤种，不再读取 CSV 作为运行时主数据。
- 优化历史和置换比历史写入 SQLite 历史表。
- CSV/Excel 仅作为首次种子初始化、批量导入和导出交换格式。

首次访问接口时，应用会自动建表，并在煤种表为空时从 `data/test_coal_datas.csv` 导入种子数据。

## 开发约定

- 新的应用入口、配置和模型变更优先放在 `app/`。
- 业务算法和既有 API 行为可以继续在 `backend/` 中演进，但要避免重新引入 CSV 运行时存储。
- 涉及数据库结构时，使用 Flask-Migrate 生成新迁移，并运行 `flask --app run.py db upgrade` 验证。
- 前端页面和交互更新后，需要同步检查相关 API 文档和浏览器冒烟流程。
