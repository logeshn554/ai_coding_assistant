import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Settings,
  Sparkles,
  Terminal,
  Check,
  Plus,
  ChevronDown,
  FileText,
  Database,
  Globe,
  FileCode,
  AlertCircle
} from 'lucide-react';

import type { ChatMessage, AgentState, Session, ProcessEntry, ChatMode } from '../types/chat';
import { MessageList } from './chat/MessageList';
import { AgentStatusBar } from './chat/AgentStatusBar';

import { useUI } from '../core/ui/UIContext';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (text: string, mode: ChatMode, autoApply: boolean) => void;
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  isGenerating: boolean;
  statusMessage: string | null;
  activeProfileName: string;
  onOpenSettings: () => void;
  onCancelGeneration: () => void;

  // Collaboration & Agent States
  activeAgent?: string | null;
  activeTask?: string | null;
  agents?: AgentState[];
  collaborationLog?: string[];
  subtasks?: any[];
  contextTokens?: string;
  contextPercentage?: number;
  totalCostUsd?: number;

  // Background running processes
  activeProcesses?: ProcessEntry[];
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  onStopProcess?: (processId?: string) => void;

  // Sessions / Chat History
  sessions?: Session[];
  activeSessionId?: string;
  onSelectSession?: (sessionId: string) => void;
  onDeleteSession?: (sessionId: string) => void;
  onNewSession?: () => void;
  onRenameSession?: (sessionId: string, newTitle: string) => void;

  // Git & File Selection
  gitChangesList?: any[];
  onGitAction?: (action: any, files?: any) => any;
  onSelectFile?: (filePath: any) => any;
  currentIntent?: string | null;
}

const MENTION_OPTIONS = [
  { trigger: '@file', label: '@file', description: 'Active file context' },
  { trigger: '@workspace', label: '@workspace', description: 'Full repository code index' },
  { trigger: '@terminal', label: '@terminal', description: 'Terminal buffer & output' },
  { trigger: '@git', label: '@git', description: 'Git diff & commit history' },
  { trigger: '@problems', label: '@problems', description: 'Compiler & linter errors' },
];

const SLASH_OPTIONS = [
  { trigger: '/goal', label: '/goal', description: 'Run autonomous agent until goal is achieved' },
  { trigger: '/schedule', label: '/schedule', description: 'Schedule recurring timer or cron task' },
  { trigger: '/grill-me', label: '/grill-me', description: 'Interactive plan interview & design review' },
  { trigger: '/learn', label: '/learn', description: 'Persist preference or coding rule to memory' },
  { trigger: '/review', label: '/review', description: 'Perform code quality & security audit' },
  { trigger: '/test', label: '/test', description: 'Run test suite and report results' },
  { trigger: '/clear', label: '/clear', description: 'Reset chat conversation state' },
];

