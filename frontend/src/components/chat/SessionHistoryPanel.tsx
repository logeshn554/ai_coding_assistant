import React, { useCallback, useEffect, useState } from 'react';
import { History, Loader2, MessageSquare, Play } from 'lucide-react';
import type { Session } from '../../types/chat';

interface SessionHistoryPanelProps {
  activeSessionId?: string;
  onResume: (sessionId: string) => Promise<void>;
}

function formatTimestamp(value: string | number | undefined): string {
  if (value === undefined || value === null || value === '') {
    return '—';
  }
  const ms = typeof value === 'number'
    ? (value < 1e12 ? value * 1000 : value)
    : Date.parse(value);
  if (Number.isNaN(ms)) {
    return '—';
  }
  return new Date(ms).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Session History tab — lists persisted chats with Resume.
 */
export const SessionHistoryPanel: React.FC<SessionHistoryPanelProps> = ({
  activeSessionId,
  onResume,
}) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resumingId, setResumingId] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/sessions');
      if (!res.ok) {
        throw new Error(`Failed to load sessions (${res.status})`);
      }
      const data: unknown = await res.json();
      const list = (data as { sessions?: Session[] }).sessions ?? [];
      setSessions(list);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to load sessions';
      setError(message);
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const handleResume = async (sessionId: string) => {
    setResumingId(sessionId);
    try {
      await onResume(sessionId);
    } finally {
      setResumingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 p-8 text-[var(--dp-text-muted)]" role="status" aria-live="polite">
        <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
        <span className="text-[11px]">Loading session history…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 space-y-3" role="alert">
        <p className="text-[12px] text-[var(--dp-error)]">{error}</p>
        <button
          type="button"
          onClick={() => void loadSessions()}
          className="px-3 py-1.5 text-[11px] font-semibold rounded-md bg-white/8 text-[var(--dp-text-secondary)] hover:bg-white/12 cursor-pointer"
        >
          Retry
        </button>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 p-8 text-center" role="status">
        <History className="w-8 h-8 text-[var(--dp-text-muted)] opacity-40" aria-hidden="true" />
        <p className="text-[12px] font-medium text-[var(--dp-text-secondary)]">No sessions yet</p>
        <p className="text-[11px] text-[var(--dp-text-muted)] max-w-[220px]">
          Start a chat and your conversation history will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="p-3 space-y-2" role="list" aria-label="Session history">
      {sessions.map((s) => {
        const isActive = s.id === activeSessionId;
        const preview = s.first_user_message || s.title || '(no messages)';
        return (
          <article
            key={s.id}
            role="listitem"
            className={`rounded-lg border p-3 transition-colors ${
              isActive
                ? 'border-[var(--dp-accent)]/40 bg-[var(--dp-accent-dim)]'
                : 'border-[var(--dp-border)] bg-white/3 hover:border-[var(--dp-border-mid)]'
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-1.5 min-w-0">
                <MessageSquare className="w-3.5 h-3.5 text-[var(--dp-accent)] shrink-0" aria-hidden="true" />
                <time className="text-[10px] font-mono text-[var(--dp-text-muted)]" dateTime={String(s.updated_at ?? '')}>
                  {formatTimestamp(s.updated_at)}
                </time>
                {s.mode && (
                  <span className="text-[9px] uppercase tracking-wider font-semibold text-[var(--dp-text-muted)] bg-white/6 px-1.5 py-0.5 rounded">
                    {s.mode}
                  </span>
                )}
              </div>
              <span className="text-[10px] font-mono text-[var(--dp-text-muted)] shrink-0">
                {s.message_count ?? 0} msgs
              </span>
            </div>
            <p className="text-[12px] text-[var(--dp-text-primary)] leading-snug mb-2.5 line-clamp-2">
              {preview}
            </p>
            <button
              type="button"
              disabled={resumingId === s.id}
              onClick={() => void handleResume(s.id)}
              aria-label={`Resume session ${preview}`}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold rounded-md bg-[var(--dp-accent)] text-white hover:opacity-90 disabled:opacity-50 cursor-pointer transition-opacity"
            >
              {resumingId === s.id ? (
                <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="w-3 h-3" aria-hidden="true" />
              )}
              Resume
            </button>
          </article>
        );
      })}
    </div>
  );
};
