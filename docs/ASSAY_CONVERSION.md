# 化验输入、换算与计算准入

## 边界与接口

`app.services.assay_conversion` 是无数据库副作用的纯转换服务：

- `validate_raw_assay(raw)` 返回新字典，允许不完整资料；错误数值、字段名、单位或无意义的基准组合抛出 `ValueError`。
- `evaluate_assay(raw, settings)` 返回独立的 `blending`、`theory`，各含 `eligible`、`issues`、`values`、`trace`。每项 issue 为 `{field, code, message}`；trace 是可读字符串数组。
- `eligible` 只表示当前计算功能的输入依赖和一致性检查通过，不表示化验认证或生产试验验证。调用方必须检查 eligible，不能因 values 中已有部分值就计算。
- 原始值不会被覆盖；没有审批或 screening 绕过。一次调用的数据必须属于明确的同批次/样品化验版本，不从其他批次补字段。

每个指标结构为 `{value, unit, basis}`。热值另含 `heat_type`，氢另含 `hydrogen_includes_moisture`。缺值/null 省略；缺单位或基准记为 unknown，不猜测。只接受有限 JSON 数字，不接受布尔值或数值字符串；导入层先解析数值。百分数使用 0–100，水分小于 100；HGI 非负且可大于 100。

| 指标 | 支持的明确基准 | 单位 |
|---|---|---|
| 灰分 A | ar/ad/d | % |
| V、FC、全硫、元素 C/H/N | ar/ad/d/daf | % |
| Mt / Mad | ar / ad | % |
| 热值 | ar/ad/d/daf | MJ/kg、kJ/kg、kcal/kg |
| 价格 | ar/d | CNY/t |
| SiO₂ | ash（灰质量基准） | % |
| HGI、燃尽率 | 无质量基准换算，basis=unknown | index、% |

所有指标允许 unknown 存档，但需要该字段的计算会被阻断。热值允许 gr_v、net_v、net_p、unknown 存档；仅明确的恒容 gr_v/net_v 可参加热值计算。

## 默认计算口径

默认 settings 为 `ratio_basis=ar, heat_type=net_v, heat_unit=MJ/kg`。管理员可选择 d 或 gr_v。heat_unit 仅影响显示；blending.values.calorific_value **始终是 kcal/kg**，供现有算法与约束接口使用。价格与六项指标均投影到同一目标质量基准；配比上下限也应解释为该质量基准下的比例。

内部先转换到干基，再投影到 ar/d。热值在此过程保留自身高/低位定义，只有目标定义改变才要求氢。干基、高位且价格与全部工业分析已为干基的数据，不需要为了计算而补 Mt、Mad 或 H。

## 换算公式

下面 M、A、H、X 都是百分数；例如 10 表示 10%，不是 0.1。换算假设同一样品的干物质没有损失或化学变化。

### 工业分析

```text
X_d = X_ad / (1 − Mad/100)
X_d = X_ar / (1 − Mt/100)
X_d = X_daf × (1 − A_d/100)
X_ar = X_d × (1 − Mt/100)
```

Mt 和 Mad 不互代；A_daf 不作为灰分输入。daf 转换需要 A_d<100，不把缺失灰分视为零。干基的零水分是换算定义，不能生成该批实煤的 Mt=0。

缺 FC 时允许 `FC_d=100−A_d−V_d` 标准差减，并标注派生来源；投影到 ar 等价于 `FC_ar=100−Mt−A_ar−V_ar`。不减全硫，不用 FC 代替元素 C。已有 FC 不被重算或覆盖。

完整工业分析在统一干基检查 `A_d+V_d+FC_d=100±0.5` 个百分点。这是本应用输入质控容差，不是标准方法精密度。采用固定干基检查，避免管理员切换目标基准改变同一原始资料的闭合状态。容差内保留原值，不归一化至 100%。

全部工业指标都是 ar，但缺 Mt 时，质量加权本身虽可写出，却无法完成本应用要求的闭合检查，因此不准入。不能倒推 Mt 绕过缺项。

### 热值：GB/T 213-2008 恒容路径

热值先统一为 kJ/kg（数值等于 J/g）：1 MJ/kg=1000 kJ/kg；1 kcal/kg=4.1868 kJ/kg。

```text
Qnet,v,d = Qgr,v,d − 206 × H_d
Qnet,v,b = Qnet,v,d × (1 − M_b/100) − 23 × M_b
Qnet,v,d = (Qnet,v,b + 23 × M_b) / (1 − M_b/100)
Qgr,v,d = Qnet,v,d + 206 × H_d
```

