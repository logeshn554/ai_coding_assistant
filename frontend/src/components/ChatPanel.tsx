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
  FileCode
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
  onRenameSession: _onRenameSession
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
    <div className="flex flex-col h-full bg-[#0d0e15] text-zinc-200 select-none overflow-hidden font-sans border-l border-zinc-800/60">

      {/* ── 1. Top Header Bar ── */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/80 bg-[#11131c] shrink-0">
        <div className="relative flex items-center gap-2 min-w-0">
          <Sparkles className="w-4 h-4 text-violet-400 shrink-0" />
          <button
            onClick={() => setShowHistoryDropdown(!showHistoryDropdown)}
            className="flex items-center gap-1.5 text-xs font-semibold text-zinc-100 hover:text-white truncate max-w-[170px] bg-zinc-900/60 hover:bg-zinc-800/60 px-2 py-1 rounded-md border border-zinc-800 transition-colors"
          >
            <span className="truncate">{sessionTitle}</span>
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
          </button>

          {/* Session History Dropdown */}
          {showHistoryDropdown && (
            <div className="absolute top-9 left-0 w-64 bg-[#141622] border border-zinc-800 rounded-lg shadow-xl z-50 p-1.5 space-y-1">
              <div className="flex items-center justify-between px-2 py-1 border-b border-zinc-800">
                <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">Sessions</span>
                <button
                  onClick={() => { onNewSession?.(); setShowHistoryDropdown(false); }}
                  className="flex items-center gap-1 text-[11px] text-violet-400 hover:text-violet-300 font-semibold"
                >
                  <Plus className="w-3 h-3" /> New
                </button>
              </div>
              <div className="max-h-48 overflow-y-auto space-y-0.5 pr-0.5">
                {sessions.map(s => (
                  <div
                    key={s.id}
                    onClick={() => { onSelectSession?.(s.id); setShowHistoryDropdown(false); }}
                    className={`flex items-center justify-between px-2 py-1.5 rounded text-xs cursor-pointer ${s.id === activeSessionId ? 'bg-violet-600/20 text-violet-300 font-medium' : 'hover:bg-zinc-800/60 text-zinc-300'}`}
                  >
                    <span className="truncate max-w-[170px]">{s.title || 'Untitled Session'}</span>
                    {s.id === activeSessionId && <Check className="w-3 h-3 text-violet-400 shrink-0" />}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={onNewSession}
            className="p-1 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 rounded transition-colors"
            title="New Chat Session"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onOpenSettings}
            className="p-1 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 rounded transition-colors"
            title="Settings & Models"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── 2. Message List Stream ── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
        <MessageList
          messages={messages}
          onConfirmTool={onConfirmTool}
          onConfirmPermission={onConfirmPermission}
          onConfirmPortConflict={onConfirmPortConflict}
          hunkDecisions={hunkDecisions}
          onToggleHunk={handleToggleHunk}
        />

        {/* Streaming Thinking Indicator */}
        {showTypingIndicator && (
          <div className="flex gap-2.5 max-w-[95%] items-start select-none px-4 mb-3 animate-slide-up">
            <div className="w-7 h-7 rounded-md bg-zinc-900 border border-zinc-800 text-violet-400 shrink-0 flex items-center justify-center font-bold">
              <Sparkles className="w-4 h-4 text-violet-400 animate-pulse" />
            </div>
            <div className="flex flex-col items-start max-w-[calc(100%-2.25rem)]">
              <div className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-2 shadow-md">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
                </span>
                <span className="text-[11.5px] text-zinc-300 font-medium font-sans">
                  {statusMessage || 'Working...'}
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* ── 3. Input Area & Rich Action Controls ── */}
      <div className="p-2.5 border-t border-zinc-800/80 bg-[#11131c] shrink-0 font-sans space-y-2 relative">

        {/* Mention (@) Autocomplete Popover */}
        {showMentions && (
          <div className="absolute bottom-full left-3 mb-2 w-64 bg-[#161824] border border-zinc-700/80 rounded-xl shadow-2xl z-50 p-1 space-y-0.5 animate-slide-up">
            <div className="px-2 py-1 text-[10px] font-bold text-violet-400 uppercase tracking-wider border-b border-zinc-800">
              Mention Context
            </div>
            {MENTION_OPTIONS.map((item) => (
              <button
                key={item.trigger}
                type="button"
                onClick={() => insertMentionOrSlash(item.trigger)}
                className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-violet-600/20 hover:text-violet-200 transition-colors flex flex-col gap-0.5 cursor-pointer"
              >
                <span className="font-mono font-bold text-xs text-zinc-100">{item.label}</span>
                <span className="text-[10px] text-zinc-400">{item.description}</span>
              </button>
            ))}
          </div>
        )}

        {/* Slash (/) Actions Autocomplete Popover */}
        {showSlashMenu && (
          <div className="absolute bottom-full left-3 mb-2 w-72 bg-[#161824] border border-zinc-700/80 rounded-xl shadow-2xl z-50 p-1 space-y-0.5 animate-slide-up">
            <div className="px-2 py-1 text-[10px] font-bold text-violet-400 uppercase tracking-wider border-b border-zinc-800 flex items-center justify-between">
              <span>Slash Actions</span>
              <span className="text-[9px] text-zinc-500 font-mono">Press Tab or Click</span>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-0.5">
              {SLASH_OPTIONS.map((item) => (
                <button
                  key={item.trigger}
                  type="button"
                  onClick={() => insertMentionOrSlash(item.trigger)}
                  className="w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-violet-600/20 hover:text-violet-200 transition-colors flex flex-col gap-0.5 cursor-pointer"
                >
                  <span className="font-mono font-bold text-xs text-zinc-100">{item.label}</span>
                  <span className="text-[10px] text-zinc-400">{item.description}</span>
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
        />

        {/* Quick prompt suggestions */}
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1 px-0.5 text-[10.5px]">
          <button
            type="button"
            onClick={() => setInput('/review Perform security & code review on active file')}
            className="px-2 py-0.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-lg shrink-0 cursor-pointer transition-colors"
          >
            🔍 Review Code
          </button>
          <button
            type="button"
            onClick={() => setInput('Scan workspace for potential bugs and performance risks')}
            className="px-2 py-0.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-lg shrink-0 cursor-pointer transition-colors"
          >
            🐛 Scan Bugs
          </button>
          <button
            type="button"
            onClick={() => setInput('Generate unit tests covering happy path and edge cases')}
            className="px-2 py-0.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-lg shrink-0 cursor-pointer transition-colors"
          >
            🧪 Generate Tests
          </button>
          <button
            type="button"
            onClick={() => setInput('/goal Refactor active file for high performance and clean architecture')}
            className="px-2 py-0.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-lg shrink-0 cursor-pointer transition-colors"
          >
            ⚡ Refactor
          </button>
        </div>

        {/* Input Box Container */}
        <form onSubmit={handleSubmit} className="bg-zinc-950 border border-zinc-800 rounded-xl p-2.5 flex flex-col gap-2.5 focus-within:border-violet-500/60 shadow-inner">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything, @ to mention, / for actions"
            rows={2}
            className="w-full max-h-32 min-h-[42px] bg-transparent text-[13px] text-zinc-100 focus:outline-none resize-none font-sans placeholder:text-zinc-600 p-0.5 scrollbar-none"
          />

          {/* Action Toolbar Row (Matching user UI screenshot) */}
          <div className="flex items-center justify-between pt-2 border-t border-zinc-800/80 select-none">
            
            {/* Left Tools & Context Attachments */}
            <div className="flex items-center gap-1.5">
              {/* Document / File Context */}
              <button
                type="button"
                onClick={() => setFileContextActive(!fileContextActive)}
                className={`relative p-1.5 rounded-lg transition-colors cursor-pointer ${
                  fileContextActive ? 'bg-zinc-800/80 text-zinc-200 border border-zinc-700' : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                }`}
                title="Toggle active document context"
              >
                <FileText className="w-3.5 h-3.5" />
                {fileContextActive && (
                  <span className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-blue-400" />
                )}
              </button>

              {/* Terminal Context */}
              <button
                type="button"
                onClick={() => setTerminalContextActive(!terminalContextActive)}
                className={`relative p-1.5 rounded-lg transition-colors cursor-pointer ${
                  terminalContextActive ? 'bg-zinc-800/80 text-zinc-200 border border-zinc-700' : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                }`}
                title="Toggle terminal buffer context"
              >
                <Terminal className="w-3.5 h-3.5" />
                {terminalContextActive && (
                  <span className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                )}
              </button>

              {/* Database Context */}
              <button
                type="button"
                onClick={() => setDbContextActive(!dbContextActive)}
                className={`relative p-1.5 rounded-lg transition-colors cursor-pointer ${
                  dbContextActive ? 'bg-zinc-800/80 text-zinc-200 border border-zinc-700' : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                }`}
                title="Toggle database schema context"
              >
                <Database className="w-3.5 h-3.5" />
                {dbContextActive && (
                  <span className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-blue-400" />
                )}
              </button>

              {/* Browser Preview Context */}
              <button
                type="button"
                onClick={() => setBrowserContextActive(!browserContextActive)}
                className={`relative p-1.5 rounded-lg transition-colors cursor-pointer ${
                  browserContextActive ? 'bg-zinc-800/80 text-zinc-200 border border-zinc-700' : 'text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
                }`}
                title="Toggle browser preview context"
              >
                <Globe className="w-3.5 h-3.5" />
                {browserContextActive && (
                  <span className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-amber-400" />
                )}
              </button>

              {/* Review Changes Button */}
              <button
                type="button"
                onClick={handleOpenReviewPanel}
                className="flex items-center gap-1.5 px-2.5 py-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 font-semibold border border-zinc-800 rounded-lg text-[11px] cursor-pointer transition-colors"
                title="Open Review Changes Panel"
              >
                <FileCode className="w-3.5 h-3.5 text-violet-400" />
                <span>Review Changes</span>
              </button>

              {/* Running Process Indicator Badge & Quick Stop */}
              {isProcessRunning && (
                <button
                  type="button"
                  onClick={() => onStopProcess?.()}
                  className="flex items-center gap-1 px-2 py-1 bg-red-950/60 hover:bg-red-900/60 text-red-300 font-semibold border border-red-800/80 rounded-lg text-[10.5px] cursor-pointer transition-colors"
                  title="Click to stop running background server or process"
                >
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span>Process</span>
                  <span className="text-[9px] font-bold bg-red-600 text-white px-1 rounded ml-0.5">■ Stop</span>
                </button>
              )}
            </div>

            {/* Right Controls: Mode Selector & Send */}
            <div className="flex items-center gap-2">
              {/* Auto Apply Toggle */}
              <label className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-400 hover:text-zinc-200 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={autoApply}
                  onChange={(e) => setAutoApply(e.target.checked)}
                  className="rounded border-zinc-800 bg-zinc-900 text-violet-600 focus:ring-violet-500 focus:ring-offset-0 w-3 h-3 cursor-pointer"
                />
                <span>Auto Apply</span>
              </label>

              {/* Mode Selector */}
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                className="px-2 py-1 bg-zinc-900 border border-zinc-800 rounded-lg text-[11px] font-semibold text-zinc-200 focus:outline-none focus:border-violet-500 cursor-pointer"
              >
                <option value="Auto">Auto</option>
                <option value="Ask">Ask</option>
                <option value="Plan">Plan</option>
                <option value="Agent">Agent</option>
              </select>

              {/* Submit / Stop Generation Button */}
              {isGenerating && !input.trim() ? (
                <button
                  type="button"
                  onClick={onCancelGeneration}
                  className="p-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg cursor-pointer transition-colors shadow-sm"
                  title="Stop generating"
                >
                  <span className="w-3.5 h-3.5 flex items-center justify-center font-bold text-[9px]">■</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="p-1.5 bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 text-white disabled:text-zinc-600 rounded-lg cursor-pointer disabled:cursor-not-allowed transition-colors shadow-sm"
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