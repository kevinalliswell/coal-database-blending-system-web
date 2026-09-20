import { useState, type FormEvent } from 'react';
import { api } from '../lib/http';
import { ROLE_LABELS, useSession } from '../lib/session';

export default function Account() {
  const { user, refresh } = useSession();
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    if (password !== confirmation) { setError('两次新密码不一致'); return; }
    setBusy(true);
    try {
      await api('/api/auth/password', { method: 'PUT', body: JSON.stringify({ current_password: current, password }) });
      setCurrent(''); setPassword(''); setConfirmation('');
      await refresh();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="page"><div className="page__head"><div><h1 className="page__title">我的账号</h1><p className="page__lead">{user.display_name} · {user.username} · {ROLE_LABELS[user.role]}</p></div></div>
    <section className="panel v2-card" style={{ maxWidth: 640 }}><h2>修改密码</h2><p className="text-mute">密码至少 12 位。修改后，本账号的所有会话都会退出，需要重新登录。</p>
      <form className="v2-form" onSubmit={submit}>
        <label>当前密码<input type="password" required autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} /></label>
        <label>新密码<input type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></label>
        <label>确认新密码<input type="password" required minLength={12} maxLength={128} autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>
        <p className="v2-error" role="alert">{error}</p><button className="btn btn--primary" disabled={busy}>{busy ? '正在修改…' : '修改密码并重新登录'}</button>
      </form></section></div>;
}
