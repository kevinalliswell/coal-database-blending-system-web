# 2.0 置换比输入与追溯

理论与实际置换比仍使用 `/api/calculate_theory_ratio`、`/api/calculate_actual_ratio`。两者须登录、有 calculate 权限、提供 CSRF 和当前 `settings_version`；旧请求不会自动套用示例值。历史保留旧结果的原始定义。

## 理论计算

```json
{
  "assay_revision_id": 7,
  "settings_version": 1,
  "coal_params": {
    "decomposition_heat": 921.096,
    "physical_heat": 1884.06,
    "heat_unit": "kJ/kg"
  },
  "coke_params": {
    "analysis_basis": "d",
    "carbon_content": 0.86,
    "ash_content": 0.11,
    "sio2_content": 0.52
  },
  "blast_furnace_params": {
    "eta_co": 0.4444,
    "slag_basicity": 1.15,
    "slag_enthalpy": 1800,
    "hot_blast_enthalpy": 1534
  },
  "allow_hot_blast_estimate": false,
  "parameter_source": "焦炭报告与高炉运行记录编号"
}
```

这些数字仅说明接口单位，页面不会默认填入。煤粉 C/H/A/灰中 SiO₂ 由服务器读取所选不可修改的化验修订，完成独立准入和干基换算；客户端不能覆盖。归档煤种/批次、缺失或无效修订不能计算。

焦炭 C/A 使用干基质量分数；SiO₂ 为灰质量分数。网页显示百分数，提交除以100。CO 利用率页面也显示百分数。理论模型统一干基；管理员选择的混煤 ar/d 不会悄悄改变理论置换比定义。

煤粉分解热、物理热必须显式提供 **kJ/kg 干煤**。API返回 `decomposition_heat_consumption`、`physical_heat_consumption`、`total_heat_consumption` 也为 kJ/kg，并附 `heat_consumption_unit`。内核保留 kcal_IT/kg 存储形式，路由除以4.1868、耗碳公式乘以同一4.1868，保证真实输入热量不变。之前未说明卡定义的4.184已统一；旧历史不重算。

热焓有两种互斥来源：

- 提供 `hot_blast_enthalpy`，单位 kJ/m³；未用的风温可以不填，不套用默认风温。
- 显式 `allow_hot_blast_estimate=true`，且提供 `wind_temperature`（°C），本次采用既有工程式 `1.3×T`。不提供热焓或不勾选估算时不会自动计算。

响应和快照记录 `hot_blast_enthalpy_source=provided|temperature_estimate` 及实际使用值。用户提供的数值不被系统宣称为实验室认证数据。

该模型仍是简化碳氢热平衡模型，保留既有热反应常数、风量1.2 m³/kg碳和氢利用率关系。它们作为模型版本/假设保存，不能视为缺失的现场测量值。化验准入与守恒测试不构成高炉性能验证。

## 实际计算

```json
{
  "settings_version": 1,
  "mass_basis": "d",
  "furnace_id": "BF-1",
  "period_before": "2026-09-01/2026-09-07",
  "period_after": "2026-09-08/2026-09-14",
  "correction_mode": "none",
  "production_data": {
    "initial_coke_ratio": 400,
    "final_coke_ratio": 370,
    "initial_coal_ratio": 150,
    "final_coal_ratio": 180
  }
}
```

四项观测均必填，单位 kg/t铁水。煤和焦炭必须明确共同质量基准 ar 或 d，使用同一高炉、铁水统计定义和可比较的前后期间。ar 结果包含水分影响，不冒充干基。煤比变化为零返回400；有符号的减少/增加按所填数据如实计算。

未修正模式定义为 `(焦比前−焦比后)/(煤比后−煤比前)`。此处 K=0 是公式模式，不是给缺失测量值赋零。选择 `correction_mode=provided` 时，必须提供 `production_data.adjustment_factor`（可正可负，kg/t铁水）和 `correction_source`；使用 `(Δ焦比+K)/Δ煤比`。

原 enable_advanced 模式已关闭：不再调用写死的产量/渣比/碳效率修正权重。为兼容历史分类字段，显式提供修正项的记录 `calculation_type/calculation_mode` 仍为 advanced，同时保存无歧义的 `correction_mode=provided`。

## 快照与失败行为

两类成功计算均返回并持久化 `input_snapshot.schema_version=2`，含原始请求、raw、normalized、系统设置及版本、操作者、时间。理论另含煤/批次/修订身份、换算过程、模型单位与常数；历史无需读取当前化验来重建当时结果。

缺项、NaN/Infinity、布尔数值、错误单位、过期设置、无效分母或不有限结果不会产生成功历史记录。输入字段是独立数值而不是字符串；UI空白保持缺失，不转换为0。成功后编辑任一输入会清除当前结果，下一次计算产生新快照。
