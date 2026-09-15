# API 接口参考

> 产品：**煤粉数据库管理及配煤优化控制台**（仓库 `coal-database-blending-system-web`，当前版本 `v1.0.0`）

本文档描述后端 Flask JSON API 的全部对外端点。后端以 SQLAlchemy 持久化，默认使用 SQLite（`data/coal_system.db`），可用环境变量 `DATABASE_URL` 切换到其它数据库（如 MySQL via PyMySQL）；首次访问接口会自动建表并从 `data/test_coal_datas.csv` 播种。混煤优化采用 NSGA-II 多目标 Pareto 算法（成本 / 热值 / 质量风险），返回推荐解与 Pareto 候选集。

相关文档：[项目说明](../README.md) · [架构设计](./ARCHITECTURE.md) · [部署指南](./DEPLOYMENT.md) · [使用手册](./USER_GUIDE.md) · [前端说明](../frontend/README.md)

---

## 1. 基本约定

### 1.1 Base URL 与路由前缀

| 类别 | 前缀 | 说明 |
| --- | --- | --- |
| 业务接口 | `/api` | 所有煤种、优化、置换比、报表接口统一挂在 `/api` 下（在 `app/routes/__init__.py` 中通过 `url_prefix="/api"` 注册） |
| 健康检查 | 无前缀 | `GET /health`（`page_bp` 蓝图，无前缀） |
| 单页应用 | 无前缀 | 非 `/api` 路径由 SPA catch-all 路由托管 `frontend/dist`，history 回退 `index.html` |

本地开发默认 Base URL：`http://127.0.0.1:5000`（业务接口即 `http://127.0.0.1:5000/api`）。

### 1.2 内容类型约定

