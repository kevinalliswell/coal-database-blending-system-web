import { Suspense, lazy } from 'react';
import { NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getHealth, USE_MOCK } from './lib/api';
import { qk } from './lib/query';
import { useTheme } from './lib/theme';
import { Icon, type IconName } from './components/ui/Icon';
import { StatusPill } from './components/ui/bits';

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next = theme === 'dark' ? '亮色' : '暗色';
  return (
    <button className="btn btn-icon btn--ghost theme-toggle" onClick={toggle} title={`切换到${next}主题`} aria-label={`切换到${next}主题`}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={17} />
    </button>
  );
}

const Dashboard = lazy(() => import('./pages/Dashboard'));
const CoalDatabase = lazy(() => import('./pages/CoalDatabase'));
const SmartBlending = lazy(() => import('./pages/SmartBlending'));
const ReplacementRatio = lazy(() => import('./pages/ReplacementRatio'));
const HistoryBlending = lazy(() => import('./pages/HistoryBlending'));
const HistoryReplacement = lazy(() => import('./pages/HistoryReplacement'));

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  title: string;
}
const NAV: NavItem[] = [
  { to: '/', label: '总览', icon: 'home', title: '控制台总览' },
  { to: '/coals', label: '煤种数据库', icon: 'database', title: '煤种数据库' },
  { to: '/blending', label: '智能混煤', icon: 'beaker', title: '智能混煤优化' },
  { to: '/replacement', label: '置换比计算', icon: 'scale', title: '置换比计算' },
  { to: '/history/blending', label: '混煤历史', icon: 'history', title: '混煤优化历史' },
  { to: '/history/replacement', label: '置换比历史', icon: 'chart', title: '置换比计算历史' },
];

function Rail() {
  return (
    <nav className="rail">
      <div className="rail__brand" title="煤粉数据库管理及配煤优化控制台">
        <img src="/furnace.svg" alt="煤粉数据库管理及配煤优化控制台" />
      </div>
      <div className="rail__nav">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => `rail__link${isActive ? ' is-active' : ''}`}>
            <Icon name={n.icon} size={21} />
            <span className="tip">{n.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

function Topbar() {
  const loc = useLocation();
  const active =
    NAV.filter((n) => (n.to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(n.to))).sort(
      (a, b) => b.to.length - a.to.length
    )[0] ?? NAV[0];
  const health = useQuery({ queryKey: qk.health, queryFn: getHealth, refetchInterval: 60_000 });

  return (
    <header className="topbar">
      <div className="topbar__crumbs">
        <span className="eyebrow">CBOS · 煤粉配煤控制台</span>
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
            服务在线 · {health.data.storage_mode}
          </StatusPill>
        ) : health.isError ? (
          <StatusPill tone="danger">服务离线</StatusPill>
        ) : (
          <StatusPill tone="mute">检查中…</StatusPill>
        )}
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
  return (
    <div className="shell">
      <Rail />
      <main className="main">
        <Topbar />
        <div className="scroll-area">
          <Suspense fallback={<PageFallback />}>
            <Routes>
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
