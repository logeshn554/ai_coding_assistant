import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Settings,
  Sparkles,
  Terminal,
  Check,
  X,
  Plus,
  Mic,
  ChevronDown,
  FileText
} from 'lucide-react';

import type { ChatMessage, AgentState, Session, ProcessEntry } from '../types/chat';
import { MessageList } from './chat/MessageList';
import { AgentStatusBar } from './chat/AgentStatusBar';

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (text: string, mode: 'Auto' | 'Ask' | 'Plan' | 'Agent', autoApply: boolean) => void;
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
  activeAgent = null,
  activeTask: _activeTask = null,
  agents = [],
  contextTokens = '0',
  contextPercentage = 0,
  totalCostUsd = 0.0,
  activeProcesses = [],
  onConfirmPortConflict,
  onStopProcess,
  sessions = [],
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  onNewSession,
  onRenameSession
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<'Auto' | 'Ask' | 'Plan' | 'Agent'>('Auto');
  const autoApply = false;
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});
  const isProcessRunning = activeProcesses.some(p => p.status === 'running' || p.status === 'starting');
  const [showHistoryDropdown, setShowHistoryDropdown] = useState(false);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Derive current session title
  const currentSession = sessions.find(s => s.id === activeSessionId);
  const sessionTitle = currentSession?.title || 'Current Session';

  // Compute active agent count
  const activeAgentCount = agents.filter(a => a.status === 'running').length || (activeAgent ? 1 : 0);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating, statusMessage]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isGenerating) return;
    onSendMessage(input.trim(), mode, autoApply);
    setInput('');
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

  const lastMessage = messages[messages.length - 1];
  const showTypingIndicator = isGenerating && (!lastMessage || lastMessage.role === 'user');

  return (
    <div className="h-full flex flex-col bg-zinc-950 text-zinc-200 font-sans relative overflow-hidden">

      {/* 1. TopBar (44px height) */}
      <div className="h-[44px] px-3 border-b border-zinc-800 bg-zinc-900 flex items-center justify-between shrink-0 select-none shadow-sm z-10">
        {/* Left: session name + terminal icon */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistoryDropdown(!showHistoryDropdown)}
            type="button"
            className="flex items-center gap-1.5 text-xs font-semibold text-zinc-100 hover:text-white transition-colors cursor-pointer"
            title="Switch Session"
          >
            <Terminal className="w-4 h-4 text-blue-400 shrink-0" />
            <span className="truncate max-w-[140px] font-mono">{sessionTitle}</span>
            <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
          </button>
        </div>

        {/* Right: 3 Inline Badges */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-300 border border-blue-800/60 font-semibold">
            LangGraph
          </span>
          <span className="px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700">
            {activeAgentCount} agent{activeAgentCount === 1 ? '' : 's'} active
          </span>
          {totalCostUsd > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-amber-950/80 text-amber-300 border border-amber-800/60 font-semibold">
              ${totalCostUsd.toFixed(3)}
            </span>
          )}

          <div className="flex items-center gap-0.5 ml-1 text-zinc-400">
            <button
              onClick={onNewSession}
              type="button"
              className="p-1 hover:bg-zinc-800 hover:text-zinc-100 rounded transition-colors cursor-pointer"
              title="New Session"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onOpenSettings}
              type="button"
              className="p-1 hover:bg-zinc-800 hover:text-zinc-100 rounded transition-colors cursor-pointer"
              title="Settings"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Session Dropdown Menu */}
        {showHistoryDropdown && (
          <div className="absolute left-2 top-11 w-72 max-h-[360px] bg-zinc-900 border border-zinc-800 shadow-2xl z-50 p-2.5 flex flex-col gap-2 font-sans rounded-lg">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
              <span className="text-xs font-bold text-zinc-100">Chat History</span>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={async () => {
                    if (confirm("Are you sure you want to clear all chat sessions?")) {
                      try {
                        const res = await fetch('/api/chat/sessions', { method: 'DELETE' });
                        if (res.ok) {
                          setShowHistoryDropdown(false);
                          onNewSession?.();
                        }
                      } catch (e) {
                        console.error(e);
                      }
                    }
                  }}
                  className="text-[10px] bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 px-1.5 py-0.5 rounded cursor-pointer"
                >
                  Clear All
                </button>
                <button onClick={() => setShowHistoryDropdown(false)} className="text-zinc-400 hover:text-zinc-200 p-0.5">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1 max-h-56 pr-1">
              {sessions && sessions.length > 0 ? (
                sessions.map((s) => {
                  const isActive = s.id === activeSessionId;
                  const isRenaming = renamingSessionId === s.id;
                  return (
                    <div
                      key={s.id}
                      className={`group flex items-center justify-between p-1.5 transition-all text-xs border rounded-md ${
                        isActive ? 'bg-blue-950/80 border-blue-500/50 text-white font-medium' : 'bg-zinc-950/40 border-transparent text-zinc-400 hover:bg-zinc-800'
                      }`}
                    >
                      {isRenaming ? (
                        <div className="flex items-center gap-1 w-full">
                          <input
                            type="text"
                            value={renameText}
                            onChange={(e) => setRenameText(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && renameText.trim()) {
                                onRenameSession?.(s.id, renameText.trim());
                                setRenamingSessionId(null);
                              }
                            }}
                            className="bg-zinc-950 border border-zinc-800 px-1.5 py-0.5 text-xs text-zinc-100 focus:outline-none w-full rounded"
                            autoFocus
                          />
                          <button
                            onClick={() => {
                              if (renameText.trim()) {
                                onRenameSession?.(s.id, renameText.trim());
                                setRenamingSessionId(null);
                              }
                            }}
                            className="p-0.5 text-green-400 hover:bg-zinc-800 rounded"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            onSelectSession?.(s.id);
                            setShowHistoryDropdown(false);
                          }}
                          className="flex-1 text-left truncate font-medium pr-2 block focus:outline-none cursor-pointer"
                          title={s.title}
                        >
                          {s.title}
                        </button>
                      )}

                      {!isRenaming && (
                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => {
                              setRenamingSessionId(s.id);
                              setRenameText(s.title);
                            }}
                            className="p-0.5 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 rounded"
                            title="Rename"
                          >
                            <FileText className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => onDeleteSession?.(s.id)}
                            className="p-0.5 hover:bg-zinc-800 text-zinc-400 hover:text-red-400 rounded"
                            title="Delete"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-[11px] text-zinc-500 text-center py-3">No saved conversations</div>
              )}
            </div>

            <button
              onClick={() => {
                onNewSession?.();
                setShowHistoryDropdown(false);
              }}
              className="mt-1 w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" /> New Session
            </button>
          </div>
        )}
      </div>

      {/* 2. Message List Feed */}
      <div className="flex-1 flex flex-col min-h-0 bg-zinc-950 overflow-hidden">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col justify-center items-center p-6 space-y-4 text-center">
            <div className="p-3 bg-blue-950/60 border border-blue-800/40 text-blue-400 rounded-xl">
              <Sparkles className="w-6 h-6 text-blue-400" />
            </div>
            <h2 className="text-xs font-bold text-zinc-100 tracking-wide uppercase">DevPilot Assistant Ready</h2>
            <p className="text-[11px] text-zinc-500 max-w-[240px] leading-relaxed font-sans">
              Ask any question, analyze the codebase, scan for issues, write unit tests, or execute multi-agent workflows.
            </p>

            <div className="grid grid-cols-2 gap-2 w-full pt-2 max-w-xs">
              {[
                { label: "Refactor file", prompt: "Explain how we can refactor this file to make it cleaner." },
                { label: "Find bugs", prompt: "Inspect the current file for potential errors or bugs." },
                { label: "Write unit tests", prompt: "Draft unit tests for the functions defined in this file." },
                { label: "Explain codebase", prompt: "Summarize the layout and relationships in this codebase." }
              ].map((act, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setInput(act.prompt)}
                  className="p-2 text-left bg-zinc-900 border border-zinc-800 hover:border-blue-500/50 rounded-md text-[11px] text-zinc-400 hover:text-zinc-100 transition-all truncate cursor-pointer font-sans"
                >
                  💡 {act.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <MessageList
            messages={messages}
            onConfirmTool={onConfirmTool}
            onConfirmPermission={onConfirmPermission}
            onConfirmPortConflict={onConfirmPortConflict}
            hunkDecisions={hunkDecisions}
            onToggleHunk={handleToggleHunk}
            onRunCommand={(cmd) => setInput(cmd)}
          />
        )}

        {/* Streaming Thinking Indicator */}
        {showTypingIndicator && (
          <div className="flex gap-2.5 max-w-[95%] items-start select-none px-4 mb-3 animate-slide-up">
            <div className="w-7 h-7 rounded-md bg-zinc-900 border border-zinc-800 text-blue-400 shrink-0 flex items-center justify-center font-bold">
              <Sparkles className="w-4 h-4 text-blue-400 animate-pulse" />
            </div>
            <div className="flex flex-col items-start max-w-[calc(100%-2.25rem)]">
              <div className="p-2.5 bg-zinc-900 border border-zinc-800 rounded-lg flex items-center gap-2 shadow-md">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                </span>
                <span className="text-[11.5px] text-zinc-400 font-medium font-sans">
                  {statusMessage || 'Agents executing task...'}
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* 3. Input & Agent StatusBar Panel (Fixed to Bottom) */}
      <div className="p-2.5 border-t border-zinc-800 bg-zinc-900 shrink-0 font-sans space-y-2">
        {/* Agent StatusBar */}
        <AgentStatusBar
          agents={agents}
          contextPercentage={contextPercentage}
          contextTokens={contextTokens}
          activeProfileName={activeProfileName}
          onOpenSettings={onOpenSettings}
        />

        {/* Input Box Container */}
        <form onSubmit={handleSubmit} className="bg-zinc-950 border border-zinc-800 rounded-lg p-2 flex flex-col gap-2 focus-within:border-blue-500/60 shadow-inner">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything, @ to mention, / for actions (Ctrl+Enter to send)"
            rows={2}
            className="w-full max-h-32 min-h-[40px] bg-transparent text-[13px] text-zinc-100 focus:outline-none resize-none font-sans placeholder:text-zinc-600 p-0.5 scrollbar-none"
          />

          {/* Action Row */}
          <div className="flex items-center justify-between pt-1 border-t border-zinc-800/80 select-none">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                className="p-1 hover:bg-zinc-800 text-zinc-500 hover:text-zinc-200 rounded cursor-pointer transition-colors"
                title="Attach file context"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1 hover:bg-zinc-800 text-blue-400 font-medium px-2 py-0.5 bg-blue-950/40 border border-blue-800/40 rounded text-[10.5px] cursor-pointer"
                title="Active Profile"
              >
                <span>{activeProfileName}</span>
                <ChevronDown className="w-3 h-3 text-blue-400 shrink-0" />
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              {/* Mode Selector */}
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                className="px-2 py-0.5 bg-zinc-900 border border-zinc-800 rounded text-[11px] font-semibold text-zinc-200 focus:outline-none focus:border-blue-500 cursor-pointer"
              >
                <option value="Auto">Auto</option>
                <option value="Ask">Ask</option>
                <option value="Plan">Plan</option>
                <option value="Agent">Agent</option>
              </select>

              <button
                type="button"
                disabled
                className="p-1 text-zinc-600 rounded cursor-not-allowed opacity-40"
                title="Voice input — coming soon"
              >
                <Mic className="w-3.5 h-3.5" />
              </button>

              {/* Submit / Cancel Button */}
              {isGenerating ? (
                <button
                  type="button"
                  onClick={onCancelGeneration}
                  className="p-1.5 bg-red-600 hover:bg-red-500 text-white rounded-md cursor-pointer transition-colors"
                  title="Stop generating"
                >
                  <span className="w-3.5 h-3.5 flex items-center justify-center font-bold text-[9px]">■</span>
                </button>
              ) : isProcessRunning ? (
                <button
                  type="button"
                  onClick={() => onStopProcess?.()}
                  className="p-1.5 bg-red-600 hover:bg-red-500 text-white rounded-md cursor-pointer transition-colors"
                  title="Stop running process"
                >
                  <span className="w-3.5 h-3.5 flex items-center justify-center font-bold text-[9px]">■</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="p-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 text-white disabled:text-zinc-600 rounded-md cursor-pointer disabled:cursor-not-allowed transition-colors shadow-sm"
                  title="Send message (Ctrl+Enter)"
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