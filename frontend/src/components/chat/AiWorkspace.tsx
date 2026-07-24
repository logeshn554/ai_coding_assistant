import React, { useState } from 'react';
import {
  Sparkles, MessageSquare, ListChecks, Brain,
  FileCode, Check, Circle, Zap, Target,
  MoreHorizontal, History, CheckCircle2, Loader2, XCircle,
  Terminal, Search, GitBranch, FileEdit
} from 'lucide-react';
import type {
  ChatMessage,
  ToolExecutionItem,
  ProjectContextInfo, ProjectMemoryItem,
  ChatMode
} from '../../types/chat';
import { AiCommandBar } from './AiCommandBar';
import { ProjectContextPanel } from './ProjectContextPanel';
import { ProjectMemoryPanel } from './ProjectMemoryPanel';
import { MessageList } from './MessageList';
import { SessionHistoryPanel } from './SessionHistoryPanel';
import { useAI } from '../../core/ai/AIContext';

type Tab = 'chat' | 'plan' | 'context' | 'history';

interface AiWorkspaceProps {
  messages: ChatMessage[];
  inputText: string;
  setInputText: (text: string) => void;
  onSendMessage: () => void;
  isGenerating: boolean;
  onCancelGeneration: () => void;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  onConfirmTool?: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  statusMessage?: string;
  contextTokens?: number | null;
  contextPercentage?: number | null;
  activeSessionId?: string;
  onResumeSession?: (sessionId: string) => Promise<void>;
}

// ── Tool icon helper ──────────────────────────────────────────────
const ToolIcon: React.FC<{ type: ToolExecutionItem['tool'] }> = ({ type }) => {
  const cls = 'w-4 h-4';
  if (type === 'terminal') return <Terminal className={cls} />;
  if (type === 'search') return <Search className={cls} />;
  if (type === 'git') return <GitBranch className={cls} />;
  if (type === 'file_edit') return <FileEdit className={cls} />;
  return <FileCode className={cls} />;
};

const toolBgColor = (type: ToolExecutionItem['tool']) => {
  if (type === 'terminal') return 'bg-orange-500/15 text-orange-400';
  if (type === 'search') return 'bg-blue-500/15 text-blue-400';
  if (type === 'git') return 'bg-purple-500/15 text-purple-400';
  if (type === 'file_edit') return 'bg-green-500/15 text-green-400';
  return 'bg-[var(--dp-accent-dim)] text-[var(--dp-accent)]';
};

// ── Live Tool Execution Card ──────────────────────────────────────
const LiveToolCard: React.FC<{ item: ToolExecutionItem }> = ({ item }) => {
  const paramLabel = item.params?.path || item.params?.query || item.params?.command || '';
  const durationSec = item.durationMs != null ? (item.durationMs / 1000).toFixed(1) : null;

  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg bg-white/3 border border-[var(--dp-border)] hover:border-[var(--dp-border-mid)] transition-colors">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${toolBgColor(item.tool)}`}>
        <ToolIcon type={item.tool} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-semibold text-[var(--dp-text-primary)] truncate">{item.name}</p>
        {paramLabel && (
          <p className="text-[10px] text-[var(--dp-text-muted)] font-mono truncate">
            {typeof paramLabel === 'string' ? paramLabel.split(/[\\/]/).pop() : String(paramLabel)}
          </p>
        )}
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {durationSec && (
          <span className="text-[9px] text-[var(--dp-text-muted)] font-mono">{durationSec}s</span>
        )}
        {item.status === 'running' && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--dp-accent)] bg-[var(--dp-accent-dim)] px-1.5 py-0.5 rounded-full font-medium">
            <Loader2 className="w-2.5 h-2.5 animate-spin" /> Running
          </span>
        )}
        {item.status === 'success' && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--dp-success)] bg-[var(--dp-success)]/10 px-1.5 py-0.5 rounded-full font-medium">
            <CheckCircle2 className="w-2.5 h-2.5" />
            {durationSec ? `Done in ${durationSec}s` : 'Done'}
          </span>
        )}
        {item.status === 'error' && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--dp-error)] bg-[var(--dp-error)]/10 px-1.5 py-0.5 rounded-full font-medium">
            <XCircle className="w-2.5 h-2.5" /> Failed
          </span>
        )}
      </div>
    </div>
  );
};

