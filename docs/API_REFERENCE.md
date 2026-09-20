# CBOS 2.0 API 参考

所有 `/api` 业务接口需要登录。返回 `{status:"success",data:...}`；登录会话接口的 `user/csrf_token/setup_required/desktop_mode` 在顶层。错误返回 `{status:"error",code,message}`，部分数据错误附 `issues:[{field,code,message,...}]`。JSON 不接受 NaN/Infinity。

## 认证与权限

1. `GET /api/auth/session` 获取会话与 CSRF token。
2. `POST /api/auth/login` 提交 `{username,password}`；使用同一 cookie jar，并发送 `X-CSRF-Token`。
3. 登录会旋转 token，后续写请求使用登录响应中的新 token。
4. `POST /api/auth/logout` 退出；`PUT /api/auth/password` 提交 `{current_password,password}`，撤销所有会话。

浏览器读请求也发送已加载会话的 X-CSRF-Token，用于发现其他标签页改变共享 cookie 后的身份变化；携带该头的业务 GET 会核对会话，未携带该头的既有只读 API 客户端仍兼容。GET /api/auth/session 可刷新过期的 token。退出会轮转为无权限匿名 cookie，使多个标签页复用同一登录前会话；每次用户点击登录/初始化后，先读取当前 token，再只提交一次凭据。登录失败保留表单与错误供手动重试；业务请求收到 csrf_failed 后刷新会话，不能自动重放写请求。标签页间只传随机变更通知，不在 localStorage 保存 token。

Web 不开放首管理员 HTTP 初始化；使用服务器 CLI。桌面 `POST /api/auth/setup` 还要求主进程认证过的本机传输。

`GET/POST /api/users` 查看/创建，创建字段为 username、display_name、role、password；`PATCH /api/users/{id}` 修改 display_name/role/active；`PUT /api/users/{id}/password` 管理员重置。角色为 admin/data_manager/calculator/viewer。

读接口需要 read，导出需要 export，写煤质需要 data_write，计算需要 calculate，用户/设置修改需要 admin。401 表示需要登录；403 表示权限或 CSRF 失败。前端按钮限制不能代替后端权限。

## 主档、批次与化验

| 路径 | 方法 | 内容 |
| --- | --- | --- |
| /api/catalog | GET / POST | 获取主档（含批次与最新修订）/ 新建 `{name,type,supplier?}` |
| /api/catalog/{id} | PATCH | 改元数据或 `{archived:true}` |
| /api/catalog/{id}/batches | GET / POST | 批次列表 / 新建 `{code,supplier?,received_at?}` |
| /api/batches/{id} | PATCH | 归档批次 |
| /api/batches/{id}/assays | GET / POST | 历次修订 / 新增 `{raw,report_number?,sampled_at?,notes?}` |
| /api/assays | GET | 平铺所有修订及功能准入 |
| /api/assays/preview | POST | `{raw}` 的换算与准入预览 |
| /api/catalog/import/preview | POST | 文件或粘贴文本预览 |
| /api/catalog/import/commit | POST | `{preview_token}` 一次性提交 |
| /api/catalog/template | GET | `?format=csv` 或 `xlsx` 模板 |
| /api/catalog/test-data | GET | `?format=csv` 或 `xlsx` 六煤合成测试表；需 read 权限，仅下载，不写库 |
| /api/catalog/export | GET | 同模板导出，包含全部修订 |

catalog、batches、assays 列表默认排除归档，可用 `include_archived=true` 查看；`page_size=0` 表示全部。导出默认保留全部历史修订（含归档），可显式指定 `include_archived=false`。

单项 raw 示例：`"ash_content":{"value":12,"unit":"%","basis":"d"}`。
热值示例：`"calorific_value":{"value":26,"unit":"MJ/kg","basis":"ar","heat_type":"net_v"}`。
氢附 `hydrogen_includes_moisture:false/true/null`。完整支持字段见煤质基准契约。

`GET /api/assays` 除 data/pagination 外，顶层返回 `settings_version`，对应本次所有化验采用值共同使用的设置快照。客户端应与正在显示的口径版本核对；不一致时重新获取设置并确认，不能将新口径数值放入旧口径页面。

导入预览接受 multipart `file`，或 JSON `text`；另支持 `mapping:{源列:目标路径|null}`、`metric_metadata:{指标:{unit,basis,heat_type?...}}`、`confirmed_headers:[源列]`。目标路径如 `coal_name`、`batch_code`、`ash_content.value`。返回 headers/mapping/rows/issues/can_commit/preview_token/expires_at。提交时用户、有效期和批次版本均再次校验。

## 混煤优化

`POST /api/optimization`：

```json
{
  "settings_version": 1,
  "components": [
    {"assay_revision_id": 10, "min_ratio": 10, "max_ratio": 80},
    {"assay_revision_id": 11, "min_ratio": 20, "max_ratio": 90}
  ],
  "constraints": {"heat_min": 6000, "heat_max": 7500, "sulfur_max": 1.0},
  "ga_params": {"population_size": 100, "max_generations": 200, "tournament_size": 4, "random_seed": 42}
}
```

