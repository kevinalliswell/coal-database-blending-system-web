# CBOS — 煤质数据库与配煤优化

面向钢厂喷煤配料的煤质管理、统一基准换算、NSGA-II 多目标混煤与置换比计算工具。提供 Web 和 Windows x64 离线版本；账号、设置和数据按部署独立保存。

## 2.0 功能

- 煤种主档 → 到货批次 → 不可变化验修订；手工、CSV/XLSX 和表格粘贴录入。
- 逐指标保存原值、单位、基准；按依赖换算，不完整记录可存档、相关计算严格准入。
- 默认收到煤质量配比、收到基恒容低位热值、元/收到吨；报价与热值同步归一。
- 线性可行性预检与 NSGA-II Pareto 候选；历史保存原值、采用值、设置和操作者快照。
- 管理员、数据维护员、计算员、只读四角色；系统设置、离线帮助和版本信息。

## 安装与升级

正式安装资产、校验和与镜像信息在 [GitHub Releases](https://github.com/kevinalliswell/coal-database-blending-system-web/releases)。Windows 安装包当前未签名。部署前备份旧数据库，按 [2.0 升级说明](docs/UPGRADE_2.0.md) 操作。

私有仓库的 Release 需要登录获授权的 GitHub 账号；私有镜像先按 [GHCR 认证步骤](docs/DEPLOYMENT.md#私有镜像认证) 登录。正式发布保留已确认的访问范围。

Web 示例：

```sh
docker run -d --name cbos -p 127.0.0.1:5000:5000 -v cbos-data:/app/data \
  ghcr.io/kevinalliswell/coal-database-blending-system-web:2.0.0
docker exec -it cbos flask --app wsgi users create-admin --username admin
```

系统没有默认密码。Windows 首次启动创建管理员；Web 通过服务器 CLI 初始化。

## 文档

| 文档 | 内容 |
| --- | --- |
| [用户手册](docs/USER_GUIDE.md) | 录入、导入、缺项处理、计算、权限、备份 |
| [煤质基准契约](docs/DATA_BASIS_CONTRACT.md) | 身份、单位、准入与快照规则 |
| [换算规范](docs/ASSAY_CONVERSION.md) | 公式、来源、依赖、固定碳差减及实例 |
| [API 参考](docs/API_REFERENCE.md) | 认证、批次修订、导入、计算与设置 |
| [批次与导入接口](docs/CATALOG_IMPORT_API.md) | 预览确认、修订、归档和安全导出 |
| [置换比输入契约](docs/REPLACEMENT_V2.md) | 干基模型、热量单位、显式估算及来源 |
| [架构](docs/ARCHITECTURE.md) | Web/桌面、权限和算法边界 |
| [Web 部署](docs/DEPLOYMENT.md) | 初始化、升级、反向代理与恢复 |
| [Windows 指南](docs/WINDOWS_DESKTOP.md) | 安装、备份、构建与验证 |
| [升级与发布说明](docs/UPGRADE_2.0.md) | 不兼容变化、恢复与资产核验 |
| [发布操作规程](docs/RELEASE.md) | 固定提交验收、发布门禁与中断恢复 |
| [CHANGELOG](CHANGELOG.md) | 各版本变更 |

## 开发验证

```sh
pip install -r requirements-dev.txt
python -m pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
node --test frontend/tests/*.test.mjs
npm --prefix desktop ci
npm --prefix desktop test
```

数据库迁移使用 Alembic。HTTP 请求不执行建库；从源码运行前执行 `flask --app wsgi initialize`。普通合并不自动发布；正式发布只在显式指定主线完整 SHA 的工作流中执行。

数值约束可行不等于现场工艺验证通过。本期采用线性混合及声明的模型边界，不预测煤种非线性燃烧相互作用。
