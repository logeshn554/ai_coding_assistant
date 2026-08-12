import React, { useState, useEffect } from 'react';
import { RotateCcw, Plus, Trash2, X, MessageSquare, Clock, Cpu, CheckCircle2, Search } from 'lucide-react';
import type { Session } from '../../types/chat';

export interface ExtendedSession extends Session {
  provider?: string;
  model?: string;
  tokenUsage?: {
    input?: number;
    output?: number;
    total?: number;
  };
}

interface ChatHistoryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeSessionId?: string;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession?: (sessionId: string) => void;
}

export const ChatHistoryDrawer: React.FC<ChatHistoryDrawerProps> = ({
  isOpen,
  onClose,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
}) => {
  const [sessions, setSessions] = useState<ExtendedSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (err) {
      console.error('Failed to load session history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const filteredSessions = sessions.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (s.title && s.title.toLowerCase().includes(q)) ||
      (s.first_user_message && s.first_user_message.toLowerCase().includes(q)) ||
      (s.provider && s.provider.toLowerCase().includes(q)) ||
      (s.model && s.model.toLowerCase().includes(q))
    );
  });

  const currentSession = filteredSessions.find((s) => s.id === activeSessionId);
  const previousSessions = filteredSessions.filter((s) => s.id !== activeSessionId);

  const formatDate = (timestamp?: number | string) => {
    if (!timestamp) return 'Recent';
    const tsNum = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp;
    if (!tsNum || isNaN(tsNum)) return 'Recent';
    const date = new Date(tsNum * 1000);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) return 'Today';
    
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';

    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs animate-[fadeIn_150ms_ease-out]">
      <div className="w-full max-w-sm h-full bg-[#14161d] border-l border-white/10 flex flex-col text-zinc-200 font-sans select-none shadow-2xl">
        
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/10 bg-[#1a1d26]">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-purple-600/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <RotateCcw className="w-3.5 h-3.5" />
            </div>
            <span className="font-bold text-sm text-zinc-100">Chat History</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                onNewSession();
                onClose();
              }}
              className="flex items-center gap-1 px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-bold transition-all shadow-sm cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Chat</span>
            </button>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Search Bar matching Requirement 17 */}
        <div className="p-3 border-b border-white/5 bg-[#171a22]">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-zinc-400 absolute left-3 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search conversations..."
              className="w-full pl-8 pr-3 py-1.5 bg-black/30 border border-white/10 rounded-xl text-xs text-white focus:outline-none focus:border-purple-500 font-sans"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 text-zinc-400 hover:text-white"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* Current Conversation Section */}
          {currentSession && (
            <div className="space-y-1.5">
              <div className="text-[10px] uppercase font-bold text-purple-400 tracking-wider flex items-center gap-1 px-1">
                <CheckCircle2 className="w-3 h-3 text-purple-400" />
                Current Conversation
              </div>
              <div className="p-3 bg-purple-950/30 border border-purple-500/30 rounded-xl space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-bold text-xs text-white truncate max-w-[220px]">
                    {currentSession.title || 'Active Session'}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">
                    Active
                  </span>
                </div>
                <div className="flex items-center justify-between text-[10.5px] text-zinc-400 font-mono">
                  <span className="flex items-center gap-1">
                    <Cpu className="w-3 h-3 text-purple-400" />
                    {currentSession.model || 'Active Model'}
                  </span>
                  <span>{currentSession.message_count || 0} msgs</span>
                </div>
              </div>
            </div>
          )}

          {/* History List */}
          <div className="space-y-2">
            <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider px-1">
              Previous Conversations
            </div>

            {loading ? (
              <div className="text-center py-8 text-xs text-zinc-500">Loading history...</div>
            ) : previousSessions.length === 0 ? (
              <div className="text-center py-8 text-xs text-zinc-500 bg-white/[0.01] border border-white/5 rounded-xl">
                No previous conversations found.
              </div>
            ) : (
              previousSessions.map((session) => {
                const dateLabel = formatDate(session.updated_at || session.created_at);
                const providerName = session.provider || 'Provider';
                const modelName = session.model || 'Model';
                const totalTokens = session.tokenUsage?.total || 0;

                return (
                  <div
                    key={session.id}
                    className="group relative p-3 rounded-xl bg-white/[0.02] hover:bg-white/[0.06] border border-white/5 transition-all cursor-pointer space-y-1.5"
                    onClick={() => {
                      onSelectSession(session.id);
                      onClose();
                    }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <MessageSquare className="w-3.5 h-3.5 text-zinc-400 shrink-0 group-hover:text-purple-400" />
                        <span className="font-semibold text-xs text-zinc-200 truncate group-hover:text-white">
                          {session.title || session.first_user_message || 'Untitled Chat'}
                        </span>
                      </div>

                      {onDeleteSession && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteSession(session.id);
                            setSessions((prev) => prev.filter((s) => s.id !== session.id));
                          }}
                          className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-red-400 transition-opacity rounded hover:bg-white/10"
                          title="Delete conversation"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-[10.5px] text-zinc-400 font-mono pt-1 border-t border-white/5">
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-sans text-[9.5px]">
                          {providerName}
                        </span>
                        <span className="truncate max-w-[110px]">{modelName}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {totalTokens > 0 && <span>{Math.round(totalTokens / 1000)}k tokens</span>}
                        <span className="flex items-center gap-0.5 text-zinc-500">
                          <Clock className="w-2.5 h-2.5" />
                          {dateLabel}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

        </div>

      </div>
    </div>
  );
};