| 场景 | Content-Type |
| --- | --- |
| 普通请求体 | `application/json` |
| 文件上传（`POST /api/coals/upload`） | `multipart/form-data` |
| 导出 / 模板下载（Excel） | 响应 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`（二进制流，`Content-Disposition: attachment`） |

### 1.3 统一成功响应

所有 JSON 接口成功时都返回 `status: "success"`。业务数据依端点放在 `data`、`result` 或平铺的顶层字段中（各端点单独说明）。

```json
{
  "status": "success",
  "message": "可选说明",
  "data": {}
}
```

优化类接口成功时结果放在 `result`：

```json
{
  "status": "success",
  "message": "优化计算完成",
  "result": {}
}
```

### 1.4 统一失败响应

```json
{
  "status": "error",
  "message": "错误原因"
}
```

常见状态码：

| 状态码 | 含义 |
| --- | --- |
| `400` | 请求体为空、参数校验不通过、缺少上传文件 |
| `404` | 资源不存在（煤种 / 历史记录不存在，或未匹配到的 `/api/*` 路径） |
| `409` | 唯一约束冲突（煤种名称已存在） |
| `500` | 服务端异常 |

> 说明：全局错误处理器（`app/routes/errors.py`）对 `/api` 路径及 `Accept: application/json` 的请求返回 `{"status": "error", "message": ...}` 结构；`POST /api/optimization` 另有 `no_feasible_solution`、`search_failed` 等业务级 `status`（见 3.1）。浮点结果中的 `NaN`/`Inf` 会被后端统一序列化为 `null`。

---

## 2. 煤种管理

煤种数据表 `coal_data`，字段来自 `app/models/coal.py`。以下端点均以 `/api` 为前缀。

### 2.0 煤种字段字典

单条煤种（`to_dict()` / `coal_to_api_dict()`）返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 主键 |
| `name` | string | 煤种名称（唯一） |
| `type` | string | 煤种类型 |
| `price` | float | 价格（元/吨） |
| `calorific_value` | float | 热值（kcal/kg） |
| `ash_content` | float | 灰分（%） |
| `volatile_matter` | float | 挥发分（%） |
| `fixed_carbon` | float | 固定碳（%） |
| `total_sulfur` | float | 全硫（%） |
| `total_moisture` | float\|null | 全水分（%） |
| `air_dry_moisture` | float\|null | 空干基水分（%） |
| `moisture` | float\|null | 全水分别名（等于 `total_moisture`） |
| `mad` | float\|null | 空干基水分别名（等于 `air_dry_moisture`） |
| `supplier` | string\|null | 供应商 / 产地 |
| `hgi` | float\|null | 可磨性指数 HGI |
| `burnout_rate` | float\|null | 燃尽率（%） |
| `carbon_content` | float\|null | 含碳量 C（%） |
| `hydrogen_content` | float\|null | 含氢量 H（%） |
| `nitrogen_content` | float\|null | 含氮量 N（%） |
| `created_at` | string\|null | 创建时间（ISO 8601） |
| `updated_at` | string\|null | 更新时间（ISO 8601） |

### 2.1 获取煤种列表 `GET /api/coals`

支持分页、搜索与类型过滤。

请求 Query 参数：

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `page` | int | 否 | `1` | 页码，最小为 `1` |
| `page_size` | int | 否 | `10` | 每页数量；传 `0`（或负数）返回全部 |
| `search` | string | 否 | `""` | 对 `name` / `type` / `supplier` 模糊匹配（`ILIKE`） |
| `type` | string | 否 | `""` | 按煤种类型精确过滤 |

示例：

```http
GET /api/coals?page=1&page_size=10&search=烟煤&type=烟煤
```

成功响应（`data` 为煤种数组，字段见 2.0）：

```json
{
  "status": "success",
  "data": [ { "id": 1, "name": "示例煤种", "type": "烟煤" } ],
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total": 42,
    "total_pages": 5
  }
}
```

分页字段：`pagination.page`、`pagination.page_size`、`pagination.total`、`pagination.total_pages`（`page_size=0` 时 `total_pages` 为 `1`，无数据时为 `0`）。

### 2.2 获取单个煤种详情 `GET /api/coals/<coal_id>`

路径参数：`coal_id`（int，煤种主键）。

```http
GET /api/coals/1
```

成功响应：`{ "status": "success", "data": { ...煤种字段（见 2.0） } }`。
煤种不存在返回 `404`：`{ "status": "error", "message": "煤种不存在" }`。

### 2.3 获取煤种类型列表 `GET /api/coals/types`

无参数。返回库中去重且非空的煤种类型（按类型名升序）。

```json
{ "status": "success", "data": ["无烟煤", "烟煤", "贫煤"] }
```

### 2.4 新增煤种 `POST /api/coals`

请求体（`application/json`）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 煤种名称，唯一 |
| `type` | string | 是 | 煤种类型 |
| `price` | float | 是 | 价格（元/吨） |
| `calorific_value` | float | 是 | 热值（kcal/kg） |
| `ash_content` | float | 是 | 灰分（%） |
| `volatile_matter` | float | 是 | 挥发分（%） |
| `fixed_carbon` | float | 是 | 固定碳（%） |
| `total_sulfur` | float | 是 | 全硫（%） |
| `supplier` | string | 否 | 供应商 / 产地 |
| `total_moisture` / `moisture` | float | 否 | 全水分（%） |
| `air_dry_moisture` / `mad` | float | 否 | 空干基水分（%） |
| `hgi` | float | 否 | 可磨性指数 |
| `burnout_rate` | float | 否 | 燃尽率（%） |
| `carbon_content` | float | 否 | 含碳量 C（%） |
| `hydrogen_content` | float | 否 | 含氢量 H（%） |
| `nitrogen_content` | float | 否 | 含氮量 N（%） |

服务端校验规则（`validate_coal_data`）：

- 必填字段不得缺失或为空（`None` / `""`）。
- `price` 须 `> 0` 且 `<= 2000`。
- `calorific_value` 须在 `3000-8000`（kcal/kg）。
- `ash_content` 在 `0-50`（%）。
- `volatile_matter` 在 `0-50`（%）。
- `fixed_carbon` 在 `0-100`（%）。
- `total_sulfur` 在 `0-5`（%）。
- `ash_content + volatile_matter + fixed_carbon` 须接近 `100`（区间 `90-110`）。

请求体示例：

```json
{
  "name": "示例煤种",
  "type": "烟煤",
  "supplier": "山西",
  "price": 680,
  "calorific_value": 6100,
  "ash_content": 11.5,
  "volatile_matter": 24.2,
  "fixed_carbon": 63.1,
  "total_sulfur": 0.52,
  "moisture": 8.3,
  "mad": 1.6,
  "hgi": 62,
  "burnout_rate": 88,
  "carbon_content": 78.5,
  "hydrogen_content": 3.5,
  "nitrogen_content": 1.1
}
```

成功响应：

```json
{
  "status": "success",
  "message": "煤种添加成功",
  "coal_id": 12,
  "data": { "id": 12, "name": "示例煤种" }
}
```

错误响应：

| 状态码 | 场景 | message |
| --- | --- | --- |
| `400` | 请求体为空 | `请求数据为空` |
| `400` | 校验失败 | 以 `; ` 连接的错误列表 |
| `409` | 名称已存在 | `煤种名称已存在` |

### 2.5 更新煤种 `PUT /api/coals/<coal_id>`

路径参数：`coal_id`（int）。请求体字段与 2.4 相同，校验规则一致（`validate_coal_data` 同样要求上述字段齐全并满足数值区间）。

成功响应：`{ "status": "success", "message": "煤种更新成功", "data": { ...煤种字段 } }`。

错误响应：`404`（`煤种不存在`）、`409`（`煤种名称已存在`）、`400`（校验失败 / 请求为空）。

### 2.6 删除煤种 `DELETE /api/coals/<coal_id>`

路径参数：`coal_id`（int）。

成功响应：`{ "status": "success", "message": "煤种删除成功" }`。
煤种不存在返回 `404`：`{ "status": "error", "message": "煤种不存在" }`。

### 2.7 批量删除煤种 `POST /api/coals/batch_delete`

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `coal_ids` | int[] | 是 | 待删除的煤种 ID 数组，不可为空 |

```json
{ "coal_ids": [1, 2, 3] }
```

成功响应：`{ "status": "success", "message": "成功删除 3 条煤种记录" }`。
`coal_ids` 为空返回 `400`：`{ "status": "error", "message": "请选择要删除的煤种" }`。

### 2.8 上传煤种文件 `POST /api/coals/upload`

Content-Type：`multipart/form-data`。

| 表单字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | Excel（`.xlsx`）或 CSV 文件 |

服务端流程：保存文件 → 读取为 DataFrame → 校验列格式（`validate_coal_data_format`）→ 逐行导入（`update_existing=True`，按名称更新已有记录，不保留原始 ID）。

成功响应：

```json
{
  "status": "success",
  "message": "文件上传完成，新增 10 条，更新 2 条，跳过 0 条",
  "filename": "20260701_120000_uploaded.xlsx",
  "coal_count": 12,
  "created_count": 10,
  "updated_count": 2,
  "skipped_count": 0,
  "errors": []
}
```

| 字段 | 说明 |
| --- | --- |
| `filename` | 服务端保存后的文件名 |
| `coal_count` | 受影响记录数（新增 + 更新） |
| `created_count` / `updated_count` / `skipped_count` | 新增 / 更新 / 跳过数量 |
| `errors` | 问题行摘要（最多前 20 条）；有问题行时 `message` 追加前 5 条 |

错误响应：`400`（无 `file` 字段 → `没有文件部分`；文件格式 / 列校验失败 → `ValueError` 文案）、`500`（其它异常，`处理文件失败: ...`）。

### 2.9 导出煤种数据 `POST /api/coals/export`

请求体：

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `export_all` | bool | 否 | `false` | `true` 时导出全部煤种 |
| `coal_ids` | int[] | 否 | `[]` | 指定导出的煤种 ID；`export_all` 为 `false` 时必须非空 |

返回值：Excel 文件流（工作表 `煤种数据`），下载名形如 `煤种数据导出_YYYYMMDD_HHMMSS.xlsx`。导出列包含 `序号`、`煤种名称`、`煤种类型`、`供应商/产地`、`价格(元/吨)`、`热值(kcal/kg)`、`灰分(%)`、`挥发分(%)`、`固定碳(%)`、`全硫(%)`、`全水分(%)`、`空干基水分(%)`、`可磨性HGI`、`燃尽率(%)`、`含碳量C(%)`、`含氢量H(%)`、`含氮量N(%)`。

错误响应：`400`（既未选中也未 `export_all` → `没有选择要导出的数据`；无匹配数据 → `没有要导出的数据`）。

### 2.10 下载导入模板 `GET /api/coals/template`

无参数。返回 Excel 模板文件流，`Content-Disposition` 下载名 `煤种数据导入模板.xlsx`。

> 说明：当前 Web 前端在保存该模板时会改名为 `煤种导入模板.csv`（内容仍为 Excel），与此处的 `Content-Disposition` 名称不同；直接对接接口的集成方以本文件名为准。

---

## 3. 智能混煤优化

以下端点均以 `/api` 为前缀。核心算法为 NSGA-II 多目标 Pareto 优化，在硬约束可行域内同时权衡成本、热值与质量风险，返回推荐方案与 Pareto 候选集。

### 3.1 执行优化计算 `POST /api/optimization`

请求体顶层字段：

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `optimization_target` | string | 否 | `喷煤性价比最优` | 优化目标，见下表 |
| `selected_coal_ids` | int[] | 是 | — | 参与混配的煤种 ID，至少 2 种 |
| `constraints` | object | 否 | `{}` | 工艺约束，见「constraints 结构」 |
| `ga_params` | object | 否 | `{}` | 遗传/进化算法参数，见「ga_params 结构」 |

支持的 `optimization_target`：

| 取值 | 说明 |
| --- | --- |
| `喷煤性价比最优` | 兼容映射到多目标 Pareto |
| `最低成本` | 兼容映射到多目标 Pareto |
| `最高性价比` | 兼容映射到多目标 Pareto |
| `多目标Pareto最优` | 直接指定多目标 Pareto |

> `最佳性能` 已下线，若传入将返回 `400`（`当前版本仅支持多目标Pareto最优，最佳性能模式已下线`）；其它未知目标返回 `不支持的优化目标，请使用多目标Pareto最优`。

#### constraints 结构

| 字段 | 类型 | 必填 | 算法默认 | 说明 |
| --- | --- | --- | --- | --- |
| `heat_target` | float | 否 | `6800` | 兼容字段；当前多目标算法不使用该值，仅校验非负有限数。使用热值上下限表达约束 |
| `heat_min` / `heat_max` | float | 否 | `6000` / `7800` | 热值上下限 |
| `ash_min` / `ash_max` | float | 否 | `0.0` / `20.0` | 灰分上下限（%） |
| `volatile_min` / `volatile_max` | float | 否 | `8.0` / `40.0` | 挥发分上下限（%） |
| `fixed_carbon_min` / `fixed_carbon_max` | float | 否 | `50.0` / `85.0` | 固定碳上下限（%） |
| `sulfur_min` / `sulfur_max` | float | 否 | `0.0` / `1.2` | 全硫上下限（%） |
| `price_min` / `price_max` | float | 否 | `0` / `1500` | 价格上下限（元/吨） |
| `ratio_constraints` | object | 否 | `{}` | 单煤种配比约束，见下 |

> 缺省边界先使用上表默认值补齐，再校验 `min <= max`；单侧边界也必须为有限非负数。

**`ratio_constraints`**：键为煤种 ID 的字符串形式，值为 `{ "min": 百分数, "max": 百分数 }`（单位为百分比，`0-100`）。后端会除以 100 转为小数配比传入算法。未提供某煤种时，其 `min` 默认按 `0`、`max` 按 `100` 处理。

```json
"ratio_constraints": {
  "1": { "min": 10, "max": 60 },
  "2": { "min": 10, "max": 60 },
  "3": { "min": 10, "max": 60 }
}
```

#### ga_params 结构

| 字段 | 类型 | 默认 | 校验范围 | 说明 |
| --- | --- | --- | --- | --- |
| `population_size` | int | `500` | `1-2000` | 种群大小 |
| `max_generations` | int | `3000` | `1-10000` | 最大迭代代数 |
| `mutation_rate` | float | `0.2` | `0-1` | 变异率 |
| `crossover_rate` | float | `0.85` | `0-1` | 交叉率 |
| `tournament_size` | int | `7` | `>= 2`，且 `<= population_size` | 锦标赛规模 |
| `elite_ratio` | float | `0.1` | `0-1` | 精英保留比例 |
| `early_stopping_patience` | int | `200` | `1-10000` | 早停耐心值 |
| `constraint_penalty_factor` | float | `1500` | `>= 0` | 约束惩罚因子 |
| `parallel_workers` | int | `4` | `1-16` | 并行工作线程数 |
| `adaptive_mutation` | bool | `true` | — | 是否自适应变异 |
| `parallel_computing` | bool | `true` | — | 是否启用并行计算 |
| `diversity_factor` | float | `0.1` | `0-1` | 多样性因子 |

#### 关键校验规则（`validate_optimization_params`）

- `selected_coal_ids` 须为至少两个不同正整数的数组；兼容十进制整数字符串，规范化后检查重复。浮点、布尔、null、重复 ID 返回 `400`。
- 传入的煤种 ID 若在库中不存在，返回 `404`（`煤种不存在: [...]`）。
- 请求体、`constraints`、`ga_params`、`ratio_constraints` 须为对象；所有已知数值须有限，计数参数须为整数。非法输入返回 `400`。
- 各成对 `min/max` 约束须满足 `min <= max`，允许相等边界表达固定配方。
- 每个配比约束须满足 `0 <= min <= max <= 100`；拒绝未选煤种或规范化后重复的配比键。
- 未指定的已选煤种边界先补为 `0–100%`，再检查全部下限之和不超过 `100%`、上限之和不低于 `100%`。
- `ga_params` 各数值项须落在上表校验范围；`tournament_size` 不得大于 `population_size`。

#### 请求体示例

```json
{
  "optimization_target": "喷煤性价比最优",
  "selected_coal_ids": [1, 2, 3],
  "constraints": {
    "heat_target": 6000,
    "heat_min": 5800,
    "heat_max": 6500,
    "ash_min": 8,
    "ash_max": 18,
    "volatile_min": 15,
    "volatile_max": 35,
    "fixed_carbon_min": 55,
    "fixed_carbon_max": 75,
    "sulfur_min": 0.4,
    "sulfur_max": 0.8,
    "price_min": 450,
    "price_max": 800,
    "ratio_constraints": {
      "1": { "min": 10, "max": 60 },
      "2": { "min": 10, "max": 60 },
      "3": { "min": 10, "max": 60 }
    }
  },
  "ga_params": {
    "population_size": 500,
    "max_generations": 3000,
    "mutation_rate": 0.2,
    "crossover_rate": 0.85,
    "tournament_size": 7,
    "elite_ratio": 0.1,
    "early_stopping_patience": 200,
    "constraint_penalty_factor": 1500,
    "parallel_workers": 4,
    "adaptive_mutation": true,
    "parallel_computing": true,
    "diversity_factor": 0.1
  }
}
```

#### 成功响应

```json
{
  "status": "success",
  "message": "优化计算完成",
  "history_saved": true,
  "result": {
    "objective_type": "pci_pareto_nsga2_v1",
    "optimization_target": "多目标Pareto最优",
    "coal_names": ["煤A", "煤B", "煤C"],
    "optimal_ratios": [0.4, 0.35, 0.25],
    "blending_ratio": { "煤A": 0.4, "煤B": 0.35, "煤C": 0.25 },
    "total_price": 612.5,
    "total_heat": 6020,
    "total_ash": 11.8,
    "total_volatile": 23.4,
    "total_fixed_carbon": 64.1,
    "total_sulfur": 0.58,
    "performance_price_ratio": 9.83,
    "iterations": 186,
    "time_taken": 1.27,
    "fitness_value": 0.18,
    "quality_penalty": 0.18,
    "objective_values": { "cost": 612.5, "heat": 6020, "quality_penalty": 0.18 },
    "recommended_solution": {
      "solution_id": "pareto_001",
      "total_price": 612.5,
      "total_heat": 6020,
      "quality_penalty": 0.18,
      "optimal_ratios": [0.4, 0.35, 0.25],
      "objective_values": { "cost": 612.5, "heat": 6020, "quality_penalty": 0.18 }
    },
    "pareto_solutions": [
      {
        "solution_id": "pareto_001",
        "total_price": 612.5,
        "total_heat": 6020,
        "total_ash": 11.8,
        "total_sulfur": 0.58,
        "quality_penalty": 0.18,
        "optimal_ratios": [0.4, 0.35, 0.25]
      }
    ],
    "is_feasible": true,
    "constraints_satisfied": true,
    "constraint_violations": [],
    "violation_score": 0,
    "active_constraints": ["heat_min", "sulfur_max"],
    "diagnosis": [],
    "timestamp": "2026-07-01T12:00:00"
  }
}
```

`result` 字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `objective_type` | string | 目标类型，当前固定 `pci_pareto_nsga2_v1` |
| `optimization_target` | string | 实际采用的优化目标 |
| `coal_names` | string[] | 参与混配的煤种名称，顺序与 `optimal_ratios` 一致 |
| `optimal_ratios` | float[] | 推荐方案各煤种小数配比（总和约为 `1`） |
| `blending_ratio` | object | `{ 煤种名: 小数配比 }` |
| `total_price` / `total_heat` / `total_ash` / `total_volatile` / `total_fixed_carbon` / `total_sulfur` | float | 推荐方案的加权综合指标 |
| `performance_price_ratio` | float | 性价比指标 |
| `iterations` | int | 实际迭代代数 |
| `time_taken` | float | 计算耗时（秒） |
| `fitness_value` | float | 推荐方案质量风险值，越小越好 |
| `quality_penalty` | float | 质量惩罚 |
| `objective_values` | object | 目标值（成本 / 热值 / 质量惩罚等） |
| `recommended_solution` | object | 系统按归一化理想点距离选出的默认推荐方案 |
| `pareto_solutions` | object[] | 可行、非支配的 Pareto 候选方案集（每项含 `solution_id`、指标与 `optimal_ratios`） |
| `is_feasible` | bool | 是否满足全部工艺约束 |
| `constraints_satisfied` | bool | 同 `is_feasible` |
| `constraint_violations` | array | 约束违反明细 |
| `violation_score` | number | 违约度评分，越小越好 |
| `active_constraints` | string[] | 最终解贴边生效的关键约束 |
| `diagnosis` | array | 诊断信息 |
| `timestamp` | string | 结果生成时间（ISO 8601） |

顶层附加字段：

| 字段 | 说明 |
| --- | --- |
| `history_saved` | 是否成功写入优化历史表（`true`/`false`） |
| `warning` | 仅当历史保存失败时出现，提示需初始化/迁移数据库 |

#### 失败与业务状态

| status | 状态码 | 说明 |
| --- | --- | --- |
| `error` | `400` | 请求为空 / 参数校验失败 / `ValueError` |
| `error` | `404` | 传入的煤种不存在 |
| `error` | `500` | 服务端异常 |
| `no_feasible_solution` | `200` | 约束组合无可行解（算法侧返回） |
| `search_failed` | `200` | 存在可行域但本次搜索未找到可行解（算法侧返回） |

> 业务级状态（`no_feasible_solution` / `search_failed`）随算法结果透传，HTTP 状态码仍为 `200`，需读取响应体 `status` 判定。

### 3.2 获取优化历史列表 `GET /api/optimization/history`

无参数。按创建时间倒序返回全部历史记录（`to_summary_dict()`）。

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "timestamp": "2026-07-01T12:00:00",
      "date": "2026-07-01 12:00:05",
      "coal_names": ["煤A", "煤B"],
      "optimal_ratios": [0.6, 0.4],
      "ratio_items": [
        { "coal_name": "煤A", "ratio": 0.6, "ratio_percent": 60.0 },
        { "coal_name": "煤B", "ratio": 0.4, "ratio_percent": 40.0 }
      ],
      "total_price": 612.5,
      "total_heat": 6020,
      "total_ash": 11.8,
      "total_volatile": 23.4,
      "total_fixed_carbon": 64.1,
      "total_sulfur": 0.58,
      "performance_price_ratio": 9.83,
      "iterations": 186,
      "time_taken": 1.27,
      "fitness_value": 0.18,
      "constraints_satisfied": true
    }
  ]
}
```

### 3.3 获取优化历史详情 `GET /api/optimization/history/<history_id>`

路径参数：`history_id`（int，对应 `optimization_history` 表主键）。

成功响应在 3.2 摘要字段基础上追加（`to_detail_dict()`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `constraints` | object | 本次请求的约束条件 |
| `request_payload` | object | 原始请求体 |
| `result_payload` | object | 完整结果响应体（含 `result`） |

记录不存在返回 `404`：`{ "status": "error", "message": "历史记录不存在" }`。

---

## 4. 置换比计算

煤焦置换比历史表 `replacement_ratio_history`。以下端点均以 `/api` 为前缀。

### 4.1 理论置换比 `POST /api/calculate_theory_ratio`

请求体：

| 分组 | 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `coal_params` | `carbon_content` | float | 是 | `0.78` | 煤粉含碳（小数） |
| | `hydrogen_content` | float | 是 | `0.035` | 煤粉含氢（小数） |
| | `ash_content` | float | 是 | `0.12` | 煤粉灰分（小数） |
| | `sio2_content` | float | 否 | `0.48` | 煤粉 SiO₂（小数） |
| | `decomposition_heat` | float | 否 | `220.0` | 分解热 |
| | `physical_heat` | float | 否 | `450.0` | 物理热 |
| `coke_params` | `carbon_content` | float | 是 | `0.86` | 焦炭含碳（小数） |
| | `ash_content` | float | 是 | `0.11` | 焦炭灰分（小数） |
| | `sio2_content` | float | 否 | `0.52` | 焦炭 SiO₂（小数） |
| `blast_furnace_params` | `eta_co` | float | 否 | `0.4444` | CO 利用率 |
| | `slag_basicity` | float | 否 | `1.15` | 炉渣碱度 |
| | `slag_enthalpy` | float | 否 | `1800.0` | 渣焓 |
| | `wind_temperature` | float | 否 | `1180.0` | 风温 |
| | `hot_blast_enthalpy` | float | 否 | `1.5` | 热风焓 |

校验规则（`validate_replacement_ratio_params`）：`coal_params` 的 `carbon_content`、`hydrogen_content`、`ash_content` 与 `coke_params` 的 `carbon_content`、`ash_content` 必填且须为正数。

请求体示例：

```json
{
  "coal_params": {
    "carbon_content": 0.78,
    "hydrogen_content": 0.035,
    "ash_content": 0.12,
    "sio2_content": 0.48,
    "decomposition_heat": 220.0,
    "physical_heat": 450.0
  },
  "coke_params": {
    "carbon_content": 0.86,
    "ash_content": 0.11,
    "sio2_content": 0.52
  },
  "blast_furnace_params": {
    "eta_co": 0.4444,
    "slag_basicity": 1.15,
    "slag_enthalpy": 1800.0,
    "wind_temperature": 1180.0,
    "hot_blast_enthalpy": 1.5
  }
}
```

成功响应：

```json
{
  "status": "success",
  "ratio": 0.8523,
  "details": {
    "煤粉含碳量": 0.78,
    "煤粉中氢参加还原而节约的碳量": 1.32,
    "煤粉中灰分造渣所消耗的碳": 0.21,
    "煤粉分解热和加热至1500°C物理热所消耗的碳": 0.65,
    "焦炭含碳量": 0.86,
    "焦炭中灰分造渣所消耗的碳": 0.19,
    "置换比分子": 78.46,
    "置换比分母": 85.02,
    "理论置换比": 0.8523
  },
  "carbon_burning_heat": 9797.0,
  "hydrogen_saving_carbon": 1.32,
  "decomposition_heat_consumption": 152.3,
  "physical_heat_consumption": 450.0,
  "hydrogen_replacement_heat": 62222
}
```

顶层字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ratio` | float | 理论置换比 |
| `details` | object | 计算明细，中文键见上（`煤粉含碳量`、`煤粉中氢参加还原而节约的碳量`、`煤粉中灰分造渣所消耗的碳`、`煤粉分解热和加热至1500°C物理热所消耗的碳`、`焦炭含碳量`、`焦炭中灰分造渣所消耗的碳`、`置换比分子`、`置换比分母`、`理论置换比`） |
| `carbon_burning_heat` | float | 碳燃烧净有效热量（kJ/kg） |
| `hydrogen_saving_carbon` | float | 氢节约碳量百分比 |
| `decomposition_heat_consumption` | float | 分解热消耗（kcal/kg） |
| `physical_heat_consumption` | float | 物理热消耗（等于 `coal_params.physical_heat`） |
| `hydrogen_replacement_heat` | int | 氢直接还原替代热（`62222` kJ/kg，常量） |

计算完成后写入置换比历史（`calculation_type=theory`，`calculation_mode=theory`）。校验失败返回 `400`；异常返回 `500`（`计算失败: ...`）。

### 4.2 实际置换比 `POST /api/calculate_actual_ratio`

请求体：

| 分组 | 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 顶层 | `enable_advanced` | bool | 否 | `false` | `true` 走高级（含高炉状态修正）计算 |
| `production_data` | `initial_coke_ratio` | float | 否 | `400.0` | 调整前焦比（kg/t） |
| | `final_coke_ratio` | float | 否 | `370.0` | 调整后焦比（kg/t） |
| | `initial_coal_ratio` | float | 否 | `150.0` | 调整前煤比（kg/t） |
| | `final_coal_ratio` | float | 否 | `180.0` | 调整后煤比（kg/t） |
| | `adjustment_factor` | float | 否 | `2.5` | 基础修正系数（kg/t） |
| | `iron_output_change` | float | 否 | `0.0` | 铁水产量变化（t/d，仅高级） |
| | `slag_ratio_change` | float | 否 | `0.0` | 渣比变化（kg/t，仅高级） |
| | `carbon_efficiency_change` | float | 否 | `0.0` | 碳利用效率变化（%，仅高级） |

> 该接口不执行 `validate_replacement_ratio_params`，仅要求请求体非空；煤比变化量（`final_coal_ratio - initial_coal_ratio`）为 0 会触发计算异常（分母为零）。

请求体示例：

```json
{
  "enable_advanced": true,
  "production_data": {
    "initial_coke_ratio": 400,
    "final_coke_ratio": 370,
    "initial_coal_ratio": 150,
    "final_coal_ratio": 180,
    "adjustment_factor": 2.5,
    "iron_output_change": 0,
    "slag_ratio_change": 0,
    "carbon_efficiency_change": 0
  }
}
```

成功响应：

```json
{
  "status": "success",
  "ratio": 1.0833,
  "details": { },
  "calculation_type": "advanced"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ratio` | float | 实际置换比 |
| `details` | object | 计算明细，中文键，随模式不同 |
| `calculation_type` | string | `basic` 或 `advanced` |

`details` 中文键（基础模式，`enable_advanced=false`）：`调整前焦比(kg/t)`、`调整后焦比(kg/t)`、`调整前煤比(kg/t)`、`调整后煤比(kg/t)`、`焦比减少量(kg/t)`、`煤比增加量(kg/t)`、`修正系数(kg/t)`、`实际置换比`。

高级模式（`enable_advanced=true`）在上述基础键之上追加：`铁水产量变化(t/d)`、`铁水产量修正项`、`渣比变化(kg/t)`、`渣比修正项`、`碳利用效率变化(%)`、`碳效率修正项`、`总修正量`、`修正后实际置换比`。

计算完成后写入置换比历史（`calculation_type=actual`，`calculation_mode` 为 `basic` 或 `advanced`）。请求为空返回 `400`；异常返回 `500`（`计算失败: ...`）。

### 4.3 置换比历史列表 `GET /api/replacement_ratio/history`

无参数。按创建时间倒序返回全部历史（`to_summary_dict()`）。

```json
{
  "status": "success",
  "data": [
    {
      "id": 1,
      "date": "2026-07-01 12:00:05",
      "calculation_type": "theory",
      "calculation_mode": "theory",
      "ratio_value": 0.8523,
      "parameter_summary": "煤粉含碳 78.00%，焦炭含碳 86.00%，煤气利用率 0.4444"
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `date` | 创建时间（`YYYY-MM-DD HH:MM:SS`） |
| `calculation_type` | `theory` 或 `actual` |
| `calculation_mode` | `theory` / `basic` / `advanced` |
| `ratio_value` | 置换比数值 |
| `parameter_summary` | 参数摘要（理论：煤/焦含碳与煤气利用率；实际：焦比、煤比变化与模式） |

### 4.4 置换比历史详情 `GET /api/replacement_ratio/history/<history_id>`

路径参数：`history_id`（int，对应 `replacement_ratio_history` 表主键）。

成功响应在 4.3 摘要字段基础上追加（`to_detail_dict()`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `request_payload` | object | 原始请求体 |
| `result_payload` | object | 完整结果响应体 |

记录不存在返回 `404`：`{ "status": "error", "message": "历史记录不存在" }`。

---

## 5. 报表导出

以下端点均以 `/api` 为前缀。除失败时返回 JSON 错误外，成功均返回 Excel 二进制流。

### 5.1 导出历史优化报告 `GET /api/optimization/export/<history_id>`

路径参数：`history_id`（int，对应 `optimization_history` 表主键）。

服务端取历史详情的 `result_payload` 作为报告数据（若缺 `constraints` 则回填历史约束），生成 A4 排版 Excel 报告并作为附件返回。

优化记录不存在返回 `404`：`{ "status": "error", "message": "优化记录不存在" }`；生成失败返回 `500`。

### 5.2 导出当前优化结果报告 `POST /api/optimization/export/current`

请求体：直接传入当前优化结果对象，**至少包含 `result`**；可附带 `constraints`（用户设置的约束，用于报表展示）。

```json
{
  "result": { "coal_names": ["煤A", "煤B"], "optimal_ratios": [0.6, 0.4] },
  "constraints": { "heat_target": 6000 }
}
```

返回值：A4 排版 Excel 报告（附件）。缺少 `result` 返回 `400`：`{ "status": "error", "message": "没有优化结果数据" }`；生成失败返回 `500`。

### 5.3 导出置换比结果报告 `POST /api/replacement_ratio/export`

请求体（用于填充 Excel 表格，均可选）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `calculation_type` | string | 计算类型（写入报告） |
| `result` | any | 计算结果（写入报告） |
| `timestamp` | string | 计算时间（写入报告） |
| `details` | object | 计算明细，逐行写入「参数名称 / 数值」 |

返回值：Excel 文件流，下载名 `置换比计算结果_YYYYMMDD_HHMMSS.xlsx`。请求为空返回 `400`（`请求数据为空`）；生成失败返回 `500`。

---

## 6. 健康检查

### 6.1 `GET /health`

无前缀、无参数。用于探活与基本状态查询。

```json
{
  "status": "ok",
  "app": "coal-database-blending-system-web",
  "storage_mode": "sqlite",
  "coal_count": 42
}
```

| 字段 | 说明 |
| --- | --- |
| `status` | 固定 `ok` |
| `app` | 应用名（`APP_NAME`） |
| `storage_mode` | 数据存储模式（`DATA_STORAGE_MODE`，默认 `sqlite`） |
| `coal_count` | 当前煤种记录数 |

---

## 7. 调用建议

- **先取煤种再优化**：执行智能混煤前，先调用 `GET /api/coals` 拿到煤种列表与 `id`，再把选中的 `id` 传入 `POST /api/optimization` 的 `selected_coal_ids`。
- **配比约束用百分数**：`ratio_constraints` 的 `min`/`max` 以百分比（`0-100`）传入，后端会转为小数；请自查「下限之和 ≤ 100、上限之和 ≥ 100」，否则会被校验拦截。
- **区分 HTTP 状态与业务状态**：`POST /api/optimization` 的 `no_feasible_solution` / `search_failed` 仍是 `200`，务必读取响应体 `status` 判定，不能只看 HTTP 码。
- **历史与报表**：展示历史推荐方案优先读 `GET /api/optimization/history`；导出报表时，当前结果走 `POST /api/optimization/export/current`（请求体带 `result`），历史记录走 `GET /api/optimization/export/<history_id>`。
- **置换比参数独立于煤种库**：置换比接口的参数为独立计算参数，不依赖煤种主表；计算成功会自动写入置换比历史，供 `GET /api/replacement_ratio/history` 与详情接口查询。
- **导出为二进制流**：所有导出/模板接口成功返回 Excel 附件（`Content-Disposition: attachment`），失败才返回 JSON；前端需按 `blob` 处理响应。
- **健康探活**：容器 / 反向代理健康检查建议访问 `GET /health`（无 `/api` 前缀）。

---

相关文档：[项目说明](../README.md) · [架构设计](./ARCHITECTURE.md) · [部署指南](./DEPLOYMENT.md) · [使用手册](./USER_GUIDE.md) · [前端说明](../frontend/README.md)
