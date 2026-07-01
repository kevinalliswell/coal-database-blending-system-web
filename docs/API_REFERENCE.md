# API 接口说明

本文档整理当前项目已注册并对外提供的后端接口，统一以 `/api` 为前缀。当前默认数据模式为 SQLite/SQLAlchemy：煤种 CRUD、智能混煤读取和优化历史都使用同一份数据库。CSV/Excel 仅作为导入、导出和首次种子初始化的数据格式。

## 1. 基本约定

- Base URL：`http://127.0.0.1:5000/api`
- 请求体格式：默认使用 `application/json`
- 文件上传：使用 `multipart/form-data`
- 导出接口：返回 Excel 二进制流

### 统一成功响应

```json
{
  "status": "success",
  "message": "可选",
  "data": {},
  "result": {}
}
```

### 统一失败响应

```json
{
  "status": "error",
  "message": "错误原因"
}
```

## 2. 煤种管理

### 2.1 获取煤种列表

- 方法：`GET`
- 路径：`/coals`
- Query 参数：
  - `page`：页码，默认 `1`
  - `page_size`：每页数量，默认 `10`，传 `0` 表示返回全部
  - `search`：按煤种名称/煤种类型模糊搜索
  - `type`：按煤种类型过滤

示例：

```http
GET /api/coals?page=1&page_size=10&search=烟煤&type=烟煤
```

响应字段：

- `data`：煤种列表
- `pagination.page`
- `pagination.page_size`
- `pagination.total`
- `pagination.total_pages`

单条煤种主要字段：

- `id`
- `name`
- `type`
- `supplier`
- `price`
- `calorific_value`
- `ash_content`
- `volatile_matter`
- `fixed_carbon`
- `total_sulfur`
- `moisture`
- `mad`
- `hgi`
- `burnout_rate`
- `carbon_content`
- `hydrogen_content`
- `nitrogen_content`

### 2.2 获取单个煤种详情

- 方法：`GET`
- 路径：`/coals/{coal_id}`

示例：

```http
GET /api/coals/1
```

### 2.3 新增煤种

- 方法：`POST`
- 路径：`/coals`

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

必填字段：

- `name`
- `type`
- `price`
- `calorific_value`
- `ash_content`
- `volatile_matter`
- `fixed_carbon`
- `total_sulfur`

### 2.4 更新煤种

- 方法：`PUT`
- 路径：`/coals/{coal_id}`
- 说明：仅更新请求体中出现的字段

### 2.5 删除煤种

- 方法：`DELETE`
- 路径：`/coals/{coal_id}`

### 2.6 批量删除煤种

- 方法：`POST`
- 路径：`/coals/batch_delete`

请求体示例：

```json
{
  "coal_ids": [1, 2, 3]
}
```

### 2.7 上传煤种文件

- 方法：`POST`
- 路径：`/coals/upload`
- Content-Type：`multipart/form-data`
- 表单字段：
  - `file`：Excel 或 CSV 文件

成功响应示例：

```json
{
  "status": "success",
  "message": "文件上传完成：新增 10 条，更新 2 条，跳过 0 条",
  "filename": "uploaded.xlsx",
  "coal_count": 12,
  "created_count": 10,
  "updated_count": 2,
  "skipped_count": 0,
  "errors": []
}
```

### 2.8 导出煤种数据

- 方法：`POST`
- 路径：`/coals/export`

请求体示例：

```json
{
  "coal_ids": [1, 2, 3],
  "export_all": false
}
```

返回值：Excel 文件流

### 2.9 下载导入模板

- 方法：`GET`
- 路径：`/coals/template`

返回值：Excel 模板文件流

## 3. 智能混煤优化

### 3.1 执行优化计算

- 方法：`POST`
- 路径：`/optimization`
- 说明：当前版本使用 NSGA-II 做多目标 Pareto 优化，在硬约束可行域内同时考虑成本、热值和质量风险，并返回推荐方案与 Pareto 候选方案集。

支持的 `optimization_target`：

- `喷煤性价比最优`
- `最低成本`
- `最高性价比`
- `多目标Pareto最优`

说明：

- `喷煤性价比最优`、`最低成本` 与 `最高性价比` 会兼容映射到 `多目标Pareto最优`
- `最佳性能` 已下线，请勿再传

请求体示例：

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

关键校验规则：

- `selected_coal_ids` 至少选择两种煤
- 各类 `min/max` 必须满足 `min < max`
- `heat_target` 必须位于 `heat_min` 与 `heat_max` 之间
- 单煤种配比约束取值范围为 `0-100`
- 所有煤种配比下限总和不能超过 `100`
- 所有煤种配比上限总和不能低于 `100`

成功响应示例：

