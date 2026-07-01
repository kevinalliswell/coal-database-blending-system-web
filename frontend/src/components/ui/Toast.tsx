import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { Icon, type IconName } from './Icon';

type Tone = 'success' | 'error' | 'warn' | 'info';
interface Toast {
  id: number;
  tone: Tone;
  title: string;
  msg?: string;
}

interface ToastApi {
  push: (tone: Tone, title: string, msg?: string) => void;
  success: (title: string, msg?: string) => void;
  error: (title: string, msg?: string) => void;
  warn: (title: string, msg?: string) => void;
  info: (title: string, msg?: string) => void;
}

const Ctx = createContext<ToastApi | null>(null);

const ICONS: Record<Tone, IconName> = {
  success: 'checkCircle',
  error: 'xCircle',
  warn: 'alert',
  info: 'info',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const remove = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (tone: Tone, title: string, msg?: string) => {
      const id = ++idRef.current;
      setToasts((t) => [...t, { id, tone, title, msg }]);
      setTimeout(() => remove(id), tone === 'error' ? 6000 : 4000);
    },
    [remove]
  );

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (t, m) => push('success', t, m),
      error: (t, m) => push('error', t, m),
      warn: (t, m) => push('warn', t, m),
      info: (t, m) => push('info', t, m),
    }),
    [push]
  );

  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone}`} onClick={() => remove(t.id)}>
            <span className="toast__icon">
              <Icon name={ICONS[t.tone]} size={18} />
            </span>
            <div>
              <div className="toast__title">{t.title}</div>
              {t.msg && <div className="toast__msg">{t.msg}</div>}
            </div>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
