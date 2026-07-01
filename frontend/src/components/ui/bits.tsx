import type { ReactNode } from 'react';
import { Icon, type IconName } from './Icon';

export function Readout({
  label,
  value,
  unit,
  tone,
  hint,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  tone?: 'ember' | 'cyan';
  hint?: ReactNode;
}) {
  return (
    <div className="readout">
      <span className="readout__label">{label}</span>
      <span className={`readout__value${tone === 'ember' ? ' is-ember' : tone === 'cyan' ? ' is-cyan' : ''}`}>
        {value}
        {unit && <span className="u">{unit}</span>}
      </span>
      {hint && <span className="readout__delta">{hint}</span>}
    </div>
  );
}

export function StatPanel({
  label,
  value,
  unit,
  icon,
  tone,
  hint,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  icon: IconName;
  tone?: 'ember' | 'cyan';
  hint?: ReactNode;
}) {
  return (
    <div className="panel" style={{ padding: '18px 20px' }}>
      <div className="row between items-start">
        <Readout label={label} value={value} unit={unit} tone={tone} hint={hint} />
        <span
          className="row center"
          style={{
            width: 38,
            height: 38,
            borderRadius: 'var(--r)',
            background: tone === 'cyan' ? 'var(--cyan-soft)' : 'var(--ember-soft)',
            color: tone === 'cyan' ? 'var(--cyan-bright)' : 'var(--ember-glow)',
            border: `1px solid ${tone === 'cyan' ? 'var(--cyan-line)' : 'var(--ember-line)'}`,
          }}
        >
          <Icon name={icon} size={18} />
        </span>
      </div>
    </div>
  );
}

export function Field({
  label,
  unit,
  required,
  hint,
  error,
  children,
}: {
  label: string;
  unit?: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field__label">
        <span>
          {label}
          {required && <span className="field__req">*</span>}
        </span>
        {unit && <span className="unit">{unit}</span>}
      </span>
      {children}
      {error ? <span className="field__hint text-danger">{error}</span> : hint ? <span className="field__hint">{hint}</span> : null}
    </label>
  );
}

export function EmptyState({ icon = 'box', title, sub }: { icon?: IconName; title: string; sub?: string }) {
  return (
    <div className="empty">
      <span className="empty__icon">
        <Icon name={icon} size={30} />
      </span>
      <div className="fw-600">{title}</div>
      {sub && <div className="text-sm text-mute">{sub}</div>}
    </div>
  );
}

export function SkeletonRows({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="col gap-8" style={{ padding: 6 }}>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="row gap-12">
          {Array.from({ length: cols }).map((__, c) => (
            <div key={c} className="sk" style={{ height: 16, flex: c === 0 ? 2 : 1 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="segmented" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          className={`segmented__item${o.value === value ? ' is-active' : ''}`}
          onClick={() => onChange(o.value)}
          role="tab"
          aria-selected={o.value === value}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function StatusPill({ tone, children, live }: { tone: 'ember' | 'cyan' | 'mint' | 'warn' | 'danger' | 'mute'; children: ReactNode; live?: boolean }) {
  const cls =
    tone === 'mint'
      ? 'pill--live'
      : tone === 'ember'
      ? 'pill--ember'
      : tone === 'cyan'
      ? 'pill--cyan'
      : tone === 'warn'
      ? 'pill--warn'
      : tone === 'danger'
      ? 'pill--danger'
      : 'pill--mute';
  return (
    <span className={`pill ${cls}`}>
      {live && <span className="dot" />}
      {children}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="row gap-8 items-center">
      <span className="spinner" />
      {label && <span className="text-sm text-mute">{label}</span>}
    </span>
  );
}