```json
{
  "status": "success",
  "message": "优化计算完成",
  "result": {
    "objective_type": "pci_pareto_nsga2_v1",
    "optimization_target": "多目标Pareto最优",
    "coal_names": ["煤A", "煤B", "煤C"],
    "optimal_ratios": [0.4, 0.35, 0.25],
    "blending_ratio": {
      "煤A": 0.4,
      "煤B": 0.35,
      "煤C": 0.25
    },
    "total_price": 612.5,
    "total_heat": 6020,
    "total_ash": 11.8,
    "total_volatile": 23.4,
    "total_fixed_carbon": 64.1,
    "total_sulfur": 0.58,
    "iterations": 186,
    "time_taken": 1.27,
    "fitness_value": 0.18,
    "quality_penalty": 0.18,
    "objective_values": {
      "cost": 612.5,
      "heat": 6020,
      "quality_penalty": 0.18
    },
    "recommended_solution": {
      "solution_id": "pareto_001",
      "total_price": 612.5,
      "total_heat": 6020,
      "quality_penalty": 0.18,
      "optimal_ratios": [0.4, 0.35, 0.25],
      "objective_values": {
        "cost": 612.5,
        "heat": 6020,
        "quality_penalty": 0.18
      }
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
    "timestamp": "2026-04-24T12:00:00"
  }
}
```

结果字段说明：

- `objective_type`：当前固定为 `pci_pareto_nsga2_v1`
- `optimal_ratios`：按 `coal_names` 顺序返回的小数配比，总和为 `1`
- `recommended_solution`：系统按归一化理想点距离选出的默认推荐方案
- `pareto_solutions`：最多 20 个可行、非支配的 Pareto 候选方案
- `fitness_value`：推荐方案的质量风险值，越小越好
- `is_feasible`：是否满足全部工艺约束
- `constraint_violations`：约束违反明细
- `violation_score`：违约度评分，越小越好
- `active_constraints`：最终解中贴边生效的关键约束

典型失败状态：

- `status=error`：请求参数错误或服务异常
- `status=no_feasible_solution`：约束组合无可行解
- `status=search_failed`：存在可行域，但当前搜索未找到可行解

### 3.2 获取优化历史列表

- 方法：`GET`
- 路径：`/optimization/history`

返回字段：

- `id`
- `date`
- `coal_names`
- `optimal_ratios`
- `total_price`
- `total_heat`
- `objective_type`
- `is_feasible`

### 3.3 获取优化历史详情

- 方法：`GET`
- 路径：`/optimization/history/{history_id}`

说明：`history_id` 对应 SQLite `optimization_history` 表中的记录 `id`。

## 4. 置换比计算

### 4.1 理论置换比

- 方法：`POST`
- 路径：`/calculate_theory_ratio`

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

响应字段：

- `ratio`
- `details`
- `carbon_burning_heat`
- `hydrogen_saving_carbon`
- `decomposition_heat_consumption`
- `physical_heat_consumption`
- `hydrogen_replacement_heat`

### 4.2 实际置换比

- 方法：`POST`
- 路径：`/calculate_actual_ratio`

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

响应字段：

- `ratio`
- `details`
- `calculation_type`：`basic` 或 `advanced`

### 4.3 置换比历史

- 方法：`GET`
- 路径：`/replacement_ratio/history`
- 说明：返回 SQLite `replacement_ratio_history` 表中的理论置换比和实际置换比历史记录。

返回字段：

- `id`
- `date`
- `calculation_type`：`theory` 或 `actual`
- `calculation_mode`：`theory`、`basic` 或 `advanced`
- `ratio_value`
- `parameter_summary`

### 4.4 获取置换比历史详情

- 方法：`GET`
- 路径：`/replacement_ratio/history/{history_id}`
- 说明：`history_id` 对应 SQLite `replacement_ratio_history` 表中的记录 `id`。

返回字段：

- 历史摘要字段
- `request_payload`
- `result_payload`

## 5. 报表导出

### 5.1 导出历史优化报告

- 方法：`GET`
- 路径：`/optimization/export/{history_id}`
- 返回值：A4 排版 Excel 报告

### 5.2 导出当前优化结果报告

- 方法：`POST`
- 路径：`/optimization/export/current`
- 说明：请求体需直接传入当前优化结果对象，至少包含 `result`
- 返回值：A4 排版 Excel 报告

### 5.3 导出置换比结果报告

- 方法：`POST`
- 路径：`/replacement_ratio/export`
- 返回值：Excel 文件流

## 6. 调用建议

- 前端执行智能混煤前，先调用 `/coals` 获取煤种列表与 `id`
- 若需要展示历史推荐方案，优先读取 `/optimization/history`
- 若要导出报表，当前优化结果直接走 `/optimization/export/current`，历史记录走 `/optimization/export/{history_id}`
- 置换比接口中的参数为计算参数，不依赖煤种库主表；计算完成后会写入置换比历史表，供历史页面和详情接口查询
