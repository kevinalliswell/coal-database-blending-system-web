import { useEffect, useRef } from 'react';
import * as echarts from 'echarts';
import type { EChartsOption, TooltipComponentOption } from 'echarts';
import { useTheme } from '../../lib/theme';

/** Thin ECharts wrapper — handles lifecycle, resize, theming. */
export function Chart({
  option,
  height = 260,
  onEvents,
  className,
}: {
  option: EChartsOption;
  height?: number | string;
  onEvents?: Record<string, (params: unknown) => void>;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);
  const eventsRef = useRef(onEvents);
  eventsRef.current = onEvents;

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: 'canvas' });
    chartRef.current = chart;
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || chart.isDisposed()) return;
    chart.setOption(option, true);
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onEvents) return;
    const handlers: [string, (p: unknown) => void][] = [];
    for (const evt of Object.keys(onEvents)) {
      const h = (p: unknown) => eventsRef.current?.[evt]?.(p);
      chart.on(evt, h);
      handlers.push([evt, h]);
    }
    return () => {
      handlers.forEach(([evt, h]) => chart.off(evt, h));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Object.keys(onEvents ?? {}).join(',')]);

  return <div ref={ref} className={className} style={{ width: '100%', height }} />;
}

/* ---- Theme-aware chart palette (single source of truth = CSS tokens) ---- */

export interface ChartPalette {
  ember: string;
  emberBright: string;
  emberGlow: string;
  cyan: string;
  cyanBright: string;
  mint: string;
  amber: string;
  danger: string;
  violet: string;
  ink: string;
  inkMute: string;
  line: string;
  surface: string;
  series: string[];
}

/** Categorical series colors, per theme (deepened for light so slices read on white). */
export const SERIES_COLORS = [
  '#ff9d3c',
  '#38e1cf',
  '#ffb547',
  '#a98bff',
  '#46dd9a',
  '#ff7a1a',
  '#6ff2e4',
  '#ffc74d',
  '#ff6b6b',
  '#7db8ff',
  '#e58cff',
  '#b6ff7a',
];
const SERIES_LIGHT = [
  '#c2400a',
  '#0f8177',
  '#b06a00',
  '#6a4fd0',
  '#0d8f5a',
  '#b83c06',
  '#0a6d64',
  '#8a6d00',
  '#cf2b2b',
  '#2f6fd0',
  '#a13fb8',
  '#4a7d16',
];

function cssVar(cs: CSSStyleDeclaration, name: string, fallback: string): string {
  return cs.getPropertyValue(name).trim() || fallback;
}

/** Reads the active theme's tokens so ECharts colors always match the CSS theme. */
export function useChartPalette(): ChartPalette {
  const { theme } = useTheme();
  const cs = getComputedStyle(document.documentElement);
  return {
    ember: cssVar(cs, '--ember', '#ff7a1a'),
    emberBright: cssVar(cs, '--ember-bright', '#ff9d3c'),
    emberGlow: cssVar(cs, '--ember-glow', '#ffb547'),
    cyan: cssVar(cs, '--cyan', '#38e1cf'),
    cyanBright: cssVar(cs, '--cyan-bright', '#6ff2e4'),
    mint: cssVar(cs, '--mint', '#46dd9a'),
    amber: cssVar(cs, '--amber', '#ffc74d'),
    danger: cssVar(cs, '--danger', '#ff4d4d'),
    violet: cssVar(cs, '--violet', '#a98bff'),
    ink: cssVar(cs, '--ink', '#f4f0e6'),
    inkMute: cssVar(cs, '--ink-mute', '#928d81'),
    line: cssVar(cs, '--line-2', 'rgba(240,232,214,0.12)'),
    surface: cssVar(cs, '--surface-2', '#1b1b23'),
    series: theme === 'light' ? SERIES_LIGHT : SERIES_COLORS,
  };
}

export function axisText(p: ChartPalette) {
  return { color: p.inkMute, fontFamily: 'IBM Plex Mono, monospace', fontSize: 10 };
}

export function tooltipBase(p: ChartPalette): TooltipComponentOption {
  return {
    backgroundColor: p.surface,
    borderColor: p.line,
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: p.ink, fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 },
    extraCssText: 'border-radius:8px;box-shadow:0 12px 34px rgba(0,0,0,.28);',
  };
}
