# 煤质基准与筛选模式

本版本区分输入一致性校验与真实化验/生产验证。界面或 API 中的 `verified` **仅表示输入基准一致且通过数值检查**，不代表实验室认证、燃烧性能或高炉运行已经验证。

## 煤种字段

| 字段 | 值 | 含义 |
|---|---|---|
| `analysis_basis` | `unknown` / `ad` / `ar` / `d` | 灰分、挥发分、固定碳、全硫共同基准 |
| `calorific_basis` | 同上 | 热值质量基准 |
| `price_basis` | 同上 | 每吨价格对应的煤质量基准 |
| `calorific_type` | `unknown` / `gr` / `net` | 未确认 / 高位热值 / 低位热值 |

`d` 为干煤质量；`ad` 为空干分析样质量；`ar` 为收到煤质量。此版本不支持 `daf` 输入，也不做任何基准换算。不得将干基配比直接视为湿煤现场投料比例；需要湿煤投料时，先据真实水分和化验记录统一为收基输入。本版本也不把高位热值转为低位热值。

空白基准保存为 `unknown`。旧数据及原始演示种子全部保持原有化验数值，迁移不会从煤名、残余量或水分猜测基准，不自动归一化。字段可以逐项补充；只有全部输入满足下述要求才可正式计算。

### 数值与闭合检查

所有必选和可选数值必须有限；导入和手工编辑使用同一校验。已声明 `analysis_basis` 时检查：

- `d`：A + V + FC = 100%。
- `ad`：A + V + FC + Mad = 100%，必须提供空干基水分。
- `ar`：A + V + FC + Mt = 100%，必须提供全水分。

允许偏差为 **0.5 个百分点**，是本应用的输入质控容差，不是对标准试验精密度的引用或保证。全硫和元素碳不再额外相加到上述工业分析闭合式。基准 `unknown` 不执行完整闭合认证，只拒绝超过 100% 的明显不可能固体组分总和及其他非法数值。

导入/导出增加 `工业分析基准`、`热值基准`、`热值类型`、`计价基准` 四列，也接受对应英文 API 字段名作为服务层列别名。模板中的 `unknown` 必须根据真实记录填写，不得为通过校验而随意选择 `d`。

## 优化请求：有意的兼容性变化

`POST /api/optimization` 新增顶层字段：

| 字段 | 默认 | 规则 |
|---|---|---|
| `calculation_mode` | `verified` | `verified` 正式输入校验，或显式 `screening` 筛选试算 |
| `ratio_basis` | `unknown` | `verified` 必须明确 `ad` / `ar` / `d`；`screening` 可为 `unknown` |

正式计算要求所有煤的 `analysis_basis`、`calorific_basis`、`price_basis` 与 `ratio_basis` 完全一致，且热值类型已知并相同。任何一项缺失返回 HTTP 400，错误会列出缺失字段。已知混基准或高低位热值混用，在筛选模式也拒绝。

旧接口调用若没有新模式字段，默认正式校验，含 `unknown` 的旧数据会被拒绝。为保留演示或待确认数据试算，调用方必须显式加入：

```json
{"calculation_mode": "screening", "ratio_basis": "unknown"}
```

以上字段与原有选煤、约束及算法参数一起提交。筛选结果仅展示原始数值下的数学候选，不得作为生产投料依据。

结果增加 `result.data_validation`，随结果快照写入历史：

```json
{
  "status": "unverified",
  "ratio_basis": "unknown",
  "scope": "screening_only",
  "warnings": ["筛选试算：配比与指标未完成正式基准校验，不能作为生产投料依据。"]
}
```

正式校验通过时 `status=verified`、`scope=input_consistency_only`。`is_feasible` 与 `constraints_satisfied` **始终只表示当前数学约束满足**；不代替 `data_validation`，更不构成制粉、燃尽或高炉验证。历史缺少此字段的结果应显示未确认。

## 数据库升级

先备份数据库，按项目既有迁移流程运行 `python -m flask --app run.py db upgrade`，再启动新版本。新修订 `c8a1d24f5e67` 在煤表新增四个非空字符串列，旧行均填 `unknown`，不改任何已有化验、价格、水分或时间字段。

如果数据库历史上由 `db.create_all()` 创建、没有 Alembic 版本记录，先确认其表结构完整匹配上一修订 `b3f7b0d5f1a2`，再执行 `python -m flask --app run.py db stamp b3f7b0d5f1a2` 后升级。不能直接对未知结构盲目 stamp。`create_all()` 只创建新表，不会给旧表补列；部署必须执行迁移。

回归测试覆盖新数据库升级、旧修订含原样旧数据的升级、三类基准闭合、混基准拒绝、筛选明确标记、编辑与导入导出元数据往返。
