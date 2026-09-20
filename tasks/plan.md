# CBOS 2.0 implementation

Approved scope: raw per-metric assay bases; batch/revision records; automatic normalization with per-function eligibility; no screening bypass; four roles; settings/help/about; shared Web/offline desktop; docs/changelog; gated v2.0.0 release, Windows and Docker assets from one immutable SHA.

## Shared contracts (implementation coordination)
- Raw assay is a JSON dictionary keyed by existing metric names: ash_content, volatile_matter, fixed_carbon, total_sulfur, calorific_value, total_moisture, air_dry_moisture, price, carbon_content, hydrogen_content, nitrogen_content, sio2_content, hgi, burnout_rate.
- Each supplied metric is {value: number|null, unit: string, basis: unknown|ar|ad|d|daf|ash}; calorific_value additionally heat_type: unknown|gr_v|net_v|net_p; hydrogen_content additionally hydrogen_includes_moisture: boolean|null. Water units %, heat units MJ/kg|kJ/kg|kcal/kg, price CNY/t. Empty metric is absent/null. No guessed metadata.
- app/services/assay_conversion.py exposes validate_raw_assay(raw) -> normalized raw (ValueError for malformed/invalid numbers) and evaluate_assay(raw, settings) -> {blending:{eligible,issues,values,trace},theory:{eligible,issues,values,trace}}. Issues are {field,code,message}; trace entries are readable formula/source details. values use legacy canonical field names and algorithm heat unit kcal/kg. Settings include ratio_basis (ar default or d), heat_type (net_v default or gr_v), heat_unit (MJ/kg default or kcal/kg).
- Settings REST GET/PUT /api/settings -> {status:success,data:{version,system_name,organization,ratio_basis,heat_type,heat_unit,constraints,ga_params}}. Changing basis/type requires constraints_confirmed:true plus constraints. Constraint heat numbers are consistently kcal/kg at API/kernel boundary; UI converts display only.
- Authentication endpoints /api/auth/session (public bootstrap status, csrf_token, user|null, setup_required, desktop_mode); /api/auth/setup POST; /api/auth/login POST; /api/auth/logout POST; /api/auth/password PUT. User has id,username,display_name,role,active,permissions. Roles admin,data_manager,calculator,viewer. Permissions read,export,data_write,calculate,admin.
- /api/users GET/POST, /api/users/<id> PATCH (role,active,display_name), /api/users/<id>/password PUT. /api/system/info version/build/mode.
- V2 catalog separate endpoints /api/catalog GET/POST; /api/catalog/<coal_id> PATCH (metadata/archive); /api/catalog/<coal_id>/batches GET/POST; /api/batches/<batch_id>/assays GET/POST; /api/batches/<batch_id> PATCH archive. Assay revisions immutable. POST assays {raw,report_number,sampled_at,notes}; batch {code,supplier,received_at}. Catalog data includes batches and latest assay in batch for list UI.
- GET /api/assays returns flat revisions with id,coal_id,batch_id,revision,coal_name,batch_code,label,raw,eligibility,archived. POST /api/assays/preview evaluates raw only.
- V2 optimization still POST /api/optimization: components:[{assay_revision_id,min_ratio,max_ratio}],settings_version,constraints,ga_params. No old coal ID fallback. Result uses existing shape with input_snapshot schema_version2 and per-revision IDs as coal IDs, unique coal/batch labels.
- Existing legacy tests must migrate to approved new behavior rather than production TESTING/auth bypasses. Specialized algorithm unit tests remain valid.

## Work ownership
- formula_science: conversion service, conversion tests, conversion specification doc only.
- api_ui_review: auth/settings backend + desktop protocol session integration + own migration + tests, initializer hook (coordinate registration).
- ga_review: catalog models/services/routes/import + own migration + tests, legacy Coal nullable/archive adaptations. Do not touch auth/app factory registration or frontend.
- root: release guard, integration registrations, optimization/replacement endpoints, frontend, shared docs/version/release pipeline and final review.

## Deliverable order
1. Disable automatic main releases before feature merges; merge verified desktop foundation.
2. Conversion + catalog + auth vertical slices with tests and corresponding docs.
3. Integrate calculation/UI; migrations and snapshot compatibility; full smoke tests.
4. Docs and CHANGELOG, prepare 2.0.0 version, review/merge PRs.
5. Same-SHA Linux/Docker/Windows build and validation, annotated tag/draft Release/assets/digest checks, publish and promote latest, download verification.