先通过 GET /api/settings 获取实际版本，替换例子的修订 ID。比例使用百分数；热值约束及结果热值统一 kcal/kg，其他煤质为质量百分数，成本为元/所选基准吨。页面显示单位换算不能改变 API 数值单位。

只通过 components 提供比例边界。旧 selected_coal_ids / calculation_mode / ratio_basis 请求被拒绝，不自动挑选最新批次。每批次只允许一份修订。

成功返回 result（recommended_solution/pareto_solutions 等）及 input_snapshot。快照 schema_version=2，含 assays/raw/eligibility、algorithm_coals、settings、operator、formula_version。200 状态下还可能有 no_feasible_solution 或 search_failed，请检查 status；只有成功计算写入历史。

错误包括 409 settings_changed、422 data_conflict、422 assay_not_eligible（详情中的 issue 区分 missing/conversion_dependency/conflict 等）、404 record_not_found、400 invalid_request。

`GET /api/optimization/history` 和 `/{id}` 读历史。`POST /api/optimization/export/current` 导出已完成响应；`GET /api/optimization/export/{id}` 导出历史。报告以结果快照为准。

两类计算历史的 `date` 字段：SQLite `CURRENT_TIMESTAMP` 产生的 UTC 时间序列化为带 `Z` 的 ISO 时间；已有明确时区的值保留其偏移。其他数据库未记录时区的旧值保持 `YYYY-MM-DD HH:mm:ss`，表示时间口径未声明，客户端不得猜作 UTC 或本地时间。界面仅对带 `Z` / 偏移的值转换为浏览器本地时间并计算“几分钟前”；无时区值按原始绝对时间显示。此规则只改变响应，不改写历史存储或结果快照。

## 置换比

### 理论置换比

`POST /api/calculate_theory_ratio` 使用不可变化验修订及显式炉况输入。例子仅说明结构，数值需要用本厂有来源的数据替换：

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
  "parameter_source": "本厂模型参数记录编号"
}
```

煤 C/H/A 从该修订换算为干基，灰中 SiO₂ 保持灰分基；客户端不能覆盖这些组分。缺少相关字段或换算依赖时返回 422，归档记录不可用于新计算。coal_params 只接受上述两个显式热耗及必填 heat_unit=kJ/kg，热耗均按 kg 干煤计。焦炭 C/A 和灰中 SiO₂、ηCO 均为 0–1 分数；焦炭必须声明干基。炉渣热焓单位为 kJ/kg，鼓风热焓为 kJ/m³，风温为 ℃；体积与其余热参数须采用该经验模型的同一口径。

如果没有鼓风热焓，可显式设置 `allow_hot_blast_estimate:true`，在 blast_furnace_params 提供 wind_temperature 并省略 hot_blast_enthalpy，采用现有经验式 `1.3 × 风温`。两者不能同时提供；估算来源和模型常量保存于快照，这不等于现场校准。缺省不启用估算。

响应含 ratio（kg 干焦/kg 干煤）、details、decomposition_heat_consumption、physical_heat_consumption、total_heat_consumption、`heat_consumption_unit:"kJ/kg"`、effective_hot_blast_enthalpy、hot_blast_enthalpy_source（provided/temperature_estimate）、input_snapshot。热耗从输入 kJ/kg 除以 4.1868 传入内部 kcal_IT/kg 模型，并以同一系数转回 kJ/kg；1 kcal_IT=4.1868 kJ。

### 实际置换比

`POST /api/calculate_actual_ratio`：

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

四项煤焦比为同一质量基准下的 kg/t 铁，均必填且非负。mass_basis 必须为 ar 或 d；需指定高炉及不同的前后期间。`correction_mode:"none"` 明确表示不修正，不能另传 K。`provided` 模式在 production_data 增加 adjustment_factor（K，kg/t 铁，可正可负），并在顶层提供非空 correction_source。计算式为 `(前焦比 − 后焦比 + K) / (后煤比 − 前煤比)`；煤比变化不能为零。不从炉况变化自动推算 K，旧 enable_advanced 等隐式修正请求被拒绝。

两类计算均校验 settings_version，过期返回 409 settings_changed。`GET /api/replacement_ratio/history` 和 `/{id}` 返回保存的请求、结果和来源快照。schema_version=2 的 input_snapshot 包含原始请求/raw、normalized 采用值和单位、settings、actor、conversion_trace；理论计算还保存 assay 修订与模型常量。旧历史保持原样，不补造缺失数据。完整边界见 [置换比 2.0 契约](REPLACEMENT_V2.md)。

## 设置与版本

`GET/PUT /api/settings`：version、system_name、organization、ratio_basis(ar/d)、heat_type(net_v/gr_v)、heat_unit(MJ/kg/kcal/kg)、constraints、ga_params。PUT 提交当前 version；改变基准或热值类型还需 constraints_confirmed=true 和完整约束。并发冲突返回409，不覆盖别人设置。

`GET /api/system/info` 返回统一版本、完整构建提交、构建时间、运行方式、存储方式。

## 旧接口

旧 `/api/coals` 读取及导出用于兼容；原写/导入/删除接口返回410 api_upgrade_required。旧历史不强行升级为拥有完整输入的新快照。集成系统需要按批次修订重新接入。
