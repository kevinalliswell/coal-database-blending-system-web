# 煤粉数据库管理及配煤优化控制台 · 前端

煤粉数据库管理及配煤优化系统（Coal Blending Optimization System）的前端重构版本。

一套面向钢厂高炉喷吹配煤（PCI）场景的**工业控制台**风格界面：把「煤种维护 → 多目标混煤优化 → 置换比计算 → 历史追溯」四条业务线整合进一个单页应用。

> 设计主题：**Furnace Control Console（熔炉控制台，暗色）** 以煤黑为底、熔铁琥珀为主色、仪表青为数据色；**Foundry Daylight（锻造日光，亮色）** 以暖调纸白为底、深琥珀为强调色。Chakra Petch 显示字体 + IBM Plex Mono 仪表数字 + 系统中文字体；蓝图网格纹理、发丝级描边、熔融辉光。刻意避开通用 Bootstrap/Inter 观感，贴合煤—炉—钢的行业语境。
>
> 顶栏右上角可**一键切换暗/亮主题**，选择记忆在本地；全部配色由 CSS 设计令牌驱动，ECharts 图表通过 `useChartPalette()` 读取当前主题令牌同步换肤。

---

## 技术栈

| 关注点 | 选型 | 说明 |
| --- | --- | --- |
| 框架 | **React 18 + TypeScript** | 组件化 + 类型安全（大量数值字段） |
| 构建 | **Vite 5** | 快速开发与产物构建 |
| 服务端状态 | **TanStack Query v5** | 统一数据获取、缓存、失效 |
| 路由 | **React Router v6** | SPA 无刷新导航 |
| 可视化 | **ECharts 5** | Pareto 散点、配比环图、约束余量雷达 |
| 样式 | 手写 **CSS 设计系统** | 无 UI 套件，完全掌控「熔炉控制台」视觉语言 |

后端沿用原仓库的 **Flask JSON API**（`/api`）。前端不改动后端，只作为其消费方。

---

## 快速开始

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

默认以**演示模式**启动（`VITE_USE_MOCK=true`）：内置真实的包钢煤种种子数据 + 一个合成的 NSGA-II 求解引擎与置换比计算器，**无需启动 Python 后端**即可体验全部流程（选煤、约束、求解、Pareto 前沿、置换比、历史）。演示数据写入浏览器 `localStorage`。

环境开关按模式拆分：`.env.development`（开发，默认 `VITE_USE_MOCK=true`）、`.env.production`（生产构建，默认 `VITE_USE_MOCK=false`）、`.env`（共享的 `VITE_API_TARGET`）。

### 连接真实后端

把 `.env.development` 的 `VITE_USE_MOCK` 改为 `false`，先启动 Flask 服务（`python run.py`），再 `npm run dev`。Vite 会把 `/api` 与 `/health` 代理到 `VITE_API_TARGET`。所有请求/响应字段已严格对齐后端契约（见 [`../docs/API_REFERENCE.md`](../docs/API_REFERENCE.md)）。

> 若 Windows 本地 `npm run build` 报 rollup 原生模块缺失（npm/cli#4828），执行 `npm install @rollup/rollup-win32-x64-msvc` 后重试；Docker 构建已内置该问题的兜底处理。

### 构建产物

```bash
npm run build        # 输出到 frontend/dist
npm run preview      # 本地预览产物
```

用 Flask 托管产物时，加一个「兜底路由」把非 `/api` 请求指向 `dist/index.html` 即可（SPA history 模式）：

```python
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa(path):
    full = os.path.join(app.static_folder, path)
    if path and os.path.exists(full):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')
```

---

## 目录结构

```
frontend/src
├── main.tsx / App.tsx        # 入口、应用外壳（左侧导轨 + 顶栏 + 路由）
├── styles/                   # 设计系统：tokens / base / layout / components / pages
├── lib/
│   ├── types.ts              # 与后端契约一一对应的类型
│   ├── api.ts                # API 客户端（真实后端 / 演示引擎切换）
│   ├── constants.ts          # 约束默认值、GA 档位、字段元数据
│   ├── format.ts             # 数值/时间格式化
│   └── mock/                 # 种子数据 + 合成 NSGA-II 求解与置换比引擎
├── components/
│   ├── ui/                   # 设计系统组件：Icon / Toast / Overlay / Chart / bits
│   ├── blending/             # 混煤图表 + 算法参数抽屉
│   └── CoalForm.tsx          # 煤种录入表单
└── pages/                    # Dashboard / CoalDatabase / SmartBlending /
                              # ReplacementRatio / History*（按路由懒加载）
```

---

## 相较旧版的交互改进

针对原 Bootstrap 版本梳理出的痛点逐一重做：

- **智能混煤不再层层弹窗**：约束、单煤配比边界从模态里搬到常驻工作区，「选煤 → 约束 → 配比边界 → 求解」自上而下一屏可见；老用户一键直接求解。
- **单煤配比边界独立成区**：从煤种表格里的迷你输入框中抽离，只对已选煤种展示，并实时校验「配比下限之和 ≤ 100 ≤ 上限之和」。
- **求解前预检查**：约束不自洽（min≥max、热值目标越界、配比和不满足）时即时提示并禁用求解，避免提交后才被后端拒绝。
- **算法参数档位化**：快速/标准/精细三档一键切换，12 项原始参数收进「高级参数」抽屉，去掉了只有一个选项的假下拉。
- **Pareto 可交互**：散点图点击即切换查看对应方案，表格覆盖成本/热值/灰分/硫分/风险全维度；推荐解高亮。
- **通用体验**：SPA 无刷新、骨架屏、语义化 Toast（成功/错误/警告分色）、历史分页与筛选、历史详情人性化展示并保留原始 JSON 折叠区。

---

## 说明

- 演示模式下的优化解、置换比数值由内置引擎生成，用于交互演示；生产环境请连接真实后端获取严谨算法结果。
- ECharts 以按页懒加载方式引入；如需进一步压缩体积，可改为 `echarts/core` 按需注册所用图表与组件。
