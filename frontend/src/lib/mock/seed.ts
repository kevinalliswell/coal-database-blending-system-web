import type { Coal } from '../types';

/* Real 包钢 (Baotou Steel) coal samples from the project's seed CSV,
   plus a handful of representative Chinese coals for a fuller demo table. */

type Row = [
  name: string,
  type: string,
  supplier: string,
  price: number,
  heat: number,
  ash: number,
  vol: number,
  fc: number,
  s: number,
  tm: number,
  hgi: number,
  burnout: number,
  c: number,
  h: number,
  n: number,
  mad: number
];

const ROWS: Row[] = [
  ['山西潞阳洗末煤 S1.0（分析基）', '无烟煤', '包钢', 998.46, 7419, 11.59, 9.61, 76.3, 0.9, 9.82, 65.71, 100, 79.79, 3.21, 1.57, 0.96],
  ['包钢矿业洗末煤 S1.0（分析基）', '无烟煤', '包钢', 992.03, 7174, 10.4, 10.14, 77.06, 0.96, 9.18, 64.35, 100, 80.89, 3.35, 1.65, 0.91],
  ['阳煤4#末煤（分析基）', '无烟煤', '包钢', 1002.24, 7374, 11.01, 9.84, 76.65, 1.06, 7.02, 61.75, 100, 80.31, 3.23, 1.66, 0.81],
  ['山焦1#末煤（分析基）', '无烟煤', '包钢', 1042.79, 6313, 10.63, 9.42, 77.44, 0.48, 7.61, 61.97, 100, 81.21, 3.34, 1.66, 0.63],
  ['宁煤1#末煤（分析基）', '无烟煤', '包钢', 1093.31, 7737, 7.71, 10.01, 79.78, 0.11, 8.21, 69.65, 100, 81.15, 3.23, 1.33, 0.59],
  ['宁煤3#烟煤（分析基）', '烟煤', '包钢', 812.23, 6540, 10.61, 32.11, 54.78, 0.84, 16.5, 59.16, 100, 68.52, 4.35, 1.42, 5.25],
  ['衮矿1#烟煤（分析基）', '烟煤', '包钢', 595.21, 6113, 5.74, 31.6, 60.17, 0.32, 19.1, 61.94, 100, 69.09, 4.53, 1.25, 8.48],
  ['昊华1#烟煤（分析基）', '烟煤', '包钢', 534.44, 6648, 8.85, 37.45, 51.2, 0.48, 22.22, 63.95, 100, 66.72, 4.86, 1.32, 7.73],
  ['神华优混烟煤', '烟煤', '神华集团', 705, 6820, 9.8, 28.5, 58.2, 0.55, 12.0, 62, 98.5, 71.2, 4.4, 1.2, 3.2],
  ['平顶山贫煤末', '贫煤', '平煤神马', 760, 6950, 13.2, 14.8, 68.5, 0.62, 8.5, 78, 96, 76.5, 3.6, 1.4, 1.8],
  ['晋城无烟煤末', '无烟煤', '晋煤集团', 1015, 7250, 12.5, 8.2, 76.8, 0.42, 8.0, 68, 99, 80.2, 3.1, 1.5, 1.1],
  ['蒙泰褐煤提质粉', '褐煤', '蒙泰能源', 410, 5200, 15.6, 38.5, 41.2, 0.38, 22.0, 52, 99.5, 60.1, 4.9, 1.1, 12.5],
  ['大同弱粘煤', '烟煤', '大同煤矿', 640, 6480, 8.9, 30.2, 57.5, 0.45, 11.5, 60, 98, 70.5, 4.4, 1.3, 4.5],
  ['陕北长焰煤', '烟煤', '陕煤集团', 560, 6250, 6.5, 34.8, 55.8, 0.3, 14.0, 55, 99, 68.9, 4.7, 1.0, 6.8],
];

export function seedCoals(): Coal[] {
  const now = new Date();
  return ROWS.map((r, i): Coal => {
    const created = new Date(now.getTime() - (ROWS.length - i) * 86400000 * 3);
    return {
      id: i + 1,
      name: r[0],
      type: r[1],
      supplier: r[2],
      price: r[3],
      calorific_value: r[4],
      ash_content: r[5],
      volatile_matter: r[6],
      fixed_carbon: r[7],
      total_sulfur: r[8],
      total_moisture: r[9],
      moisture: r[9],
      hgi: r[10],
      burnout_rate: r[11],
      carbon_content: r[12],
      hydrogen_content: r[13],
      nitrogen_content: r[14],
      air_dry_moisture: r[15],
      mad: r[15],
      created_at: created.toISOString(),
      updated_at: created.toISOString(),
    };
  });
}
