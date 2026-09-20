import { createContext, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, authenticate, setCsrfToken } from './http';
import { createSessionNotifier } from './sessionEvents';
export interface User { id: number; username: string; display_name: string; role: string; active: boolean; permissions: string[] }
interface Session { user: User | null; csrf_token: string; setup_required: boolean; desktop_mode: boolean }
interface SessionContext { user: User; can: (permission: string) => boolean; refresh: () => Promise<void>; logout: () => Promise<void> }
const Context = createContext<SessionContext | null>(null);
export const ROLE_LABELS: Record<string, string> = { admin: '管理员', data_manager: '数据维护员', calculator: '计算员', viewer: '只读' };
export function useSession() { const ctx = useContext(Context); if (!ctx) throw new Error('需要登录'); return ctx; }
export function SessionProvider({ children }: {children: ReactNode}) {
  const cache = useQueryClient();
  const identity = useRef('');
  const generation = useRef(0);
  const bootstrapped = useRef(false);
  const notifier = useRef<ReturnType<typeof createSessionNotifier> | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState('');
  const loadSession = async () => {
    const ticket = ++generation.current;
    const value = await api<Session>('/api/auth/session');
    if (ticket !== generation.current) return;
    const nextIdentity = value.user ? `${value.user.id}:${value.user.role}` : '';
    if (identity.current !== nextIdentity) {
      cache.clear(); identity.current = nextIdentity;
      window.dispatchEvent(new CustomEvent('cbos-user-changed', {detail: value.user?.id || null}));
    }
    setCsrfToken(value.csrf_token);
    setSession(value);
    setError('');
  };
  const refresh = async () => { notifier.current?.notify(); await loadSession(); };
  useEffect(() => {
    const expire = () => { setCsrfToken(''); setSession(null); cache.clear(); void loadSession().catch(e => setError(e.message)); };
    const channel = createSessionNotifier(expire); notifier.current = channel;
    if (!bootstrapped.current) { bootstrapped.current = true; void loadSession().catch(e => setError(e.message)); }
    window.addEventListener('cbos-session-expired', expire);
    const interval = window.setInterval(() => { void loadSession().catch(e => setError(e.message)); }, 60_000);
    return () => { channel.close(); notifier.current = null; window.removeEventListener('cbos-session-expired', expire); window.clearInterval(interval); };
  }, []);
  const logout = async () => {
    await api('/api/auth/logout', { method: 'POST' });
    setSession(null); setCsrfToken(''); cache.clear();
    await refresh();
  };
  if (!session) return <main className="login-page"><section className="panel v2-card"><h1>CBOS</h1><p role="status">{error || '正在连接本机服务…'}</p>{error && <button className="btn" onClick={() => void refresh().catch(e => setError(e.message))}>重试连接</button>}</section></main>;
  if (!session.user) return <Login session={session} onSuccess={async () => { cache.clear(); await refresh(); }} />;
  const value = { user: session.user, can: (p: string) => session.user!.permissions.includes(p), refresh, logout };
  return <Context.Provider value={value}><div key={session.user.id}>{children}</div></Context.Provider>;
}
function Login({ session, onSuccess }: {session: Session; onSuccess: () => Promise<void>}) {
  const [username, setUsername] = useState(''); const [password, setPassword] = useState(''); const [confirm, setConfirm] = useState('');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const setup = session.setup_required;
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    if (setup && password !== confirm) { setError('两次密码不一致'); return; }
    setBusy(true);
    try { await authenticate(setup ? 'setup' : 'login', {username, password}); setPassword(''); setConfirm(''); await onSuccess(); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <main className="login-page"><section className="panel v2-card"><img src="/furnace.svg" width="48" height="48" alt="" /><p className="eyebrow">COAL BLENDING OPTIMIZATION SYSTEM</p><h1>{setup ? '创建首个管理员' : '登录 CBOS'}</h1><p className="text-mute">{session.desktop_mode ? 'Windows 离线版 · 账号与煤质数据保存在本机' : '煤质数据库与配煤优化系统'}</p>{setup && !session.desktop_mode ? <p>请部署管理员在服务器执行 <code>flask --app wsgi users create-admin --username admin</code>，完成后刷新此页。</p> : <form className="v2-form" onSubmit={submit}><label>账号<input required autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} /></label><label>密码<input required type="password" minLength={setup ? 12 : undefined} autoComplete={setup ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} /></label>{setup && <><label>确认密码<input required type="password" autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} /></label><p className="text-mute">使用至少 12 位的独立密码。系统没有默认密码。</p></>}<p role="alert">{error}</p><button className="btn btn--primary" disabled={busy}>{busy ? '处理中…' : setup ? '创建并登录' : '登录'}</button></form>}</section></main>;
}
