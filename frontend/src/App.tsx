import { Suspense, lazy, useEffect, useRef, useState, type RefObject } from 'react';
import { NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getHealth, USE_MOCK } from './lib/api';
import { useSession, ROLE_LABELS } from './lib/session';
import { getSettings } from './lib/v2';
import { qk } from './lib/query';
import { useTheme } from './lib/theme';
import { Icon } from './components/ui/Icon';
import { StatusPill } from './components/ui/bits';
import { Navigation, NAV } from './components/Navigation';

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next = theme === 'dark' ? '亮色' : '暗色';
  return (
    <button className="btn btn-icon btn--ghost theme-toggle" onClick={toggle} title={`切换到${next}主题`} aria-label={`切换到${next}主题`}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={17} />
    </button>
  );
}

const UserAdmin = lazy(() => import('./pages/UserAdmin'));
const SystemSettings = lazy(() => import('./pages/SystemSettings'));
const Account = lazy(() => import('./pages/Account'));
const Help = lazy(() => import('./pages/Help'));
const About = lazy(() => import('./pages/About'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const CoalDatabase = lazy(() => import('./pages/CoalDatabase'));
const SmartBlending = lazy(() => import('./pages/SmartBlending'));
const ReplacementRatio = lazy(() => import('./pages/ReplacementRatio'));
const HistoryBlending = lazy(() => import('./pages/HistoryBlending'));
const HistoryReplacement = lazy(() => import('./pages/HistoryReplacement'));

function Topbar({ onMenu, menuOpen, menuRef }: {onMenu: () => void; menuOpen: boolean; menuRef: RefObject<HTMLButtonElement>}) {
  const loc = useLocation();
  const { user, logout } = useSession();
  const settings = useQuery({ queryKey: ['settings'], queryFn: getSettings });
  const active =
    NAV.filter((n) => (n.to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(n.to))).sort(
      (a, b) => b.to.length - a.to.length
    )[0] ?? NAV[0];
  const health = useQuery({ queryKey: qk.health, queryFn: getHealth, refetchInterval: 60_000 });

  return (
    <header className="topbar">
      <div className="topbar__crumbs">
        <button ref={menuRef} className="btn btn-icon btn--ghost mobile-menu-toggle" aria-label="打开导航菜单" aria-controls="primary-navigation" aria-expanded={menuOpen} onClick={onMenu}><Icon name="menu" size={19} /></button>
        <span className="eyebrow">{settings.data?.system_name || 'CBOS · 煤粉配煤控制台'}</span>
        <Icon name="chevronRight" size={14} className="text-mute" />
        <span className="topbar__title">{active.title}</span>
      </div>
      <div className="topbar__meta">
        {USE_MOCK && (
          <StatusPill tone="warn">
            <Icon name="zap" size={13} fill /> 演示数据
          </StatusPill>
        )}
        {health.isSuccess ? (
          <StatusPill tone="mint" live>
            服务在线
          </StatusPill>
        ) : health.isError ? (
          <StatusPill tone="danger">服务离线</StatusPill>
        ) : (
          <StatusPill tone="mute">检查中…</StatusPill>
        )}
        <NavLink to="/account" className="session-name">{user.display_name || user.username} · {ROLE_LABELS[user.role]}</NavLink>
        <button className="btn btn--ghost" onClick={() => void logout()}>退出</button>
        <ThemeToggle />
      </div>
    </header>
  );
}

function PageFallback() {
  return (
    <div className="page">
      <div className="sk" style={{ height: 30, width: 260, marginBottom: 20 }} />
      <div className="grid grid--stats">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="sk" style={{ height: 92 }} />
        ))}
      </div>
    </div>
  );
}

export function App() {
  const { can, user } = useSession();
  const preferenceKey = `cbos_sidebar_user_${user.id}`;
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(preferenceKey) === 'collapsed'; } catch { return false; }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const location = useLocation();
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollRef.current?.scrollTo(0, 0); }, [location.pathname]);
  useEffect(() => {
    if (mainRef.current) mainRef.current.inert = mobileOpen;
    if (!mobileOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') { if (mainRef.current) mainRef.current.inert = false; setMobileOpen(false); menuRef.current?.focus(); } };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [mobileOpen]);
  useEffect(() => {
    const screen = window.matchMedia('(max-width: 860px)');
    const closeOnDesktop = () => { if (!screen.matches) setMobileOpen(false); };
    screen.addEventListener('change', closeOnDesktop);
    return () => screen.removeEventListener('change', closeOnDesktop);
  }, []);
  function toggleSidebar() {
    setCollapsed(value => {
      try { localStorage.setItem(preferenceKey, value ? 'expanded' : 'collapsed'); } catch { /* Optional preference. */ }
      return !value;
    });
  }
  return (
    <div className={`shell${collapsed ? ' shell--collapsed' : ''}${mobileOpen ? ' shell--nav-open' : ''}`}>
      <Navigation collapsed={collapsed} mobileOpen={mobileOpen} onToggle={toggleSidebar} onClose={() => { if (mobileOpen) { if (mainRef.current) mainRef.current.inert = false; setMobileOpen(false); menuRef.current?.focus(); } }} />
      <main className="main" ref={mainRef}>
        <Topbar onMenu={() => setMobileOpen(true)} menuOpen={mobileOpen} menuRef={menuRef} />
        <div className="scroll-area" ref={scrollRef}>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/users" element={can('admin') ? <UserAdmin /> : <Help />} />
              <Route path="/settings" element={can('admin') ? <SystemSettings /> : <Help />} />
              <Route path="/account" element={<Account />} />
              <Route path="/help" element={<Help />} />
              <Route path="/about" element={<About />} />
              <Route path="/" element={<Dashboard />} />
              <Route path="/coals" element={<CoalDatabase />} />
              <Route path="/blending" element={<SmartBlending />} />
              <Route path="/replacement" element={<ReplacementRatio />} />
              <Route path="/history/blending" element={<HistoryBlending />} />
              <Route path="/history/replacement" element={<HistoryReplacement />} />
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  );
}
