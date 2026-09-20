/* Lightweight stroke-icon set — no external font dependency.
   24x24 viewBox, currentColor stroke, Feather-esque geometry. */

const P: Record<string, string> = {
  menu: 'M4 6h16M4 12h16M4 18h16',
  flame:
    'M12 3c1.8 2.6 1 4.2-.2 5.6 2.2-.4 3.4 1.2 3.4 3.4a4.2 4.2 0 1 1-8.4 0c0-1.6.7-2.9 1.8-4-.2 2 .9 3 2 3.2C10.8 12 9 9.5 12 3Z',
  home: 'M4 11 12 4l8 7M6 10v9a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-9',
  database:
    'M12 3c4.4 0 8 1.1 8 2.5S16.4 8 12 8 4 6.9 4 5.5 7.6 3 12 3ZM4 5.5v6c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-6M4 11.5v6c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-6',
  layers: 'M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5M3 16.5l9 5 9-5',
  calculator:
    'M7 3h10a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM8 7h8M8 11h.01M12 11h.01M16 11h.01M8 15h.01M12 15h.01M16 15v3M8 18h4',
  history: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 4v4h4M12 8v4l3 2',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14ZM20 20l-4-4',
  refresh: 'M20 11a8 8 0 0 0-14-4.5L3 9M3 4v5h5M4 13a8 8 0 0 0 14 4.5L21 15M21 20v-5h-5',
  plus: 'M12 5v14M5 12h14',
  upload: 'M12 16V4M7 9l5-5 5 5M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2',
  download: 'M12 4v12M7 11l5 5 5-5M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6',
  edit: 'M4 20h4L18.5 9.5a2.1 2.1 0 0 0-3-3L5 17v3ZM15 6l3 3',
  eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  x: 'M6 6l12 12M18 6 6 18',
  check: 'M5 12.5 10 17 19 7',
  chevronDown: 'M6 9l6 6 6-6',
  chevronUp: 'M6 15l6-6 6 6',
  chevronLeft: 'M15 6l-6 6 6 6',
  chevronRight: 'M9 6l6 6-6 6',
  play: 'M7 4.5v15l13-7.5-13-7.5Z',
  sliders: 'M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M13 4v4M7 10v4M15 16v4',
  settings:
    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 0 0-1.7-1l-.3-2.5H9.4l-.3 2.5a7 7 0 0 0-1.7 1l-2.3-1-2 3.4L5.1 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 1.7 1l.3 2.5h4.2l.3-2.5a7 7 0 0 0 1.7-1l2.3 1 2-3.4-2-1.5c.1-.3.1-.7.1-1Z',
  copy: 'M9 9h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1ZM5 15H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v1',
  arrowRight: 'M4 12h15M13 6l6 6-6 6',
  arrowUp: 'M12 20V5M6 11l6-6 6 6',
  arrowDown: 'M12 4v15M6 13l6 6 6-6',
  activity: 'M3 12h4l3 8 4-16 3 8h4',
  alert: 'M12 4 2.5 20h19L12 4ZM12 10v4M12 17.5v.01',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 11v5M12 7.5v.01',
  checkCircle: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM8.5 12l2.5 2.5 4.5-5',
  xCircle: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM9 9l6 6M15 9l-6 6',
  filter: 'M3 5h18l-7 8v5l-4 2v-7L3 5Z',
  gauge: 'M4 19a9 9 0 1 1 16 0M12 13l4-4M12 13a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z',
  zap: 'M13 3 4 14h7l-1 7 9-11h-7l1-7Z',
  box: 'M12 3 3 7.5v9L12 21l9-4.5v-9L12 3ZM3 7.5 12 12M12 12l9-4.5M12 12v9',
  chart: 'M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-7',
  target: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 11.5a.5.5 0 1 0 0 1 .5.5 0 0 0 0-1Z',
  scale: 'M12 3v18M7 21h10M6 6l-3 6a3 3 0 0 0 6 0L6 6ZM18 6l-3 6a3 3 0 0 0 6 0l-3-6ZM4 6h16',
  beaker: 'M9 3h6M10 3v6l-4.5 8A2 2 0 0 0 7.3 20h9.4a2 2 0 0 0 1.8-3L14 9V3M7.5 14h9',
  minus: 'M5 12h14',
  dots: 'M6 12h.01M12 12h.01M18 12h.01',
  dot: 'M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z',
  bolt: 'M13 3 4 14h7l-1 7 9-11h-7l1-7Z',
  save: 'M5 4h11l3 3v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1ZM8 4v5h7V4M8 21v-6h8v6',
  reset: 'M4 4v5h5M4 9a8 8 0 1 1-1.5 6',
  external: 'M14 4h6v6M20 4l-9 9M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
  flask: 'M9 3h6M10 3v6l-4.5 8A2 2 0 0 0 7.3 20h9.4a2 2 0 0 0 1.8-3L14 9V3M7.5 14h9',
  sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M18.4 5.6l1.4-1.4M4.2 19.8l1.4-1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 7 7 0 1 0 20 14.5Z',
};

export type IconName = keyof typeof P;

export function Icon({
  name,
  size = 18,
  className,
  fill = false,
  strokeWidth = 1.75,
}: {
  name: IconName;
  size?: number;
  className?: string;
  fill?: boolean;
  strokeWidth?: number;
}) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill ? 'currentColor' : 'none'}
      stroke={fill ? 'none' : 'currentColor'}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ display: 'block', flex: 'none' }}
    >
      <path d={P[name]} />
    </svg>
  );
}
