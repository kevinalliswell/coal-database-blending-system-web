import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from './Icon';

function useLockScroll(open: boolean) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);
}

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  icon,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useLockScroll(open);
  useEscape(open, onClose);
  if (!open) return null;
  return createPortal(
    <>
      <div className="scrim" onClick={onClose} />
      <aside className={`drawer${wide ? ' drawer--wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="drawer__head">
          <div className="row gap-12">
            {icon && <span className="text-ember">{icon}</span>}
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 16 }}>{title}</div>
              {subtitle && <div className="text-sm text-mute mt-4">{subtitle}</div>}
            </div>
          </div>
          <button className="btn btn-icon btn--ghost" onClick={onClose} aria-label="关闭">
            <Icon name="x" size={18} />
          </button>
        </header>
        <div className="drawer__body">{children}</div>
        {footer && <footer className="drawer__foot">{footer}</footer>}
      </aside>
    </>,
    document.body
  );
}

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  icon,
  children,
  footer,
  maxWidth = 560,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  maxWidth?: number;
}) {
  useLockScroll(open);
  useEscape(open, onClose);
  if (!open) return null;
  return createPortal(
    <div className="scrim" onClick={onClose} style={{ display: 'grid', placeItems: 'center', padding: 20 }}>
      <div
        className="panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ width: '100%', maxWidth, maxHeight: '90vh', display: 'flex', flexDirection: 'column', animation: 'fadeUp .24s var(--ease)' }}
      >
        <header className="panel__head">
          <div className="panel__title">
            {icon && <span className="tico">{icon}</span>}
            <div>
              {title}
              {subtitle && <div className="panel__sub" style={{ fontWeight: 400 }}>{subtitle}</div>}
            </div>
          </div>
          <button className="btn btn-icon btn--ghost" onClick={onClose} aria-label="关闭">
            <Icon name="x" size={18} />
          </button>
        </header>
        <div className="panel__body" style={{ overflow: 'auto' }}>
          {children}
        </div>
        {footer && (
          <footer className="drawer__foot" style={{ borderRadius: '0 0 var(--r-lg) var(--r-lg)' }}>
            {footer}
          </footer>
        )}
      </div>
    </div>,
    document.body
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = '确认',
  danger,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: ReactNode;
  confirmText?: string;
  danger?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      icon={<Icon name={danger ? 'alert' : 'info'} size={18} />}
      maxWidth={440}
      footer={
        <>
          <button className="btn btn--ghost" onClick={onClose}>
            取消
          </button>
          <button
            className={`btn ${danger ? 'btn--danger' : 'btn--primary'}`}
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            {confirmText}
          </button>
        </>
      }
    >
      <div className="text-soft">{message}</div>
    </Modal>
  );
}