export default function ChatPanel({
  messages,
  onSendMessage,
  onConfirmTool,
  isGenerating,
  statusMessage,
  activeProfileName,
  onOpenSettings,
  onCancelGeneration,
  onConfirmPermission,
  activeAgent: _activeAgent = null,
  activeTask: _activeTask = null,
  agents = [],
  contextTokens = '0',
  contextPercentage = 0,
  totalCostUsd: _totalCostUsd = 0.0,
  activeProcesses = [],
  onConfirmPortConflict,
  onStopProcess,
  sessions = [],
  activeSessionId,
  onSelectSession,
  onDeleteSession: _onDeleteSession,
  onNewSession,
  onRenameSession: _onRenameSession,
  currentIntent = null
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<'Auto' | 'Ask' | 'Plan' | 'Agent'>('Auto');
  const [autoApply, setAutoApply] = useState(true);
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});
  const isProcessRunning = activeProcesses.some(p => p.status === 'running' || p.status === 'starting');
  const [showHistoryDropdown, setShowHistoryDropdown] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { setSecondarySidebarTab, setIsAiPanelOpen } = useUI();

  // Tool attachment active states
  const [fileContextActive, setFileContextActive] = useState(true);
  const [terminalContextActive, setTerminalContextActive] = useState(false);
  const [dbContextActive, setDbContextActive] = useState(true);
  const [browserContextActive, setBrowserContextActive] = useState(false);

  // Autocomplete menu state
  const [showMentions, setShowMentions] = useState(false);
  const [showSlashMenu, setShowSlashMenu] = useState(false);

  // Derive current session title
  const currentSession = sessions.find(s => s.id === activeSessionId);
  const sessionTitle = currentSession?.title || 'Current Session';


  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating, statusMessage]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);

    const lastWord = val.split(/\s+/).pop() || '';
    if (lastWord.startsWith('@')) {
      setShowMentions(true);
      setShowSlashMenu(false);
    } else if (lastWord.startsWith('/')) {
      setShowSlashMenu(true);
      setShowMentions(false);
    } else {
      setShowMentions(false);
      setShowSlashMenu(false);
    }
  };

  const insertMentionOrSlash = (itemTrigger: string) => {
    const words = input.split(/\s+/);
    words.pop();
    const newText = [...words, itemTrigger].join(' ').trim() + ' ';
    setInput(newText);
    setShowMentions(false);
    setShowSlashMenu(false);
    textareaRef.current?.focus();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isGenerating) return;
    onSendMessage(input.trim(), mode, autoApply);
    setInput('');
    setShowMentions(false);
    setShowSlashMenu(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.key === 'Enter' && (e.ctrlKey || e.metaKey)) || (e.key === 'Enter' && !e.shiftKey)) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleToggleHunk = (msgId: string, hunkId: string, accepted: boolean) => {
    setHunkDecisions(prev => ({
      ...prev,
      [msgId]: {
        ...(prev[msgId] || {}),
        [hunkId]: accepted
      }
    }));
  };

  const handleOpenReviewPanel = () => {
    setSecondarySidebarTab('review');
    setIsAiPanelOpen(true);
  };

  const showTypingIndicator = isGenerating;

  return (
    <div className="flex flex-col h-full text-[#ececec] select-none overflow-hidden font-sans" style={{ background: '#2b2b2b', borderLeft: '1px solid #515151' }}>

      {/* ── 1. Top Header Bar ── */}
      <div className="flex items-center justify-between px-3 py-2 shrink-0" style={{ background: '#3c3f41', borderBottom: '1px solid #515151' }}>
        <div className="relative flex items-center gap-2 min-w-0">
          <Sparkles className="w-4 h-4 shrink-0" style={{ color: '#4C8DFF' }} />
          <button
            onClick={() => setShowHistoryDropdown(!showHistoryDropdown)}
            className="flex items-center gap-1.5 text-xs font-semibold truncate max-w-[170px] px-2 py-1 rounded-md transition-colors"
            style={{ color: '#DFE1E5', background: '#3B3D42', border: '1px solid #393B40' }}
          >
            <span className="truncate">{sessionTitle}</span>
            <ChevronDown className="w-3.5 h-3.5 shrink-0" style={{ color: '#6F737A' }} />
          </button>

          {/* Session History Dropdown */}
          {showHistoryDropdown && (
            <div className="absolute top-9 left-0 w-64 rounded-xl shadow-2xl z-50 p-1.5 space-y-1" style={{ background: '#2B2D30', border: '1px solid #393B40', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
              <div className="flex items-center justify-between px-2 py-1" style={{ borderBottom: '1px solid #393B40' }}>
                <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: '#6F737A' }}>Sessions</span>
                <button
                  onClick={() => { onNewSession?.(); setShowHistoryDropdown(false); }}
                  className="flex items-center gap-1 text-[11px] font-semibold transition-colors"
                  style={{ color: '#4C8DFF' }}
                >
                  <Plus className="w-3 h-3" /> New
                </button>
              </div>
              <div className="max-h-48 overflow-y-auto space-y-0.5 pr-0.5">
                {sessions.map(s => (
                  <div
                    key={s.id}
                    onClick={() => { onSelectSession?.(s.id); setShowHistoryDropdown(false); }}
                    className="flex items-center justify-between px-2 py-1.5 rounded-lg text-xs cursor-pointer transition-colors"
                    style={s.id === activeSessionId
                      ? { background: 'rgba(76,141,255,0.18)', color: '#DFE1E5', fontWeight: 600 }
                      : { color: '#ececec' }
                    }
                    onMouseEnter={e => { if (s.id !== activeSessionId) (e.currentTarget as HTMLElement).style.background = '#3B3D42'; }}
                    onMouseLeave={e => { if (s.id !== activeSessionId) (e.currentTarget as HTMLElement).style.background = ''; }}
                  >
                    <span className="truncate max-w-[170px]">{s.title || 'Untitled Session'}</span>
                    {s.id === activeSessionId && <Check className="w-3 h-3 shrink-0" style={{ color: '#4C8DFF' }} />}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={onNewSession}
            className="p-1 rounded transition-colors"
            style={{ color: '#6F737A' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#3B3D42'; (e.currentTarget as HTMLElement).style.color = '#DFE1E5'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = ''; (e.currentTarget as HTMLElement).style.color = '#6F737A'; }}
            title="New Chat Session"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onOpenSettings}
            className="p-1 rounded transition-colors"
            style={{ color: '#6F737A' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#3B3D42'; (e.currentTarget as HTMLElement).style.color = '#DFE1E5'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = ''; (e.currentTarget as HTMLElement).style.color = '#6F737A'; }}
            title="Settings & Models"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── 2. Message List Stream ── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0" style={{ background: '#1E1F22' }}>
        <MessageList
          messages={messages}
          onConfirmTool={onConfirmTool}
          onConfirmPermission={onConfirmPermission}
          onConfirmPortConflict={onConfirmPortConflict}
          hunkDecisions={hunkDecisions}
          onToggleHunk={handleToggleHunk}
          isGenerating={isGenerating}
        />

        {/* Agent Failed Alert Banner */}
        {agents && agents.some(ag => ag.status === 'error') && (
          <div className="mx-4 my-2 p-3.5 rounded-xl border border-red-500/30 bg-red-950/40 text-red-200 text-xs flex items-center justify-between gap-3 animate-slide-up" style={{ maxWidth: '760px', margin: '10px auto' }}>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 animate-pulse" />
              <span className="font-semibold">Agent execution failed</span>
            </div>
            <div className="font-mono text-[10px] text-red-300">
              One or more agents encountered an error. Check logs for details.
            </div>
          </div>
        )}

        {/* Streaming Thinking Indicator */}
        {showTypingIndicator && (
          <div className="flex gap-3 items-start px-4 pb-4 animate-slide-up" style={{ maxWidth: '760px', margin: '0 auto' }}>
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5"
              style={{ background: 'rgba(76,141,255,0.10)', border: '1px solid rgba(76,141,255,0.25)' }}
            >
              <Sparkles className="w-3.5 h-3.5 animate-pulse" style={{ color: '#4C8DFF' }} />
            </div>
            <div className="flex items-center gap-2.5 py-2">
              <span className="flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: '#4C8DFF', animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: '#4C8DFF', animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: '#4C8DFF', animationDelay: '300ms' }} />
              </span>
              <span className="text-[13px]" style={{ color: '#6F737A' }}>
                {statusMessage || 'Working...'}
              </span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* ── 3. Input Area & Rich Action Controls ── */}
      <div className="px-3 pt-2 pb-3 shrink-0 font-sans space-y-2 relative" style={{ background: '#1E1F22', borderTop: '1px solid #393B40' }}>

        {/* Mention (@) Autocomplete Popover */}
        {showMentions && (
          <div className="absolute bottom-full left-3 mb-2 w-64 rounded-xl shadow-2xl z-50 p-1 space-y-0.5 animate-slide-up" style={{ background: '#2B2D30', border: '1px solid #393B40', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
            <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider" style={{ color: '#4C8DFF', borderBottom: '1px solid #393B40' }}>
              Mention Context
            </div>
            {MENTION_OPTIONS.map((item) => (
              <button
                key={item.trigger}
                type="button"
                onClick={() => insertMentionOrSlash(item.trigger)}
                className="w-full text-left px-2.5 py-1.5 rounded-lg transition-colors flex flex-col gap-0.5 cursor-pointer"
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'rgba(76,141,255,0.12)'}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = ''}
              >
                <span className="font-mono font-bold text-xs" style={{ color: '#DFE1E5' }}>{item.label}</span>
                <span className="text-[10px]" style={{ color: '#6F737A' }}>{item.description}</span>
              </button>
            ))}
          </div>
        )}

        {/* Slash (/) Actions Autocomplete Popover */}
        {showSlashMenu && (
          <div className="absolute bottom-full left-3 mb-2 w-72 rounded-xl shadow-2xl z-50 p-1 space-y-0.5 animate-slide-up" style={{ background: '#2B2D30', border: '1px solid #393B40', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
            <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider flex items-center justify-between" style={{ color: '#4C8DFF', borderBottom: '1px solid #393B40' }}>
              <span>Slash Actions</span>
              <span className="text-[9px] font-mono" style={{ color: '#6F737A' }}>Press Tab or Click</span>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-0.5">
              {SLASH_OPTIONS.map((item) => (
                <button
                  key={item.trigger}
                  type="button"
                  onClick={() => insertMentionOrSlash(item.trigger)}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg transition-colors flex flex-col gap-0.5 cursor-pointer"
                  onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'rgba(76,141,255,0.12)'}
                  onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = ''}
                >
                  <span className="font-mono font-bold text-xs" style={{ color: '#DFE1E5' }}>{item.label}</span>
                  <span className="text-[10px]" style={{ color: '#6F737A' }}>{item.description}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Agent StatusBar */}
        <AgentStatusBar
          agents={agents}
          contextPercentage={contextPercentage}
          contextTokens={contextTokens}
          activeProfileName={activeProfileName}
          onOpenSettings={onOpenSettings}
          intent={currentIntent}
          totalCostUsd={_totalCostUsd}
        />

        {/* Quick prompt suggestions */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 px-0.5 text-[10.5px] no-scrollbar">
          <button
            type="button"
            onClick={() => setInput('/review Perform security & code review on active file')}
            className="px-2 py-0.5 rounded-md shrink-0 cursor-pointer transition-colors"
            style={{ background: '#2B2D30', color: '#9DA0A8', border: '1px solid #393B40', borderRadius: '4px' }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#3B3D42'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = '#2B2D30'}
          >

            Review Code
          </button>
          <button
            type="button"
            onClick={() => setInput('Scan workspace for potential bugs and performance risks')}
            className="px-2 py-0.5 rounded-md shrink-0 cursor-pointer transition-colors"
            style={{ background: '#2B2D30', color: '#9DA0A8', border: '1px solid #393B40', borderRadius: '4px' }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#3B3D42'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = '#2B2D30'}
          >
            Scan Bugs
          </button>
          <button
            type="button"
            onClick={() => setInput('Generate unit tests covering happy path and edge cases')}
            className="px-2 py-0.5 rounded-md shrink-0 cursor-pointer transition-colors"
            style={{ background: '#2B2D30', color: '#9DA0A8', border: '1px solid #393B40', borderRadius: '4px' }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#3B3D42'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = '#2B2D30'}
          >
            Generate Tests
          </button>
          <button
            type="button"
            onClick={() => setInput('/goal Refactor active file for high performance and clean architecture')}
            className="px-2 py-0.5 rounded-md shrink-0 cursor-pointer transition-colors"
            style={{ background: '#2B2D30', color: '#9DA0A8', border: '1px solid #393B40', borderRadius: '4px' }}
            onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#3B3D42'}
            onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = '#2B2D30'}
          >
            Refactor
          </button>
        </div>

        {/* Input Box Container */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-2 p-3 rounded-2xl" style={{ background: '#2B2D30', border: '1px solid #393B40', boxShadow: '0 4px 12px rgba(0,0,0,0.5)' }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything, @ to mention, / for actions"
            rows={2}
            className="w-full max-h-36 min-h-[44px] bg-transparent text-[13.5px] focus:outline-none resize-none font-sans scrollbar-none p-0"
            style={{ color: '#DFE1E5' }}
          />

          {/* Action Toolbar Row */}
          <div className="flex items-center justify-between pt-2 select-none" style={{ borderTop: '1px solid #393B40' }}>

            {/* Left Tools */}
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setFileContextActive(!fileContextActive)}
                className="relative p-1.5 rounded-lg transition-colors cursor-pointer"
                style={fileContextActive
                  ? { background: 'rgba(76,141,255,0.15)', color: '#4C8DFF', border: '1px solid rgba(76,141,255,0.35)' }
                  : { color: '#6F737A' }
                }
                title="Toggle active document context"
              >
                <FileText className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setTerminalContextActive(!terminalContextActive)}
                className="relative p-1.5 rounded-lg transition-colors cursor-pointer"
                style={terminalContextActive
                  ? { background: 'rgba(76,141,255,0.15)', color: '#4C8DFF', border: '1px solid rgba(76,141,255,0.35)' }
                  : { color: '#6F737A' }
                }
                title="Toggle terminal buffer context"
              >
                <Terminal className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setDbContextActive(!dbContextActive)}
                className="relative p-1.5 rounded-lg transition-colors cursor-pointer"
                style={dbContextActive
                  ? { background: 'rgba(76,141,255,0.15)', color: '#4C8DFF', border: '1px solid rgba(76,141,255,0.35)' }
                  : { color: '#6F737A' }
                }
                title="Toggle database schema context"
              >
                <Database className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setBrowserContextActive(!browserContextActive)}
                className="relative p-1.5 rounded-lg transition-colors cursor-pointer"
                style={browserContextActive
                  ? { background: 'rgba(76,141,255,0.15)', color: '#4C8DFF', border: '1px solid rgba(76,141,255,0.35)' }
                  : { color: '#6F737A' }
                }
                title="Toggle browser preview context"
              >
                <Globe className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={handleOpenReviewPanel}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer transition-colors"
                style={{ background: '#2B2D30', color: '#9DA0A8', border: '1px solid #393B40', borderRadius: '4px' }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#3B3D42'}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = '#3B3D42'}
                title="Open Review Changes Panel"
              >
                <FileCode className="w-3.5 h-3.5" style={{ color: '#4C8DFF' }} />
                <span>Review Changes</span>
              </button>

              {isProcessRunning && (
                <button
                  type="button"
                  onClick={() => onStopProcess?.()}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10.5px] font-semibold cursor-pointer transition-colors"
                  style={{ background: 'rgba(255,107,107,0.12)', color: '#FF6B6B', border: '1px solid rgba(255,107,107,0.30)' }}
                  title="Click to stop running background server or process"
                >
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span>Process</span>
                  <span className="text-[9px] font-bold text-white px-1 rounded ml-0.5" style={{ background: '#FF6B6B' }}>Stop</span>
                </button>
              )}
            </div>

            {/* Right Controls */}
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-[11px] font-medium cursor-pointer select-none" style={{ color: '#6F737A' }}>
                <input
                  type="checkbox"
                  checked={autoApply}
                  onChange={(e) => setAutoApply(e.target.checked)}
                  className="rounded w-3 h-3 cursor-pointer"
                  style={{ accentColor: '#4b6eaf' }}
                />
                <span>Auto Apply</span>
              </label>

              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                className="px-2 py-1 rounded-lg text-[11px] font-semibold focus:outline-none cursor-pointer"
                style={{ background: '#2B2D30', border: '1px solid #393B40', color: '#DFE1E5', borderRadius: '4px' }}
              >
                <option value="Auto">Auto</option>
                <option value="Ask">Ask</option>
                <option value="Plan">Plan</option>
                <option value="Agent">Agent</option>
              </select>



              {isGenerating && !input.trim() ? (
                <button
                  type="button"
                  onClick={onCancelGeneration}
                  className="p-1.5 rounded-lg cursor-pointer transition-all"
                  style={{ background: 'rgba(255,107,107,0.12)', color: '#FF6B6B', border: '1px solid rgba(255,107,107,0.30)', borderRadius: '4px' }}
                  title="Stop generating"
                >
                  <span className="w-3.5 h-3.5 flex items-center justify-center font-bold text-[10px]">■</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="p-1.5 rounded-lg cursor-pointer disabled:cursor-not-allowed transition-all"
                  style={input.trim()
                    ? { background: '#4C8DFF', color: '#fff', borderRadius: '4px' }
                    : { background: '#2B2D30', color: '#6F737A', borderRadius: '4px' }
                  }
                  title="Send message (Enter)"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </form>
      </div>


    </div>
  );
}