import { useState } from 'react';
import type { GaParams } from '../../lib/types';
import { DEFAULT_GA, GA_FIELDS, GA_PRESETS, type GaPreset } from '../../lib/constants';
import { Drawer } from '../ui/Overlay';
import { Field } from '../ui/bits';
import { Icon } from '../ui/Icon';

export function GaDrawer({
  open,
  onClose,
  params,
  presetId,
  onApply,
}: {
  open: boolean;
  onClose: () => void;
  params: GaParams;
  presetId: GaPreset['id'] | 'custom';
  onApply: (params: GaParams, presetId: GaPreset['id'] | 'custom') => void;
}) {
  const [draft, setDraft] = useState<GaParams>(params);
  const [pid, setPid] = useState<GaPreset['id'] | 'custom'>(presetId);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const applyPreset = (p: GaPreset) => {
    setDraft((d) => ({ ...d, ...p.params }));
    setPid(p.id);
  };
  const setField = (k: keyof GaParams, v: number | boolean | undefined) => {
    setDraft((d) => ({ ...d, [k]: v }));
    setPid('custom');
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="算法参数"
      subtitle="NSGA-II 多目标遗传算法"
      icon={<Icon name="settings" size={18} />}
      wide
      footer={
        <>
          <button
            className="btn btn--ghost"
            onClick={() => {
              setDraft(DEFAULT_GA);
              setPid('balanced');
            }}
          >
            <Icon name="reset" size={15} /> 恢复默认
          </button>
          <button
            className="btn btn--primary"
            onClick={() => {
              onApply(draft, pid);
              onClose();
            }}
          >
            <Icon name="check" size={15} /> 应用参数
          </button>
        </>
      }
    >
      <div className="eyebrow mb-12">求解档位</div>
      <div className="col gap-10">
        {GA_PRESETS.map((p) => (
          <button
            key={p.id}
            className={`coal-pick${pid === p.id ? ' is-picked' : ''}`}
            onClick={() => applyPreset(p)}
            style={{ textAlign: 'left' }}
          >
            <span
              className="row center flex-none"
              style={{
                width: 34,
                height: 34,
                borderRadius: 'var(--r-sm)',
                background: pid === p.id ? 'var(--ember-soft)' : 'var(--surface-3)',
                color: pid === p.id ? 'var(--ember-glow)' : 'var(--ink-mute)',
              }}
            >
              <Icon name={p.id === 'fast' ? 'zap' : p.id === 'fine' ? 'target' : 'gauge'} size={17} />
            </span>
            <div className="grow">
              <div className="coal-pick__name">{p.label}</div>
              <div className="text-xs text-mute">{p.desc}</div>
            </div>
            {pid === p.id && <Icon name="check" size={16} className="text-ember" />}
          </button>
        ))}
        {pid === 'custom' && <div className="text-xs text-amber row gap-6"><Icon name="sliders" size={13} /> 已自定义参数</div>}
      </div>

      <button className="btn btn--ghost btn--block mt-16" onClick={() => setShowAdvanced((s) => !s)}>
        <Icon name={showAdvanced ? 'chevronUp' : 'chevronDown'} size={15} />
        {showAdvanced ? '收起高级参数' : `展开高级参数（${GA_FIELDS.length + 1} 项）`}
      </button>

      {showAdvanced && (
        <div className="mt-16">
          <div className="grid grid--2" style={{ gap: 14 }}>
            {GA_FIELDS.map((f) => (
              <Field key={f.key} label={f.label} hint={f.hint}>
                <input
                  className="input"
                  type="number"
                  min={f.min}
                  max={f.max}
                  step={f.step ?? 1}
                  value={(draft[f.key] as number | undefined) ?? ''}
                  onChange={(e) => setField(f.key,
                    f.key === 'random_seed' && e.target.value === '' ? undefined : Number(e.target.value))}
                />
              </Field>
            ))}
          </div>
          <div className="col gap-12 mt-16">
            <label className="switch">
              <input type="checkbox" checked={draft.adaptive_mutation} onChange={(e) => setField('adaptive_mutation', e.target.checked)} />
              <span className="switch__track" />
              <span>
                <div className="fw-500 text-sm">启用自适应变异</div>
                <div className="text-xs text-mute">根据收敛情况动态调整变异率</div>
              </span>
            </label>
          </div>
        </div>
      )}
    </Drawer>
  );
}
