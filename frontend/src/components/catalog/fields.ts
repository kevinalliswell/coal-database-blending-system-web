import type { RawAssay, RawMetric } from '../../lib/v2';

export interface MetricField { key: string; label: string; units: string[]; bases: RawMetric['basis'][] }
const qualityBases: RawMetric['basis'][] = ['unknown', 'ar', 'ad', 'd', 'daf'];
export const metricFields: MetricField[] = [
  { key: 'ash_content', label: '灰分 A', units: ['%', 'unknown'], bases: ['unknown', 'ar', 'ad', 'd'] },
  { key: 'volatile_matter', label: '挥发分 V', units: ['%', 'unknown'], bases: qualityBases },
  { key: 'fixed_carbon', label: '固定碳 FC', units: ['%', 'unknown'], bases: qualityBases },
  { key: 'total_sulfur', label: '全硫 S', units: ['%', 'unknown'], bases: qualityBases },
  { key: 'calorific_value', label: '热值 Q', units: ['MJ/kg', 'kJ/kg', 'kcal/kg', 'unknown'], bases: qualityBases },
  { key: 'total_moisture', label: '全水分 Mt', units: ['%', 'unknown'], bases: ['unknown', 'ar'] },
  { key: 'air_dry_moisture', label: '分析样水分 Mad', units: ['%', 'unknown'], bases: ['unknown', 'ad'] },
  { key: 'price', label: '价格', units: ['CNY/t', 'unknown'], bases: ['unknown', 'ar', 'd'] },
  { key: 'carbon_content', label: '元素碳 C', units: ['%', 'unknown'], bases: qualityBases },
  { key: 'hydrogen_content', label: '元素氢 H', units: ['%', 'unknown'], bases: qualityBases },
  { key: 'nitrogen_content', label: '元素氮 N', units: ['%', 'unknown'], bases: qualityBases },
  { key: 'sio2_content', label: '灰中 SiO₂', units: ['%', 'unknown'], bases: ['unknown', 'ash'] },
  { key: 'hgi', label: '可磨性 HGI', units: ['index', 'unknown'], bases: ['unknown'] },
  { key: 'burnout_rate', label: '燃尽率', units: ['%', 'unknown'], bases: ['unknown'] },
];
export type MetricDraft = Omit<RawMetric, 'value'> & { value: string };
export type AssayDraft = Record<string, MetricDraft>;
export function draftFromRaw(raw: RawAssay): AssayDraft {
  return Object.fromEntries(Object.entries(raw).map(([key, metric]) => [key, { ...metric, value: metric.value == null ? '' : String(metric.value) }]));
}
export function rawFromDraft(draft: AssayDraft): RawAssay {
  const raw: RawAssay = {};
  for (const [key, item] of Object.entries(draft)) {
    if (!item.value.trim()) continue;
    const value = Number(item.value);
    if (!Number.isFinite(value)) throw new Error(`${metricFields.find(field => field.key === key)?.label || key}须为有限数字`);
    raw[key] = { ...item, value };
  }
  return raw;
}
export const metricLabel = (key: string) => metricFields.find(field => field.key === key)?.label || key;
