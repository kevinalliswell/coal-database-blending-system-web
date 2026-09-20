# 批次化验与导入接口（2.0）

煤种主档沿用 `coal_data.id`，每个煤种可有多个到货批次，每个批次可保存多份化验修订。新增修订不更新旧报告；归档煤种或批次会停止其计算资格，原始记录和旧历史仍可读取。空化验 `{}`、部分指标与未知元信息均可保存；计算资格由当前设置和具体公式所需字段决定，不提供绕过资格检查的模式。

## 存储接口

- `GET/POST /api/catalog`：煤种主档；新增 `{name,type,supplier?}`。
- `PATCH /api/catalog/<id>`：修改名称、类型、供应商或 `archived`。
- `GET/POST /api/catalog/<id>/batches`：批次；新增 `{code,supplier?,received_at?}`，编号在同一煤种内唯一。
- `PATCH /api/batches/<id>`：仅修改 `archived`。
- `GET/POST /api/batches/<id>/assays`：修订；新增 `{raw,report_number?,sampled_at?,notes?}`。
- `GET /api/assays`：平铺修订，包含稳定 ID、煤种/批次 ID、修订号、原值、两类计算资格和换算过程。
- `POST /api/assays/preview`：`{raw}`，只校验并计算资格，不保存。

列表支持 `page`、`page_size`（0 表示全部，非零最多 2000）；主档、批次和平铺修订列表默认排除归档项，`include_archived=true` 可查看归档。平铺列表另支持 `coal_id`、`batch_id`。响应为 `{status:"success",data:...}`；400 为输入错误，404 为不存在，409 为身份/修订冲突。

## 导入：预览后提交

1. `POST /api/catalog/import/preview`：上传 multipart `file`（CSV/XLSX），或 JSON `{text}` 粘贴逗号/制表符表格。每次最多 10 MB、2000 行、128 列；XLSX 仅支持一个数据工作表。
2. 可附加 `mapping`、`metric_metadata`、`confirmed_headers`。multipart 中三者均为 JSON 字符串。
3. 预览返回表头、推荐映射、每行原值和问题、计算资格。缺项不妨碍保存；非法数值、日期、身份冲突、未确认的歧义列或缺失元信息会阻止整批提交。
4. 修正映射或填写元信息后重新预览。只在 `can_commit=true` 时返回 30 分钟有效的 `preview_token`。
5. `POST /api/catalog/import/commit` 仅接受 `{preview_token}`。服务器使用自己的预览快照，校验当前用户、有效期、一次性状态和目标修订是否变化，事务内整批追加。

映射示例：

```json
{
  "text": "煤种名称,煤种类型,批次编号,灰分\n样煤,烟煤,B001,12.5\n",
  "mapping": {"灰分": "ash_content.value"},
  "metric_metadata": {"ash_content": {"unit": "%", "basis": "d"}},
  "confirmed_headers": ["灰分"]
}
```

目标字段为 `coal_name,type,batch_code,supplier,received_at,report_number,sampled_at,notes` 和 `<metric>.value/.unit/.basis`；另有 `calorific_value.heat_type` 与 `hydrogen_content.hydrogen_includes_moisture`。忽略列需映射为 `null`；多个列不能映射到同一目标。`metric_metadata` 只填单位和定义，逐行明确给出的元信息优先。确认保留缺失元信息后，值仍标记 `unknown`，不会猜测基准。

已有煤种名称或批次编号会复用该身份并新增修订，不覆盖旧记录。同名煤种类型冲突、已有批次供应商/日期不一致或已归档时需先处理。导入来源行中的 ID/修订号等追溯列不用于指定数据库主键。

## 模板与完整原值导出

`GET /api/catalog/template?format=xlsx|csv` 下载空模板；`GET /api/catalog/export?format=xlsx|csv` 导出所有修订（默认包括归档，可用 `include_archived=false`）。每个指标的原值、单位、基准、热值/氢定义都有独立列，同时包含煤种、批次、报告编号、采样日期与备注。XLSX 文本单元格按文本写入，报告内容不会成为公式。

导出的追溯信息包括原修订 ID、修订号、来源、创建时间与归档状态。重新导入会追加新修订；它不是数据库备份恢复。数据库迁移前备份负责完整身份与历史恢复。

CSV 为防止电子表格执行以 `= + - @` 等开头的用户文字，所有文本单元格统一增加一个单引号前缀，并以 `csv_text_encoding=apostrophe-v1` 明确标记。系统重导入时只对带此标记的行移除恰好一个前缀，原文字中的单引号也能无损恢复；普通外部 CSV 不做此解码。第三方程序解析系统 CSV 时须遵循该标记，或使用保持原文本单元格的 XLSX。

## 旧数据与种子

迁移 `e3b8c52da10f` 为每个旧煤种建立“历史迁入”批次与首份修订，原数字不重算，旧主键和旧列保留。旧有 `gr/net` 未明确恒容/恒压，保留为未知热值定义；采样与收货日期不由系统创建日期推测。新装示例数据同样保持未知元信息，由幂等补录函数建立批次。

旧写入接口返回 410 与 `api_upgrade_required`。该迁移无法把多批次、多修订无损降为一行煤质，降级必须恢复升级前备份。
