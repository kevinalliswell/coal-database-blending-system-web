import type { EChartsOption } from 'echarts';
import { Chart, axisText, tooltipBase, useChartPalette } from '../ui/Chart';
import type { BlendingConstraints, ParetoSolution } from '../../lib/types';
import { CONSTRAINT_ROWS } from '../../lib/constants';

/* ---- Ratio donut ---- */
export function RatioDonut({ names, ratios }: { names: string[]; ratios: number[] }) {
  const P = useChartPalette();
  const data = names.map((n, i) => ({ name: n, value: +(ratios[i] * 100).toFixed(2) }));
  const option: EChartsOption = {
    color: P.series,
    tooltip: {
      ...tooltipBase(P),
      trigger: 'item',
      formatter: (p: unknown) => {
        const d = p as { name: string; value: number; percent: number };
        return `${d.name}<br/>配比 <b>${d.value}%</b>`;
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['54%', '78%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: P.surface, borderWidth: 2 },
        label: { show: false },
        emphasis: { scale: true, scaleSize: 6, itemStyle: { shadowBlur: 16, shadowColor: 'rgba(255,122,26,.45)' } },
        data,
      },
    ],
  };
  return <Chart option={option} height={230} />;
}

/* ---- Constraint-margin radar (position within each process window) ---- */
export function MarginRadar({ sol, constraints }: { sol: ParetoSolution; constraints: BlendingConstraints }) {
  const P = useChartPalette();
  const dims = CONSTRAINT_ROWS.map((r) => {
    const lo = constraints[r.min] as number;
    const hi = constraints[r.max] as number;
    const val = (sol as unknown as Record<string, number>)[r.metric] ?? 0;
    const pos = hi > lo ? ((val - lo) / (hi - lo)) * 100 : 50;
    return { name: r.label, pos: Math.max(0, Math.min(100, pos)), val, lo, hi, unit: r.unit };
  });
  const option: EChartsOption = {
    tooltip: {
      ...tooltipBase(P),
      formatter: () =>
        dims.map((d) => `${d.name}: <b>${d.val}</b> ${d.unit} <span style="color:${P.inkMute}">[${d.lo}~${d.hi}]</span>`).join('<br/>'),
    },
    radar: {
      indicator: dims.map((d) => ({ name: d.name, min: 0, max: 100 })),
      center: ['50%', '54%'],
      radius: '66%',
      splitNumber: 4,
      axisLabel: { show: false },
      axisTick: { show: false },
      axisName: { color: P.inkMute, fontFamily: 'IBM Plex Mono', fontSize: 10 },
      splitLine: { lineStyle: { color: P.line } },
      splitArea: { areaStyle: { color: ['rgba(128,128,128,0.05)', 'transparent'] } },
      axisLine: { lineStyle: { color: P.line } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: dims.map((d) => +d.pos.toFixed(1)),
            name: '窗口内位置',
            symbolSize: 4,
            lineStyle: { color: P.cyan, width: 2 },
            areaStyle: { color: hexToRgba(P.cyan, 0.18) },
            itemStyle: { color: P.cyanBright },
          },
        ],
      },
    ],
  };
  return <Chart option={option} height={240} />;
}

/* ---- Pareto scatter (cost vs quality risk), interactive ---- */
export function ParetoScatter({
  solutions,
  recommendedId,
  activeId,
  onPick,
}: {
  solutions: ParetoSolution[];
  recommendedId: string;
  activeId: string;
  onPick: (id: string) => void;
}) {
  const P = useChartPalette();
  const pts = solutions.map((s) => {
    const isRec = s.solution_id === recommendedId;
    const isActive = s.solution_id === activeId;
    return {
      value: [s.total_price, s.quality_penalty, s.total_heat],
      id: s.solution_id,
      isRec,
      symbolSize: isActive ? 20 : isRec ? 17 : 11,
      itemStyle: {
        color: isActive ? P.cyanBright : isRec ? P.emberGlow : P.ember,
        borderColor: isActive ? P.cyan : isRec ? P.ink : 'transparent',
        borderWidth: isActive || isRec ? 2 : 0,
        shadowBlur: isRec || isActive ? 14 : 0,
        shadowColor: 'rgba(255,157,60,.55)',
        opacity: 0.95,
      },
    };
  });

  const option: EChartsOption = {
    grid: { left: 58, right: 22, top: 24, bottom: 44 },
    tooltip: {
      ...tooltipBase(P),
      formatter: (p: unknown) => {
        const d = p as { data: { value: number[]; isRec: boolean } };
        return `${d.data.isRec ? '★ 推荐方案<br/>' : ''}成本 <b>¥${d.data.value[0].toFixed(1)}</b><br/>质量偏离分 <b>${d.data.value[1].toFixed(3)}</b><br/>热值 <b>${Math.round(d.data.value[2])}</b> kcal`;
      },
    },
    xAxis: {
      name: '吨煤成本 ¥',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { ...axisText(P), fontSize: 11 },
      type: 'value',
      scale: true,
      axisLabel: axisText(P),
      axisLine: { lineStyle: { color: P.line } },
      splitLine: { lineStyle: { color: P.line } },
    },
    yAxis: {
      name: '质量偏离分',
      nameTextStyle: { ...axisText(P), fontSize: 11 },
      type: 'value',
      scale: true,
      axisLabel: axisText(P),
      axisLine: { lineStyle: { color: P.line } },
      splitLine: { lineStyle: { color: P.line } },
    },
    series: [
      {
        type: 'scatter',
        data: pts,
      },
    ],
  };

  return (
    <Chart
      option={option}
      height={300}
      onEvents={{
        click: (p) => {
          const d = p as { data?: { id?: string } };
          if (d.data?.id) onPick(d.data.id);
        },
      }}
    />
  );
}

/** convert a hex color to rgba string (for translucent fills that follow the theme accent) */
function hexToRgba(hex: string, alpha: number): string {
  const m = hex.replace('#', '');
  const full = m.length === 3 ? m.split('').map((c) => c + c).join('') : m;
  const n = parseInt(full, 16);
  if (Number.isNaN(n)) return `rgba(56,225,207,${alpha})`;
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
