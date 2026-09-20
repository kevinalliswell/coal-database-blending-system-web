type ObjectValue = Record<string, unknown>;
const object = (value: unknown): ObjectValue => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as ObjectValue : {};
const shown = (value: unknown) => value === null || value === undefined || value === '' ? '未记录' : String(value);
const basisLabels: Record<string, string> = { ar: '收到基 ar', d: '干基 d', ad: '空干基 ad', daf: '干燥无灰基 daf', ash: '灰分基 ash' };
const heatLabels: Record<string, string> = { net_v: '恒容低位 Qnet,v', gr_v: '恒容高位 Qgr,v', net_p: '恒压低位 Qnet,p' };
const metricLabels: Record<string, string> = {
  ash_content: '灰分 A', volatile_matter: '挥发分 V', fixed_carbon: '固定碳 FC', total_sulfur: '全硫 S',
  calorific_value: '热值 Q', price: '价格', total_moisture: '全水 Mt', air_dry_moisture: '空干水 Mad',
  carbon_content: '元素碳 C', hydrogen_content: '元素氢 H', nitrogen_content: '元素氮 N',
  sio2_content: '灰中 SiO₂', hgi: 'HGI', burnout_rate: '燃尽率',
};

/** Interpret only the completed run's payload. Never supplement history with current settings or assays. */
export function historyProvenance(payload: unknown) {
  const envelope = object(payload);
  const result = Object.keys(object(envelope.result)).length ? object(envelope.result) : envelope;
  const snapshot = object(envelope.input_snapshot);
  const validation = object(result.data_validation);
  const basisCode = String(snapshot.ratio_basis || validation.ratio_basis || 'unknown');
  const basis = basisLabels[basisCode] ?? '未记录';
  const heat = heatLabels[String(snapshot.heat_type)] ?? '未记录';
  const price = ({ ar: '元/收到吨', d: '元/干吨', ad: '元/空干吨' } as Record<string, string>)[basisCode] ?? '未记录';
  const operator = object(snapshot.operator || snapshot.actor);
  const operatorLabel = [operator.display_name, operator.username, operator.role].filter(Boolean).join(' / ') || '未记录';
  const units = snapshot.schema_version === 2 ? 'kcal_IT/kg（1 kcal_IT = 4.1868 kJ）' : 'kcal/kg（旧记录卡定义未记录）';
  const metadata: [string, string][] = [
    ['配比质量基准', basis], ['热值定义', heat], ['热值数值单位', units], ['计价口径', price],
    ['公式版本', shown(snapshot.formula_version)], ['设置版本', shown(object(snapshot.settings).version)], ['操作者', operatorLabel],
  ];
  const assays = (Array.isArray(snapshot.assays) ? snapshot.assays : []).map((value) => {
    const assay = object(value);
    const raw = object(assay.raw);
    const eligibility = object(object(assay.eligibility).blending);
    const adopted = object(eligibility.values);
    const rows = [...new Set([...Object.keys(raw), ...Object.keys(adopted)])].map((field) => {
      const item = object(raw[field]);
      const hasRaw = item.value !== undefined && item.value !== null;
      const hasAdopted = adopted[field] !== undefined && adopted[field] !== null;
      const definition = field === 'hydrogen_content'
        ? item.hydrogen_includes_moisture === true ? '包含水中氢' : item.hydrogen_includes_moisture === false ? '不含水中氢' : '水中氢定义未记录'
        : field === 'calorific_value' ? heatLabels[String(item.heat_type)] ?? '热值定义未记录' : '';
      return {
        field, label: metricLabels[field] ?? field, rawValue: hasRaw ? shown(item.value) : '未提供',
        rawDefinition: hasRaw ? [shown(item.unit), basisLabels[String(item.basis)] ?? '基准未记录', definition].filter(Boolean).join(' · ') : '',
        adoptedValue: hasAdopted ? shown(adopted[field]) : '本功能未采用',
        adoptedDefinition: hasAdopted ? `${field === 'calorific_value' ? 'kcal_IT/kg' : field === 'price' ? 'CNY/t' : '%'} · ${basis}` : '',
        source: hasRaw ? '原值换算/直接采用' : field === 'fixed_carbon' && hasAdopted ? '标准差减派生' : '未记录',
      };
    });
    return {
      id: shown(assay.id), label: shown(assay.label || assay.id), report: shown(assay.report_number),
      sampledAt: shown(assay.sampled_at), rows,
      trace: Array.isArray(eligibility.trace) ? eligibility.trace.map(String) : [],
    };
  });
  return { basis, heat, price, units, metadata, assays };
}