// ── File Change Card ──────────────────────────────────────────────
const FileChangeCard: React.FC<{ path: string; added: number; removed: number }> = ({ path, added, removed }) => {
  const filename = path.split(/[\\/]/).pop() || path;
  return (
    <div className="flex items-center gap-2 p-2.5 rounded-lg bg-white/3 border border-[var(--dp-border)] hover:border-[var(--dp-border-mid)] transition-colors group">
      <FileCode className="w-3.5 h-3.5 text-[var(--dp-accent)] shrink-0" />
      <span className="text-[11px] font-medium text-[var(--dp-text-primary)] truncate font-mono flex-1">{filename}</span>
      {added > 0 && <span className="text-[10px] text-[var(--dp-success)] font-mono font-semibold">+{added}</span>}
      {removed > 0 && <span className="text-[10px] text-[var(--dp-error)] font-mono font-semibold">−{removed}</span>}
      <button className="opacity-0 group-hover:opacity-100 transition-opacity px-2 py-0.5 text-[10px] font-semibold rounded-md bg-[var(--dp-accent)] text-white hover:opacity-90 cursor-pointer">
        Review
      </button>
    </div>
  );
};

// ── Goal Progress Card (real-time) ────────────────────────────────
interface GoalStep { id: string; label: string; status: 'done' | 'active' | 'pending'; }