其中 b 为 ar/ad，M_b 对应 Mt/Mad。干基 M=0。gross 换基直接使用干物质比例；net 换基必须包含水的汽化热修正。**同属 net_v 的换基不需要 H。** daf 的高位或低位输入按无灰干物质比例恢复到 d；仍需 A_d。

H 必须排除水中氢。湿基氢需要显式声明是否包含水中氢；若包含，先计算 `H_excluding_water=H_reported−0.1119×M`，再按该水分换基；已经排除的氢不重复扣除。d/daf 定义不含水，故不要求该布尔声明。不推算缺失 H，也不用经验公式补热值。

例：Qgr,v,d=32000 kJ/kg、H_d=4%、Mt=10%，则 Qnet,v,d=31176、Qnet,v,ar=27828.4 kJ/kg。已提供后一数值时，恢复 net_v,d 只需要 Mt；恢复 gr_v,d 才需要 H。

net_p 及未明确恒容/恒压的低位只存档；不得按 net_v 解释。本版本固定 GB 公式系数 206 和 23，不混用其他标准版本的 23.05 或恒压系数。

### 价格、质量与混配

```text
P_d = P_ar / (1 − Mt/100)
P_ar = P_d × (1 − Mt/100)
wet_fraction_i = [dry_fraction_i/(1 − Mt_i/100)]
                 / Σ[dry_fraction_j/(1 − Mt_j/100)]
```

这只是每收到吨/干吨的质量单位换算，不包含税费、运费、热值结算扣罚或干燥成本。价格为元/收到吨且缺 Mt 时，不能用于干基价格归一。

同一 ar + net_v 口径下，热值和价格可按收到煤湿质量比例加权；水分不同的煤不能把干质量比例直接当作湿质量比例。该判断假设混合过程没有额外失水、加水或反应。工业分析线性混配是应用采用的预测模型，不等同于混后实际化验验证；不延伸到 HGI、灰熔点、燃尽率。

## 分功能依赖

混煤要求：可统一的 A、V、FC（可差减）、全硫、热值、价格，以及完成闭合和所选转换所需的水分/灰分/氢信息。缺少某一输入不阻止存档，issues 给出不能计算的字段。

理论置换比煤样部分只要求 C_d、H_d、A_d、灰中 SiO₂；values 输出百分数，路由在传旧模型前除以 100。缺煤价、热值、V 或 FC 不阻断理论输入。C+H+A 不得超过 100 加质控容差；这不是完整元素分析闭合证明。焦炭、炉况、热耗及模型适用性由理论计算入口独立验证。

混合灰中 SiO₂ 应使用 `Σ(w_i A_i SiO2_i)/Σ(w_i A_i)`，不能按煤比例直接平均。HGI、燃尽率只存档，不参与当前准入依赖或线性预测。

## 依据与验证边界

- [GB/T 35985-2018《煤炭分析结果基的换算》](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=7DB3CA5E901291F3FABDE8B0B33A16F8)：官方记录确认现行；采标版权原因不提供全文。
- [GB/T 213-2008《煤的发热量测定方法》](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=8FF3EA84987B3B87C3A2E5922D41AC2D)：官方记录确认现行，全文同样受限。
- [WRI/中电联《GHG Protocol 中国燃煤电厂指南》印刷页73、注释40](https://ghgprotocol.org/sites/default/files/GHGP%E4%B8%AD%E5%9B%BD%E7%87%83%E7%85%A4%E7%94%B5%E5%8E%82%E8%AE%A1%E7%AE%97%E5%B7%A5%E5%85%B7%E6%8C%87%E5%8D%97_guidance_tool_Chinese_power_plants_June2013_final_2_0.pdf#page=80)：明确引用 GB 热值式及 206/23 系数。
- [SGS Coal Calculations](https://www.sgs.com/en/services/coal-calculations)：湿基/干基/daf 换算因子、氢定义和单位换算；其 ISO 热值式与 GB 版本系数有差异，不能混用。
- [ASTM D7582-15 §5.6](https://store.astm.org/d7582-15.html)：固定碳差减的定义，各项必须处于相同水分基准；此处仅引用该定义，不宣称采用这个历史版本进行化验。

自动测试检验数学换算、双向恢复、缺项阻断、异常值和质量/热量守恒，不构成原始化验真实性、混煤燃烧性能或高炉生产效果的验证。
