import React, { useState } from 'react';
import {
  Sparkles, MessageSquare, ListChecks, Clock, Brain,
  FileCode, Check, Circle, Zap, Target,
  MoreHorizontal, History
} from 'lucide-react';
import type {
  ChatMessage,
  ToolExecutionItem,
  ProjectContextInfo, ProjectMemoryItem
} from '../../types/chat';
import { AiCommandBar } from './AiCommandBar';
import { ToolExecutionCard } from './ToolExecutionCard';
import { ProjectContextPanel } from './ProjectContextPanel';
import { ProjectMemoryPanel } from './ProjectMemoryPanel';
import { MessageList } from './MessageList';
import { SessionHistoryPanel } from './SessionHistoryPanel';

type Tab = 'chat' | 'plan' | 'context' | 'timeline' | 'history';

interface AiWorkspaceProps {
  messages: ChatMessage[];
  inputText: string;
  setInputText: (text: string) => void;
  onSendMessage: () => void;
  isGenerating: boolean;
  onCancelGeneration: () => void;
  mode: 'Ask' | 'Plan' | 'Agent';
  setMode: (mode: 'Ask' | 'Plan' | 'Agent') => void;
  onConfirmTool?: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  statusMessage?: string;
  contextTokens?: number | null;
  contextPercentage?: number | null;
  activeSessionId?: string;
  onResumeSession?: (sessionId: string) => Promise<void>;
}

// ── Goal Progress Step ────────────────────────────────────────────
interface GoalStep {
  id: string;
  label: string;
  status: 'done' | 'active' | 'pending';
}

// ── File Change Card ──────────────────────────────────────────────
const FileChangeCard: React.FC<{
  filename: string;
  added: number;
  removed: number;
}> = ({ filename, added, removed }) => (
  <div className="flex items-center justify-between p-2.5 rounded-lg bg-white/3 border border-[var(--dp-border)] hover:border-[var(--dp-border-mid)] transition-colors group">
    <div className="flex items-center gap-2 min-w-0">
      <FileCode className="w-3.5 h-3.5 text-[var(--dp-accent)] shrink-0" />
      <span className="text-[11px] font-medium text-[var(--dp-text-primary)] truncate font-mono">{filename}</span>
      <span className="text-[10px] text-[var(--dp-success)] font-mono font-semibold">+{added}</span>
      <span className="text-[10px] text-[var(--dp-error)] font-mono font-semibold">−{removed}</span>
    </div>
    <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
      <button className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-[var(--dp-accent)] text-white hover:opacity-90 cursor-pointer transition-opacity">
        Review Diff
      </button>
      <button className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-white/8 text-[var(--dp-text-secondary)] hover:bg-white/12 cursor-pointer transition-colors">
        Open File
      </button>
    </div>
  </div>
);




