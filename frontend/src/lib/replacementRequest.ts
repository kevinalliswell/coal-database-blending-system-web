import type { Assay, Settings } from './v2';

export type ReplacementFields = Record<string, string>;

function number(values: ReplacementFields, field: string, label: string, maximum?: number, signed = false) {
  const raw = values[field];
  if (raw === undefined || raw.trim() === '') throw new Error(`${label}为必填项`);
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`${label}必须为有限数值`);
  if ((!signed && value < 0) || (maximum !== undefined && value > maximum)) throw new Error(`${label}超出允许范围`);
  return value;
}

function text(values: ReplacementFields, field: string, label: string) {
  const value = values[field]?.trim();
  if (!value) throw new Error(`请填写${label}`);
  return value;
}

function version(settings: Pick<Settings, 'version'> | undefined) {
  if (!settings) throw new Error('系统设置尚未加载，请刷新后重试');
  return settings.version;
}

export function buildTheoryRequest(values: ReplacementFields, assay: Assay | undefined, settings: Pick<Settings, 'version'> | undefined, allowEstimate: boolean) {
  const settingsVersion = version(settings);
  if (!assay) throw new Error('请选择煤种批次化验修订');
  if (assay.archived || !assay.eligibility.theory.eligible) throw new Error(`该化验不能用于理论置换比：${assay.eligibility.theory.issues.map(i => i.message).join('；')}`);
  const coal_params = {
    heat_unit: 'kJ/kg' as const,
    decomposition_heat: number(values, 'coal_decomp', '煤粉分解热'),
    physical_heat: number(values, 'coal_physical', '煤粉物理热'),
  };
  const coke_params = {
    analysis_basis: 'd' as const,
    carbon_content: number(values, 'coke_carbon', '焦炭干基元素碳', 100) / 100,
    ash_content: number(values, 'coke_ash', '焦炭干基灰分', 100) / 100,
    sio2_content: number(values, 'coke_sio2', '焦炭灰中 SiO₂', 100) / 100,
  };
  if (coke_params.carbon_content <= 0 || coke_params.carbon_content + coke_params.ash_content > 1.005) throw new Error('焦炭碳须大于零，且干基 C+A 不得超过 100% 加质控容差');
  const slag_basicity = number(values, 'slag_basicity', '炉渣碱度');
  if (slag_basicity <= 0) throw new Error('炉渣碱度必须大于零');
  const blast_furnace_params = {
    eta_co: number(values, 'eta_co', '煤气利用率', 100) / 100,
    slag_basicity,
    slag_enthalpy: number(values, 'slag_enthalpy', '炉渣热焓'),
    ...(allowEstimate
      ? { wind_temperature: number(values, 'wind_temp', '风温') }
      : { hot_blast_enthalpy: number(values, 'hot_blast', '鼓风热焓') }),
  };
  return { assay_revision_id: assay.id, settings_version: settingsVersion, coal_params, coke_params,
    blast_furnace_params, allow_hot_blast_estimate: allowEstimate,
    parameter_source: values.parameter_source?.trim() || '' };
}

export function buildActualRequest(values: ReplacementFields, settings: Pick<Settings, 'version'> | undefined, corrected: boolean) {
  const settingsVersion = version(settings);
  if (!['ar', 'd'].includes(values.mass_basis)) throw new Error('请选择煤与焦炭耗量的共同质量基准');
  const furnace_id = text(values, 'furnace_id', '高炉编号');
  const period_before = text(values, 'period_before', '调整前统计期间');
  const period_after = text(values, 'period_after', '调整后统计期间');
  if (period_before === period_after) throw new Error('调整前后的统计期间须不同');
  const production_data = {
    initial_coke_ratio: number(values, 'initial_coke', '调整前焦比'),
    final_coke_ratio: number(values, 'final_coke', '调整后焦比'),
    initial_coal_ratio: number(values, 'initial_coal', '调整前煤比'),
    final_coal_ratio: number(values, 'final_coal', '调整后煤比'),
    ...(corrected ? { adjustment_factor: number(values, 'adjustment', '修正量 K', undefined, true) } : {}),
  };
  if (production_data.initial_coal_ratio === production_data.final_coal_ratio) throw new Error('煤比变化不能为零');
  return { settings_version: settingsVersion, mass_basis: values.mass_basis, furnace_id, period_before, period_after,
    production_data, correction_mode: corrected ? 'provided' : 'none',
    ...(corrected ? { correction_source: text(values, 'correction_source', '修正来源') } : {}) };
}