const CurrentGoalCard: React.FC<{
  goal: string;
  steps: GoalStep[];
  isGenerating: boolean;
  onChangeGoal: () => void;
}> = ({ goal, steps, isGenerating, onChangeGoal }) => {
  const completedCount = steps.filter(s => s.status === 'done').length;
  const progressPct = steps.length > 0 ? Math.round((completedCount / steps.length) * 100) : 0;

  return (
    <div className="rounded-xl border border-[var(--dp-border)] overflow-hidden" style={{ background: 'var(--dp-bg-elevated)' }}>
      <div className="px-3 py-2 border-b border-[var(--dp-border)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-[var(--dp-accent-dim)] flex items-center justify-center">
            <Target className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
          </div>
          <span className="text-[11px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider">Current Goal</span>
        </div>
        {isGenerating && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--dp-accent)] animate-pulse-subtle">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--dp-accent)]" />
            Working...
          </span>
        )}
      </div>
      <div className="px-3 pt-2.5 pb-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[12px] font-semibold text-[var(--dp-text-bright)] leading-snug flex-1">{goal || 'No active task'}</p>
          <button
            onClick={onChangeGoal}
            className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-white/6 text-[var(--dp-text-secondary)] hover:bg-white/10 cursor-pointer transition-colors shrink-0"
          >
            Change
          </button>
        </div>
        {steps.length > 0 && (
          <>
            <div className="mt-2 mb-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] text-[var(--dp-text-muted)] font-mono">{completedCount}/{steps.length} steps</span>
                <span className="text-[9px] text-[var(--dp-accent)] font-mono font-semibold">{progressPct}%</span>
              </div>
              <div className="w-full h-1 bg-white/8 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${progressPct}%`, background: 'linear-gradient(90deg, var(--dp-accent) 0%, #60a5fa 100%)' }}
                />
              </div>
            </div>
            <div className="space-y-1.5 pb-2.5">
              {steps.map(step => (
                <div key={step.id} className="flex items-center gap-2">
                  {step.status === 'done' && (
                    <div className="w-4 h-4 rounded-full bg-[var(--dp-success)]/15 border border-[var(--dp-success)]/30 flex items-center justify-center shrink-0">
                      <Check className="w-2.5 h-2.5 text-[var(--dp-success)]" />
                    </div>
                  )}
                  {step.status === 'active' && (
                    <div className="w-4 h-4 rounded-full bg-[var(--dp-accent)]/15 border border-[var(--dp-accent)]/40 flex items-center justify-center shrink-0 animate-pulse-subtle">
                      <span className="w-1.5 h-1.5 rounded-full bg-[var(--dp-accent)]" />
                    </div>
                  )}
                  {step.status === 'pending' && (
                    <div className="w-4 h-4 rounded-full border border-white/10 flex items-center justify-center shrink-0">
                      <Circle className="w-2.5 h-2.5 text-[var(--dp-text-muted)]" />
                    </div>
                  )}
                  <span className={`text-[11px] ${
                    step.status === 'done'   ? 'text-[var(--dp-text-muted)] line-through' :
                    step.status === 'active' ? 'text-[var(--dp-text-bright)] font-medium' :
                    'text-[var(--dp-text-muted)]'
                  }`}>
                    {step.label}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// ── Main Component ────────────────────────────────────────────────
export const AiWorkspace: React.FC<AiWorkspaceProps> = ({
  messages,
  inputText,
  setInputText,
  onSendMessage,
  isGenerating,
  onCancelGeneration,
  mode,
  setMode,
  onConfirmTool,
  onConfirmPermission,
  statusMessage: _statusMessage,
  contextTokens: rawTokens = 0,
  contextPercentage: rawPercentage = 0,
  activeSessionId,
  onResumeSession,
}) => {
  const contextTokens = rawTokens ?? 0;
  const contextPercentage = rawPercentage ?? 0;
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});

  // Pull live data from AIContext
  const { liveToolCalls, liveFileChanges, currentGoal } = useAI();

  const handleToggleHunk = (msgId: string, hunkId: string, accepted: boolean) => {
    setHunkDecisions(prev => ({
      ...prev,
      [msgId]: { ...(prev[msgId] || {}), [hunkId]: accepted }
    }));
  };

  // Build real-time goal steps from tool calls
  const goalSteps: GoalStep[] = liveToolCalls.map((tc, i) => ({
    id: tc.id,
    label: tc.name + (tc.params?.path ? ` — ${String(tc.params.path).split(/[\\/]/).pop()}` : ''),
    status: tc.status === 'success' ? 'done' : tc.status === 'running' ? 'active' : 'pending'
  }));

  const [memories, setMemories] = useState<ProjectMemoryItem[]>([
    { id: 'm1', category: 'convention', title: '8px Spacing Grid', content: 'Always use 8px multiples for spacing.', enabled: true },
    { id: 'm2', category: 'architecture', title: 'Component Modularity', content: 'Keep components under 300 lines.', enabled: true },
  ]);

  // Context info (real token counts passed in)
  const contextInfo: ProjectContextInfo = {
    indexedFiles: 0,
    totalFiles: 0,
    architecture: 'Auto-detected',
    framework: 'Auto-detected',
    language: 'Auto-detected',
    database: 'Auto-detected',
    activeBranch: 'main',
    tokenUsage: typeof contextTokens === 'number' ? contextTokens : 0,
    tokenBudget: 128000,
  };

  const tabs: Array<{ id: Tab; label: string; icon: typeof MessageSquare }> = [
    { id: 'chat',    label: 'Chat',    icon: MessageSquare },
    { id: 'plan',    label: 'Plan',    icon: ListChecks },
    { id: 'history', label: 'History', icon: History },
    { id: 'context', label: 'Context', icon: Brain },
  ];

  return (
    <div
      className="h-full flex flex-col font-sans select-none overflow-hidden"
      style={{ background: 'var(--dp-bg-secondary)', borderLeft: '1px solid var(--dp-border)' }}
    >
      {/* ── Top Header ── */}
      <div
        className="px-3 pt-2.5 pb-0 shrink-0"
        style={{ borderBottom: '1px solid var(--dp-border)' }}
      >
        {/* Title row */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-[#7c6af0] to-[#4f8df5] flex items-center justify-center shadow-[0_0_10px_rgba(124,106,240,0.3)]">
              <Sparkles className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-[12px] font-bold text-[var(--dp-text-bright)] tracking-tight">AI Assistant</span>
            <span className="text-[8px] font-semibold text-[var(--dp-text-muted)] bg-white/6 px-1.5 py-0.5 rounded uppercase tracking-widest">BETA</span>
            {isGenerating && (
              <span className="flex items-center gap-1 text-[10px] text-[var(--dp-accent)] bg-[var(--dp-accent-dim)] px-2 py-0.5 rounded-full border border-[var(--dp-accent)]/20 font-medium animate-pulse">
                <Zap className="w-2.5 h-2.5" /> Active
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            <button
              title={`${typeof contextTokens === 'number' ? contextTokens.toLocaleString() : contextTokens} tokens used (${contextPercentage}%)`}
              className="flex items-center gap-1.5 px-2 py-0.5 rounded border text-[9px] font-mono transition-colors cursor-default"
              style={{
                background: contextPercentage >= 80
                  ? 'rgba(248,113,113,0.08)'
                  : contextPercentage >= 60
                  ? 'rgba(251,191,36,0.08)'
                  : 'rgba(255,255,255,0.04)',
                borderColor: contextPercentage >= 80
                  ? 'rgba(248,113,113,0.25)'
                  : contextPercentage >= 60
                  ? 'rgba(251,191,36,0.25)'
                  : 'var(--dp-border)',
                color: contextPercentage >= 80
                  ? 'var(--dp-error)'
                  : contextPercentage >= 60
                  ? 'var(--dp-warning)'
                  : 'var(--dp-text-muted)',
              }}
            >
              {typeof contextTokens === 'number' && contextTokens >= 1000
                ? `${(contextTokens / 1000).toFixed(1)}K`
                : String(contextTokens)} tokens
              {contextPercentage > 0 && <span className="opacity-60">({contextPercentage}%)</span>}
            </button>
            <button className="w-6 h-6 flex items-center justify-center rounded text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5 cursor-pointer transition-colors">
              <MoreHorizontal className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex items-center gap-0.5">
          {tabs.map(t => {
            const Icon = t.icon;
            const isActive = activeTab === t.id;
            const hasBadge = t.id === 'plan' && liveToolCalls.length > 0;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`
                  relative flex items-center gap-1.5 px-3 py-2 text-[11px] font-medium transition-all cursor-pointer
                  ${isActive
                    ? 'text-[var(--dp-text-bright)]'
                    : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-secondary)]'
                  }
                `}
              >
                {isActive && (
                  <span className="absolute bottom-0 left-1 right-1 h-[2px] bg-[var(--dp-accent)] rounded-t-full" />
                )}
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[var(--dp-accent)]' : ''}`} />
                {t.label}
                {hasBadge && (
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--dp-accent)] animate-pulse" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto min-h-0">

        {/* ── CHAT TAB ── */}
        {activeTab === 'chat' && (
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-y-auto min-h-0">
              <MessageList
                messages={messages}
                onConfirmTool={onConfirmTool || (() => {})}
                onConfirmPermission={onConfirmPermission}
                hunkDecisions={hunkDecisions}
                onToggleHunk={handleToggleHunk}
              />
            </div>

            {/* Sticky bottom area */}
            <div className="shrink-0 p-3 space-y-2" style={{ borderTop: '1px solid var(--dp-border)' }}>

              {/* Live tool calls strip — shows while agent is running */}
              {isGenerating && liveToolCalls.length > 0 && (
                <div className="space-y-1">
                  {liveToolCalls.slice(-3).map(tc => (
                    <div key={tc.id} className="flex items-center gap-2 px-2 py-1 rounded-lg bg-white/3 border border-[var(--dp-border)]">
                      <div className={`w-5 h-5 rounded flex items-center justify-center shrink-0 ${toolBgColor(tc.tool)}`}>
                        <ToolIcon type={tc.tool} />
                      </div>
                      <span className="text-[10px] text-[var(--dp-text-primary)] truncate flex-1">{tc.name}</span>
                      {tc.status === 'running' && <Loader2 className="w-3 h-3 text-[var(--dp-accent)] animate-spin shrink-0" />}
                      {tc.status === 'success' && <CheckCircle2 className="w-3 h-3 text-[var(--dp-success)] shrink-0" />}
                      {tc.status === 'error' && <XCircle className="w-3 h-3 text-[var(--dp-error)] shrink-0" />}
                    </div>
                  ))}
                </div>
              )}

              {/* File changes strip — shown once agent finishes */}
              {!isGenerating && liveFileChanges.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {liveFileChanges.map((fc, i) => (
                    <div key={i} className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/4 border border-[var(--dp-border)] text-[10px] font-mono">
                      <FileCode className="w-3 h-3 text-[var(--dp-accent)]" />
                      <span className="text-[var(--dp-text-primary)]">{fc.path.split(/[\\/]/).pop()}</span>
                      {fc.added > 0 && <span className="text-[var(--dp-success)]">+{fc.added}</span>}
                      {fc.removed > 0 && <span className="text-[var(--dp-error)]">−{fc.removed}</span>}
                    </div>
                  ))}
                </div>
              )}

              {/* Command Bar */}
              <AiCommandBar
                inputText={inputText}
                setInputText={setInputText}
                onSend={onSendMessage}
                isGenerating={isGenerating}
                onCancel={onCancelGeneration}
                mode={mode}
                setMode={setMode}
              />

              {/* Context Window Progress Bar */}
              {contextPercentage > 0 && (
                <div className="space-y-1">
                  <div className="relative h-1 bg-white/6 rounded-full overflow-hidden">
                    <div
                      className="absolute left-0 top-0 h-full rounded-full transition-all duration-700"
                      style={{
                        width: `${Math.min(100, contextPercentage)}%`,
                        background: contextPercentage >= 80
                          ? 'linear-gradient(90deg, #f87171 0%, #ef4444 100%)'
                          : contextPercentage >= 60
                          ? 'linear-gradient(90deg, #fbbf24 0%, #f59e0b 100%)'
                          : 'linear-gradient(90deg, var(--dp-accent) 0%, #60a5fa 100%)',
                        boxShadow: contextPercentage >= 80
                          ? '0 0 8px rgba(248,113,113,0.5)'
                          : contextPercentage >= 60
                          ? '0 0 8px rgba(251,191,36,0.4)'
                          : '0 0 8px rgba(124,106,240,0.4)',
                      }}
                    />
                  </div>
                  {contextPercentage >= 80 && (
                    <p className="text-[9px] text-[var(--dp-error)] font-medium flex items-center gap-1">
                      <span>⚠</span>
                      Context filling up — agent will auto-summarize soon.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── PLAN TAB (real-time) ── */}
        {activeTab === 'plan' && (
          <div className="p-3 space-y-3">
            <CurrentGoalCard
              goal={currentGoal}
              steps={goalSteps}
              isGenerating={isGenerating}
              onChangeGoal={() => {}}
            />

            {/* Real-time file changes */}
            {liveFileChanges.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider mb-2">File Changes</p>
                <div className="space-y-1.5">
                  {liveFileChanges.map((fc, i) => (
                    <FileChangeCard key={i} path={fc.path} added={fc.added} removed={fc.removed} />
                  ))}
                </div>
              </div>
            )}

            {/* Real-time tool calls */}
            {liveToolCalls.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider mb-2">Tool Calls</p>
                <div className="space-y-1.5">
                  {liveToolCalls.map(t => <LiveToolCard key={t.id} item={t} />)}
                </div>
              </div>
            )}

            {liveToolCalls.length === 0 && !isGenerating && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="w-10 h-10 rounded-xl bg-[var(--dp-accent-dim)] flex items-center justify-center mb-3">
                  <ListChecks className="w-5 h-5 text-[var(--dp-accent)]" />
                </div>
                <p className="text-[12px] font-semibold text-[var(--dp-text-primary)] mb-1">No active task</p>
                <p className="text-[11px] text-[var(--dp-text-muted)]">Tool calls and file changes will appear here in real-time when the agent runs.</p>
              </div>
            )}
          </div>
        )}

        {/* ── SESSION HISTORY TAB ── */}
        {activeTab === 'history' && (
          <SessionHistoryPanel
            activeSessionId={activeSessionId}
            onResume={onResumeSession || (async () => undefined)}
          />
        )}

        {/* ── CONTEXT TAB ── */}
        {activeTab === 'context' && (
          <div className="p-3 space-y-3">
            <ProjectContextPanel contextInfo={contextInfo} activeSessionId={activeSessionId} />
            <ProjectMemoryPanel
              memories={memories}
              onAddMemory={(item) => setMemories(prev => [{ ...item, id: `m_${Date.now()}` }, ...prev])}
              onToggleMemory={(id) => setMemories(prev => prev.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m))}
              onDeleteMemory={(id) => setMemories(prev => prev.filter(m => m.id !== id))}
            />
          </div>
        )}
      </div>
    </div>
  );
};
