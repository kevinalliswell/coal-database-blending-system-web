import { useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { Icon, type IconName } from './ui/Icon';
import { useSession } from '../lib/session';

export const NAV = [
  { to: '/', label: '工作台', icon: 'home', title: '工作台', group: '日常工作' },
  { to: '/coals', label: '煤质数据库', icon: 'database', title: '煤质数据库', group: '日常工作' },
  { to: '/blending', label: '智能混煤', icon: 'beaker', title: '智能混煤', group: '日常工作' },
  { to: '/replacement', label: '置换比计算', icon: 'scale', title: '置换比计算', group: '日常工作' },
  { to: '/history/blending', label: '混煤历史', icon: 'history', title: '混煤历史', group: '计算记录' },
  { to: '/history/replacement', label: '置换比历史', icon: 'chart', title: '置换比历史', group: '计算记录' },
  { to: '/settings', label: '系统设置', icon: 'settings', title: '系统设置', group: '系统管理', permission: 'admin' },
  { to: '/users', label: '用户与权限', icon: 'layers', title: '用户与权限', group: '系统管理', permission: 'admin' },
  { to: '/help', label: '使用帮助', icon: 'info', title: '使用帮助', group: '帮助与账号' },
  { to: '/about', label: '关于 CBOS', icon: 'box', title: '关于 CBOS', group: '帮助与账号' },
  { to: '/account', label: '我的账号', icon: 'eye', title: '我的账号', group: '帮助与账号' },
] satisfies {to: string; label: string; icon: IconName; title: string; group: string; permission?: string}[];

export function Navigation({ collapsed, mobileOpen, onToggle, onClose }: {
  collapsed: boolean; mobileOpen: boolean; onToggle: () => void; onClose: () => void;
}) {
  const { can } = useSession();
  const railRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!mobileOpen) return;
    const rail = railRef.current!;
    // Let the visibility transition start before focusing. At its initial
    // frame the link is still hidden and the browser ignores focus().
    let focusFrame = window.requestAnimationFrame(() => {
      focusFrame = window.requestAnimationFrame(() => {
        (rail.querySelector<HTMLElement>('[aria-current="page"]') || rail.querySelector<HTMLElement>('a[href]'))?.focus();
      });
    });
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const controls = [...rail.querySelectorAll<HTMLElement>('a[href],button')].filter(element => element.getClientRects().length);
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    rail.addEventListener('keydown', trapFocus);
    return () => { window.cancelAnimationFrame(focusFrame); rail.removeEventListener('keydown', trapFocus); };
  }, [mobileOpen]);
  const visible = NAV.filter(item => !item.permission || can(item.permission));
  return <>
    {mobileOpen && <button className="nav-backdrop" aria-label="关闭导航菜单" onClick={onClose} />}
    <aside ref={railRef} className="rail" aria-label="应用导航" role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen || undefined}>
      <LinkBrand onClose={onClose} />
      <nav className="rail__nav" id="primary-navigation" aria-label="主菜单">
        {[...new Set(visible.map(item => item.group))].map(group => <div className="rail__group" key={group}>
          <div className="rail__group-label">{group}</div>
          {visible.filter(item => item.group === group).map(item => <NavLink
            key={item.to} to={item.to} end={item.to === '/'} aria-label={item.label}
            title={collapsed ? item.label : undefined} onClick={onClose}
            className={({ isActive }) => `rail__link${isActive ? ' is-active' : ''}`}
          ><Icon name={item.icon} size={19} /><span className="rail__label">{item.label}</span></NavLink>)}
        </div>)}
      </nav>
      <button className="rail__toggle" aria-label={collapsed ? '展开侧边菜单' : '折叠侧边菜单'} aria-expanded={!collapsed} aria-controls="primary-navigation" onClick={onToggle}>
        <Icon name={collapsed ? 'chevronRight' : 'chevronLeft'} size={18} /><span className="rail__label">收起菜单</span>
      </button>
      <button className="rail__mobile-close btn btn--ghost" onClick={onClose}><Icon name="x" size={16} />关闭菜单</button>
    </aside>
  </>;
}

function LinkBrand({ onClose }: { onClose: () => void }) {
  return <NavLink className="rail__brand" to="/" onClick={onClose} aria-label="CBOS 工作台">
    <span className="rail__brand-mark"><img src="/furnace.svg" alt="" /></span>
    <span className="rail__brand-copy"><strong>CBOS</strong><span>煤质与配煤优化</span></span>
  </NavLink>;
}