// ── Current Goal Card ─────────────────────────────────────────────
const CurrentGoalCard: React.FC<{
  goal: string;
  steps: GoalStep[];
  isGenerating: boolean;
  onChangeGoal: () => void;
}> = ({ goal, steps, isGenerating, onChangeGoal }) => {
  const completedCount = steps.filter(s => s.status === 'done').length;
  const progressPct = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="rounded-xl border border-[var(--dp-border)] overflow-hidden" style={{ background: 'var(--dp-bg-elevated)' }}>
      {/* Goal header */}
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

      {/* Goal text */}
      <div className="px-3 pt-2.5 pb-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[12px] font-semibold text-[var(--dp-text-bright)] leading-snug flex-1">{goal}</p>
          <button
            onClick={onChangeGoal}
            className="px-2 py-0.5 text-[10px] font-semibold rounded-md bg-white/6 text-[var(--dp-text-secondary)] hover:bg-white/10 cursor-pointer transition-colors shrink-0"
          >
            Change
          </button>
        </div>

        {/* Progress bar */}
        <div className="mt-2 mb-2.5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] text-[var(--dp-text-muted)] font-mono">{completedCount}/{steps.length} steps</span>
            <span className="text-[9px] text-[var(--dp-accent)] font-mono font-semibold">{progressPct}%</span>
          </div>
          <div className="w-full h-1 bg-white/8 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progressPct}%`,
                background: 'linear-gradient(90deg, var(--dp-accent) 0%, #60a5fa 100%)',
              }}
            />
          </div>
        </div>

        {/* Steps */}
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
  const [currentGoal] = useState('Build and implement a modern Login screen with validation');

  const handleToggleHunk = (msgId: string, hunkId: string, accepted: boolean) => {
    setHunkDecisions(prev => ({
      ...prev,
      [msgId]: { ...(prev[msgId] || {}), [hunkId]: accepted }
    }));
  };

  const goalSteps: GoalStep[] = [
    { id: '1', label: 'Understand project structure',    status: 'done' },
    { id: '2', label: 'Review existing components',      status: 'done' },
    { id: '3', label: 'Create Login component',          status: 'done' },
    { id: '4', label: 'Add validation logic',            status: isGenerating ? 'active' : 'done' },
    { id: '5', label: 'Style the UI',                    status: isGenerating ? 'pending' : 'done' },
    { id: '6', label: 'Test the implementation',         status: 'pending' },
  ];

  const tools: ToolExecutionItem[] = [
    { id: 'tc1', tool: 'file_read', name: 'Read package.json',        params: { path: 'package.json' }, status: 'success', durationMs: 120 },
    { id: 'tc2', tool: 'search',    name: 'Search for useAuth hook',  params: { query: 'useAuth' },     status: 'success', durationMs: 340 },
  ];

  const contextInfo: ProjectContextInfo = {
    indexedFiles:  142,
    totalFiles:    156,
    architecture:  'Modular React + FastAPI',
    framework:     'React / Vite',
    language:      'TypeScript / Python',
    database:      'SQLite / Redis',
    activeBranch:  'main',
    tokenUsage:    contextTokens || 14200,
    tokenBudget:   128000,
  };

  const [memories, setMemories] = useState<ProjectMemoryItem[]>([
    { id: 'm1', category: 'convention', title: '8px Spacing Grid', content: 'Always use 8px multiples for spacing.', enabled: true },
    { id: 'm2', category: 'architecture', title: 'Component Modularity', content: 'Keep components under 300 lines.', enabled: true },
  ]);

  const tabs: Array<{ id: Tab; label: string; icon: typeof MessageSquare }> = [
    { id: 'chat',     label: 'Chat',     icon: MessageSquare },
    { id: 'plan',     label: 'Plan',     icon: ListChecks },
    { id: 'history',  label: 'History',  icon: History },
    { id: 'context',  label: 'Context',  icon: Brain },
    { id: 'timeline', label: 'Timeline', icon: Clock },
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
            {/* Context bar pill */}
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
            {/* Scrollable messages */}
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

              {/* Current Goal card — only when Agent mode is actively generating */}
              {isGenerating && mode === 'Agent' && (
                <CurrentGoalCard
                  goal={currentGoal}
                  steps={goalSteps}
                  isGenerating={isGenerating}
                  onChangeGoal={() => {}}
                />
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

        {/* ── PLAN TAB ── */}
        {activeTab === 'plan' && (
          <div className="p-3 space-y-3">
            <CurrentGoalCard
              goal={currentGoal}
              steps={goalSteps}
              isGenerating={isGenerating}
              onChangeGoal={() => {}}
            />

            {/* File changes section */}
            <div>
              <p className="text-[10px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider mb-2">File Changes</p>
              <div className="space-y-1.5">
                <FileChangeCard filename="Login.jsx" added={156} removed={2} />
                <FileChangeCard filename="App.jsx" added={3} removed={1} />
              </div>
            </div>

            {/* Tool calls */}
            <div>
              <p className="text-[10px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider mb-2">Tool Calls</p>
              <div className="space-y-1.5">
                {tools.map(t => <ToolExecutionCard key={t.id} toolItem={t} />)}
              </div>
            </div>
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
            <ProjectContextPanel contextInfo={contextInfo} />
            <ProjectMemoryPanel
              memories={memories}
              onAddMemory={(item) => setMemories(prev => [{ ...item, id: `m_${Date.now()}` }, ...prev])}
              onToggleMemory={(id) => setMemories(prev => prev.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m))}
              onDeleteMemory={(id) => setMemories(prev => prev.filter(m => m.id !== id))}
            />
          </div>
        )}

        {/* ── TIMELINE TAB ── */}
        {activeTab === 'timeline' && (
          <div className="p-3">
            <div className="relative pl-6 space-y-2 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-[2px] before:bg-gradient-to-b before:from-[var(--dp-accent)] before:to-transparent">
              {[
                { label: 'Initialized AI Workspace Session',          time: '16:45:00', status: 'done' },
                { label: 'Indexed project dependencies (package.json)', time: '16:45:02', status: 'done' },
                { label: 'Analyzed component architecture',             time: '16:45:05', status: 'done' },
                { label: 'Generating Login component',                 time: '16:45:08', status: isGenerating ? 'active' : 'done' },
              ].map((step, i) => (
                <div key={i} className="relative flex items-center justify-between p-2.5 rounded-lg bg-white/3 border border-[var(--dp-border)] hover:border-[var(--dp-border-mid)] transition-colors">
                  {/* Timeline dot */}
                  <span
                    className={`absolute -left-[22px] w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      step.status === 'done'
                        ? 'border-[var(--dp-success)] bg-[var(--dp-success)]/10'
                        : 'border-[var(--dp-accent)] bg-[var(--dp-accent)]/10 animate-pulse-subtle'
                    }`}
                  >
                    {step.status === 'done'
                      ? <Check className="w-2 h-2 text-[var(--dp-success)]" />
                      : <span className="w-1.5 h-1.5 rounded-full bg-[var(--dp-accent)]" />
                    }
                  </span>
                  <span className="text-[11px] text-[var(--dp-text-primary)] font-medium">{step.label}</span>
                  <span className="text-[9px] text-[var(--dp-text-muted)] font-mono">{step.time}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
