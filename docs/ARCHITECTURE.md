# CBOS 2.0 架构

## 运行结构

React/Vite SPA 通过同源 `/api` 访问 Flask。数据库由 SQLAlchemy 管理，Alembic 执行版本迁移。Docker 在 Gunicorn 启动前单次迁移；HTTP 请求不再建表或种子导入。

Windows 使用 Electron 沙箱渲染进程，主进程代理 `cbos://app` 到随机 loopback 端口的冻结 Python 后端。每次启动生成通信令牌，后端验证后才路由请求；登录会话 cookie 只存在主进程内存，退出应用即丢失。应用持久密钥与通信令牌独立。渲染进程不获得 Node、数据库路径访问权或登录 cookie。

## 数据流

```
煤种主档 → 到货批次 → 不可变化验修订(raw)
                         ↓ 逐指标换算/功能准入
系统设置版本 ──────→ 计算采用值
                         ↓ LP 可行性 / NSGA-II
                         → 结果快照 → 历史 / 报告
```

`app/services/assay_conversion.py` 是换算与准入真源；`catalog_service.py` 负责批次修订与迁移；`catalog_import.py` 负责预览快照和一次性提交。导入预览绑定用户，提交采用事务和版本冲突检测。

## 身份与权限

四角色固定权限。`app/routes/access.py` 的中央 before-request guard 对所有 `/api` 请求执行会话和权限检查，写请求额外检查 CSRF。会话在数据库保存随机令牌散列及有效期，密码采用 Werkzeug 安全散列。账号停用、角色变化和改密撤销会话。首次 Web 管理员通过服务器 CLI 创建；桌面初始化额外要求主进程通信认证。没有默认密码，也没有测试模式授权绕过。

## 算法边界

现有六项线性混合指标使用统一质量口径。LP 建立可行性证明/最低成本 seed；NSGA-II 优化 `(cost,-heat,quality_penalty)`，约束处理和推荐规则保持原实现。质量偏离分由灰分、硫分及挥发分/固定碳窗口组成，不是实测工艺风险。

理论置换比独立使用干基元素模型；数据缺失不再采用示例值，模型常量和显式工程估算进入快照。煤粉分解热、物理热通过 API 显式提交 kJ/kg 干煤；适配层除以 4.1868 得到内核所用 kcal_IT/kg，模型以相同系数恢复 kJ/kg，响应亦标明 kJ/kg。化验热值和模型热耗采用同一卡定义：1 kcal_IT = 4.1868 kJ。混煤优化 API 的热值约束及结果仍以 kcal/kg 表示，页面按保存的显示单位换算。旧历史不重新计算或以当前设置补写缺失口径。

## 发布与版本

版本真源为 `app/__version__.py`；桌面和前端清单在版本准备阶段同步。构建提交写入构建信息，前端关于页通过系统信息 API 读取。帮助内容直接从 docs/USER_GUIDE.md 打包，更新记录直接从 CHANGELOG.md 打包。

Release 仅手动指定完整 SHA 与版本触发，在同一工作流中编排 Linux、Docker 和 Windows 验收。构建期间不修改版本或提交；正式发布前核对附注标签、资产校验和与镜像 digest。普通 PR 构建不能取消发布构建。
