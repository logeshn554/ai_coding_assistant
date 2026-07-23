/**
 * NotificationContext — unified notification center for DevPilot.
 *
 * Provides:
 * - notify(message, level) — push a notification
 * - dismiss(id) — remove one
 * - clearAll() — clear all
 * - notifications[] — last 50 notifications, newest-first
 * - unreadCount — number of unread entries
 * - markAllRead() — mark all as read
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useState,
} from 'react';
import type { ReactNode } from 'react';

export type NotificationLevel = 'info' | 'success' | 'warning' | 'error';

export interface Notification {
  id: string;
  message: string;
  level: NotificationLevel;
  timestamp: number; // ms since epoch
  read: boolean;
}

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  notify: (message: string, level?: NotificationLevel) => void;
  dismiss: (id: string) => void;
  clearAll: () => void;
  markAllRead: () => void;
}

const NotificationContext = createContext<NotificationContextType | undefined>(
  undefined,
);

const MAX_NOTIFICATIONS = 50;

export const NotificationProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const notify = useCallback(
    (message: string, level: NotificationLevel = 'info') => {
      const entry: Notification = {
        id: `notif_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        message,
        level,
        timestamp: Date.now(),
        read: false,
      };
      setNotifications((prev) => {
        const next = [entry, ...prev];
        return next.length > MAX_NOTIFICATIONS
          ? next.slice(0, MAX_NOTIFICATIONS)
          : next;
      });
    },
    [],
  );

  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        notify,
        dismiss,
        clearAll,
        markAllRead,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotifications = (): NotificationContextType => {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error('useNotifications must be used inside NotificationProvider');
  }
  return ctx;
};
