import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../lib/http';
import { ROLE_LABELS, useSession, type User } from '../lib/session';

const roles = Object.entries(ROLE_LABELS);
export default function UserAdmin() {
  const { user, can, refresh } = useSession();
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('viewer');
  const [password, setPassword] = useState('');
  const load = async () => { setUsers((await api<{ data: User[] }>('/api/users')).data); };
  useEffect(() => { if (can('admin')) void load().catch(e => setError(e.message)); }, []);
  async function create(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('');
    try {
      await api('/api/users', {method: 'POST', body: JSON.stringify({username, display_name: displayName || username, role, password})});
      setUsername(''); setDisplayName(''); setPassword(''); setMessage('账号已创建'); await load();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  if (!can('admin')) return <div className="page"><p>需要管理员权限。</p></div>;
  return <div className="page"><div className="page__head"><div><h1 className="page__title">用户与权限</h1><p className="page__lead">账号属于当前部署。停用、修改角色或重置密码后，原会话立即失效。</p></div></div>
    <section className="panel v2-card role-summary"><h2>四种固定角色</h2><table><thead><tr><th>角色</th><th>可执行操作</th></tr></thead><tbody>
      <tr><td>管理员</td><td>所有操作、用户管理和系统设置</td></tr><tr><td>数据维护员</td><td>维护煤种、批次及化验记录</td></tr><tr><td>计算员</td><td>执行混煤优化和置换比计算</td></tr><tr><td>只读</td><td>查看数据和历史</td></tr>
    </tbody></table><p className="text-mute">所有登录账号都可查看及导出共享数据和历史。系统至少保留一位启用的管理员。</p></section>
    <section className="panel v2-card"><h2>创建账号</h2><form className="v2-form" onSubmit={create}><div className="v2-grid">
      <label>账号<input required minLength={3} maxLength={64} pattern="[a-zA-Z0-9_.\-]+" autoComplete="off" value={username} onChange={e => setUsername(e.target.value)} placeholder="字母、数字、点、下划线或连字符" /></label>
      <label>显示名称<input maxLength={80} value={displayName} onChange={e => setDisplayName(e.target.value)} /></label>
      <label>角色<select value={role} onChange={e => setRole(e.target.value)}>{roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>初始密码<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="至少 12 位" /></label>
    </div><div className="v2-actions"><button className="btn btn--primary" disabled={busy}>{busy ? '正在创建…' : '创建账号'}</button><span role="status">{message}</span></div><p className="v2-error" role="alert">{error}</p></form></section>
    <h2 className="v2-section-title">已有账号 · {users.length}</h2>{users.map(account => <UserEditor key={`${account.id}-${account.role}-${account.active}`} account={account} own={account.id === user.id} onSaved={async () => { await load(); await refresh(); }} />)}
  </div>;
}

function UserEditor({ account, own, onSaved }: {account: User; own: boolean; onSaved: () => Promise<void>}) {
  const [name, setName] = useState(account.display_name);
  const [role, setRole] = useState(account.role);
  const [active, setActive] = useState(account.active);
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [resetOpen, setResetOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  async function save(event: FormEvent, reset: boolean) {
    event.preventDefault(); setError(''); setMessage('');
    if (reset && password !== confirmation) { setError('两次密码不一致'); return; }
    setBusy(true);
    try {
      await api(`/api/users/${account.id}${reset ? '/password' : ''}`, {method: reset ? 'PUT' : 'PATCH', body: JSON.stringify(reset ? {password} : {display_name: name, role, active})});
      setPassword(''); setConfirmation(''); setResetOpen(false); setMessage(reset ? '密码已重置，原会话已退出' : '账号已更新'); await onSaved();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <section className="panel v2-card"><h3>{account.username}{own ? '（当前账号）' : ''}</h3><form className="v2-form" onSubmit={e => void save(e, false)}><div className="v2-grid">
    <label>显示名称<input required maxLength={80} value={name} onChange={e => setName(e.target.value)} /></label>
    <label>角色<select value={role} onChange={e => setRole(e.target.value)}>{roles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    <label>启用状态<select value={active ? 'active' : 'disabled'} onChange={e => setActive(e.target.value === 'active')}><option value="active">启用</option><option value="disabled">停用</option></select></label>
  </div><div className="v2-actions"><button className="btn" disabled={busy}>保存账号</button><button type="button" className="btn btn--ghost" onClick={() => setResetOpen(!resetOpen)} disabled={busy}>重置密码</button></div></form>
    {resetOpen && <form className="v2-form" style={{marginTop: 20}} onSubmit={e => void save(e, true)}><div className="v2-grid"><label>新密码<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></label><label>确认新密码<input required type="password" minLength={12} maxLength={128} autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label></div><p className="text-mute">重置后该账号的所有会话会退出{own ? '，包括当前会话' : ''}。</p><button className="btn btn--primary" disabled={busy}>确认重置密码</button></form>}
    <p className="v2-error" role="alert">{error}</p><p role="status">{message}</p>
  </section>;
}
