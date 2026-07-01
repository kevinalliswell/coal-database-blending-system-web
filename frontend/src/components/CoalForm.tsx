import { useState } from 'react';
import type { Coal, CoalDraft } from '../lib/types';
import { COAL_FIELDS, COAL_TYPES } from '../lib/constants';
import { Field } from './ui/bits';

const GROUPS: { id: 'basic' | 'proximate' | 'ultimate' | 'other'; label: string }[] = [
  { id: 'basic', label: '基础信息' },
  { id: 'proximate', label: '工业分析' },
  { id: 'ultimate', label: '元素分析' },
  { id: 'other', label: '其他指标' },
];

function toDraft(coal: Coal | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of COAL_FIELDS) {
    const v = coal ? (coal[f.key] as unknown) : '';
    out[f.key] = v === null || v === undefined ? '' : String(v);
  }
  if (!coal) out.type = COAL_TYPES[0];
  return out;
}

export function CoalForm({
  coal,
  onSubmit,
  onCancel,
  submitting,
  formId,
}: {
  coal: Coal | null;
  onSubmit: (draft: CoalDraft) => void;
  onCancel: () => void;
  submitting: boolean;
  formId: string;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => toDraft(coal));
  const [errors, setErrors] = useState<Record<string, string>>({});

  const set = (k: string, v: string) => setValues((s) => ({ ...s, [k]: v }));

  function validate(): CoalDraft | null {
    const errs: Record<string, string> = {};
    const draft: Record<string, unknown> = {};
    for (const f of COAL_FIELDS) {
      const raw = (values[f.key] ?? '').trim();
      if (f.key === 'name' || f.key === 'type' || f.key === 'supplier') {
        if (f.required && !raw) errs[f.key] = '必填';
        draft[f.key] = raw || (f.key === 'supplier' ? null : '');
        continue;
      }
      if (!raw) {
        if (f.required) errs[f.key] = '必填';
        draft[f.key] = null;
        continue;
      }
      const n = Number(raw);
      if (Number.isNaN(n)) {
        errs[f.key] = '需为数字';
        continue;
      }
      draft[f.key] = n;
    }
    // domain cross-check
    const proxSum = ['ash_content', 'volatile_matter', 'fixed_carbon'].reduce(
      (a, k) => a + (Number(values[k]) || 0),
      0
    );
    if (values.ash_content && values.volatile_matter && values.fixed_carbon && (proxSum < 90 || proxSum > 110)) {
      errs.fixed_carbon = '灰分+挥发分+固定碳应在 90–110 之间';
    }
    setErrors(errs);
    if (Object.keys(errs).length) return null;
    return draft as unknown as CoalDraft;
  }

  return (
    <form
      id={formId}
      onSubmit={(e) => {
        e.preventDefault();
        const d = validate();
        if (d) onSubmit(d);
      }}
    >
      {GROUPS.map((g) => {
        const fields = COAL_FIELDS.filter((f) => f.group === g.id);
        if (!fields.length) return null;
        return (
          <div key={g.id} style={{ marginBottom: 20 }}>
            <div className="eyebrow mb-12">{g.label}</div>
            <div className="grid grid--2" style={{ gap: 14 }}>
              {fields.map((f) => (
                <Field key={f.key} label={f.label} unit={f.unit} required={f.required} error={errors[f.key]}>
                  {f.key === 'type' ? (
                    <select className={`select${errors[f.key] ? ' is-invalid' : ''}`} value={values.type} onChange={(e) => set('type', e.target.value)}>
                      {COAL_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className={`input${errors[f.key] ? ' is-invalid' : ''}`}
                      type={f.key === 'name' || f.key === 'supplier' ? 'text' : 'number'}
                      step={f.step ?? 'any'}
                      value={values[f.key] ?? ''}
                      placeholder={f.required ? '必填' : '可选'}
                      onChange={(e) => set(f.key, e.target.value)}
                    />
                  )}
                </Field>
              ))}
            </div>
          </div>
        );
      })}
      {/* hidden submit handled by footer button via form attr */}
      <button type="submit" style={{ display: 'none' }} disabled={submitting} aria-hidden />
      <button type="button" onClick={onCancel} style={{ display: 'none' }} aria-hidden />
    </form>
  );
}
