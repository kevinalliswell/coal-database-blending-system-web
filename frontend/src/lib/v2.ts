import type { BlendingConstraints, GaParams } from './types';
import { apiData } from './http';
export interface RawMetric { value: number | null; unit: string; basis: 'unknown' | 'ar' | 'ad' | 'd' | 'daf' | 'ash'; heat_type?: 'unknown' | 'gr_v' | 'net_v' | 'net_p'; hydrogen_includes_moisture?: boolean | null }
export type RawAssay = Record<string, RawMetric>;
export interface Issue { field: string; code: string; message: string }
export interface Eligibility { eligible: boolean; issues: Issue[]; values: Record<string, number>; trace: unknown[] }
export interface Assay { id: number; coal_id: number; batch_id: number; revision: number; coal_name: string; coal_type: string; batch_code: string; label: string; raw: RawAssay; eligibility: {blending: Eligibility; theory: Eligibility}; archived: boolean; report_number?: string; sampled_at?: string; notes?: string }
export interface Settings { version: number; system_name: string; organization: string; ratio_basis: 'ar' | 'd'; heat_type: 'net_v' | 'gr_v'; heat_unit: 'MJ/kg' | 'kcal/kg'; constraints: BlendingConstraints; ga_params: GaParams }
export const listAssays = () => apiData<Assay[]>('/api/assays');
export const getSettings = () => apiData<Settings>('/api/settings');
export const basisLabel = (basis: string) => ({ ar: '收到基（收到煤质量）', d: '干基（干煤质量）', ad: '空干基（分析样质量）', daf: '干燥无灰基', ash: '灰中含量', unknown: '未确认' }[basis] || basis);
export const heatLabel = (type: string) => ({ net_v: '恒容低位热值', gr_v: '恒容高位热值', net_p: '恒压低位热值', unknown: '未确认' }[type] || type);
export const heatDisplay = (kcal: number, unit: string) => unit === 'MJ/kg' ? kcal * 0.0041868 : kcal;
export const heatCanonical = (value: number, unit: string) => unit === 'MJ/kg' ? value / 0.0041868 : value;
