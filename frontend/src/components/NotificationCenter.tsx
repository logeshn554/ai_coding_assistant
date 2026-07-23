/**
 * NotificationCenter — flyout panel triggered from bell icon in TitleBar.
 * Shows last 50 notifications with level icons, timestamps, and dismiss controls.
 */
import React, { useEffect, useRef } from 'react';
import {
  Bell,
  BellOff,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Info,
  X,
  Trash2,
} from 'lucide-react';
import { useNotifications } from '../core/notifications/NotificationContext';
import type { NotificationLevel } from '../core/notifications/NotificationContext';

interface NotificationCenterProps {
  isOpen: boolean;
  onClose: () => void;
}

const LEVEL_STYLES: Record<
  NotificationLevel,
  { icon: React.FC<{ className?: string; style?: React.CSSProperties }>; color: string; bg: string }
> = {
  info: {
    icon: Info,
    color: 'var(--dp-info)',
    bg: 'rgba(96,165,250,0.08)',
  },
  success: {
    icon: CheckCircle,
    color: 'var(--dp-success)',
    bg: 'rgba(52,211,153,0.08)',
  },
  warning: {
    icon: AlertTriangle,
    color: 'var(--dp-warning)',
    bg: 'rgba(251,191,36,0.08)',
  },
  error: {
    icon: AlertCircle,
    color: 'var(--dp-error)',
    bg: 'rgba(248,113,113,0.08)',
  },
};

function formatTime(ms: number): string {
  const now = Date.now();
  const diff = now - ms;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export const NotificationCenter: React.FC<NotificationCenterProps> = ({
  isOpen,
  onClose,
}) => {
  const { notifications, unreadCount, dismiss, clearAll, markAllRead } =
    useNotifications();
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen, onClose]);

  // Mark all read when opened
  useEffect(() => {
    if (isOpen && unreadCount > 0) {
      markAllRead();
    }
  }, [isOpen, unreadCount, markAllRead]);

  if (!isOpen) return null;

  return (
    <div
      ref={panelRef}
      className="absolute top-8 right-2 z-[9999] w-[340px] animate-slide-down"
      style={{
        background: 'var(--dp-bg-elevated)',
        border: '1px solid var(--dp-border-mid)',
        borderRadius: 'var(--dp-radius-xl)',
        boxShadow: 'var(--dp-shadow-float)',
        maxHeight: '480px',
        display: 'flex',
        flexDirection: 'column',
      }}
      role="dialog"
      aria-label="Notification Center"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid var(--dp-border)' }}
      >
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4" style={{ color: 'var(--dp-accent)' }} />
          <span className="text-[13px] font-semibold" style={{ color: 'var(--dp-text-bright)' }}>
            Notifications
          </span>
          {notifications.length > 0 && (
            <span
              className="text-[10px] font-mono px-1.5 py-0.5 rounded-full"
              style={{
                background: 'var(--dp-accent-dim)',
                color: 'var(--dp-accent)',
              }}
            >
              {notifications.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {notifications.length > 0 && (
            <button
              onClick={clearAll}
              title="Clear all"
              className="w-6 h-6 flex items-center justify-center rounded transition-colors cursor-pointer"
              style={{ color: 'var(--dp-text-muted)' }}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded transition-colors cursor-pointer"
            style={{ color: 'var(--dp-text-muted)' }}
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="overflow-y-auto flex-1">
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-12 px-4">
            <BellOff
              className="w-8 h-8 opacity-25"
              style={{ color: 'var(--dp-text-muted)' }}
            />
            <p
              className="text-[12px] text-center"
              style={{ color: 'var(--dp-text-muted)' }}
            >
              No notifications yet
            </p>
          </div>
        ) : (
          <ul className="p-2 space-y-1">
            {notifications.map((n) => {
              const { icon: Icon, color, bg } = LEVEL_STYLES[n.level];
              return (
                <li
                  key={n.id}
                  className="group flex items-start gap-3 px-3 py-2.5 rounded-lg transition-colors"
                  style={{
                    background: n.read ? 'transparent' : bg,
                    border: `1px solid ${n.read ? 'transparent' : `${color}22`}`,
                  }}
                >
                  <Icon
                    className="w-4 h-4 shrink-0 mt-0.5"
                    style={{ color }}
                  />
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-[12px] leading-snug break-words"
                      style={{ color: 'var(--dp-text-primary)' }}
                    >
                      {n.message}
                    </p>
                    <time
                      className="text-[10px] font-mono mt-0.5 block"
                      style={{ color: 'var(--dp-text-muted)' }}
                      dateTime={new Date(n.timestamp).toISOString()}
                    >
                      {formatTime(n.timestamp)}
                    </time>
                  </div>
                  <button
                    onClick={() => dismiss(n.id)}
                    className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center rounded transition-all cursor-pointer shrink-0"
                    style={{ color: 'var(--dp-text-muted)' }}
                    aria-label="Dismiss"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
};

/** Bell icon button with unread badge — drop into TitleBar */
export const NotificationBell: React.FC<{
  onClick: () => void;
  isOpen: boolean;
}> = ({ onClick, isOpen }) => {
  const { unreadCount } = useNotifications();

  return (
    <button
      id="notification-bell"
      onClick={onClick}
      title={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      className="relative w-7 h-7 flex items-center justify-center rounded transition-colors cursor-pointer"
      style={{
        background: isOpen ? 'var(--dp-bg-active)' : undefined,
        color: isOpen ? 'var(--dp-text-bright)' : 'var(--dp-text-muted)',
      }}
    >
      <Bell className="w-4 h-4" />
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] flex items-center justify-center rounded-full text-[8px] font-bold px-1"
          style={{
            background: 'var(--dp-error)',
            color: '#fff',
          }}
        >
          {unreadCount > 9 ? '9+' : unreadCount}
        </span>
      )}
    </button>
  );
};
