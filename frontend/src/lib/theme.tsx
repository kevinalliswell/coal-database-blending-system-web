import { createContext, useCallback, useContext, useEffect, useRef, useMemo, useState, type ReactNode } from 'react';

export type Theme = 'dark' | 'light';
const KEY = 'cbos_theme_anonymous';

interface ThemeApi {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
}

const ThemeCtx = createContext<ThemeApi | null>(null);

function readInitial(): Theme {
  try {
    const s = localStorage.getItem(KEY);
    if (s === 'light' || s === 'dark') return s;
  } catch {
    /* ignore */
  }
  // fall back to whatever the anti-FOUC inline script set on <html>
  const attr = document.documentElement.getAttribute('data-theme');
  return attr === 'light' ? 'light' : 'dark';
}

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.style.colorScheme = t;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const userKey = useRef(KEY);
  const [theme, setThemeState] = useState<Theme>(readInitial);

  const setTheme = useCallback((t: Theme) => {
    // apply synchronously so any getComputedStyle read during the ensuing
    // re-render (e.g. ECharts palette) sees the new theme immediately.
    apply(t);
    try {
      localStorage.setItem(userKey.current, t);
    } catch {
      /* ignore */
    }
    setThemeState(t);
  }, []);

  useEffect(() => {
    const onUser = (event: Event) => {
      const id = (event as CustomEvent<number | null>).detail;
      userKey.current = id ? `cbos_theme_user_${id}` : KEY;
      let saved: Theme = 'dark';
      try { if (localStorage.getItem(userKey.current) === 'light') saved = 'light'; } catch { /* Optional local preference. */ }
      apply(saved); setThemeState(saved);
    };
    window.addEventListener('cbos-user-changed', onUser);
    return () => window.removeEventListener('cbos-user-changed', onUser);
  }, []);

  const toggle = useCallback(() => setTheme(theme === 'dark' ? 'light' : 'dark'), [theme, setTheme]);

  const api = useMemo<ThemeApi>(() => ({ theme, toggle, setTheme }), [theme, toggle, setTheme]);
  return <ThemeCtx.Provider value={api}>{children}</ThemeCtx.Provider>;
}

export function useTheme(): ThemeApi {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
