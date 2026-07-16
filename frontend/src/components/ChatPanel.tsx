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
  FileCode,
  Braces,
  MessageSquare,
  FileText
} from 'lucide-react';

import type { ChatMessage } from '../types/chat';
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

  // Collaboration States
  activeAgent?: string | null;
  activeTask?: string | null;
  collaborationLog?: string[];
  subtasks?: any[];
  contextTokens?: string;
  contextPercentage?: number;

  // Background running processes
  activeProcesses?: any[];
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  onStopProcess?: (processId?: string) => void;

  // Sessions / Chat History
  sessions?: any[];
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
  activeTask = null,
  contextTokens = '0',
  contextPercentage = 0,
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
  const [activeFeedTab, setActiveFeedTab] = useState<'chat' | 'logs'>('chat');
  const [showHistoryDropdown, setShowHistoryDropdown] = useState(false);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto switch to logs feed if there is a pending confirmation that just arrived
  useEffect(() => {
    const hasPending = messages.some(m => m.isConfirmPending);
    if (hasPending) {
      setActiveFeedTab('logs');
    }
  }, [messages]);

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'py':
        return {
          icon: <FileCode className="w-3.5 h-3.5 text-emerald-400 shrink-0" />,
          className: "text-emerald-400 font-mono bg-emerald-500/5 border border-emerald-500/10 px-1.5 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'ts':
      case 'tsx':
        return {
          icon: <FileCode className="w-3.5 h-3.5 text-sky-400 shrink-0" />,
          className: "text-sky-400 font-mono bg-sky-500/5 border border-sky-500/10 px-1.5 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'js':
      case 'jsx':
        return {
          icon: <FileCode className="w-3.5 h-3.5 text-amber-400 shrink-0" />,
          className: "text-amber-400 font-mono bg-amber-500/5 border border-amber-500/10 px-1.5 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'json':
        return {
          icon: <Braces className="w-3.5 h-3.5 text-yellow-400 shrink-0" />,
          className: "text-yellow-400 font-mono bg-yellow-500/5 border border-yellow-500/10 px-1.5 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'bat':
      case 'sh':
        return {
          icon: <Terminal className="w-3.5 h-3.5 text-rose-400 shrink-0" />,
          className: "text-rose-455 font-mono bg-rose-500/5 border border-rose-500/10 px-1.5 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      default:
        return {
          icon: null,
          className: "bg-white/5 font-mono px-1.5 py-0.5 rounded text-gray-300 border border-white/5"
        };
    }
  };

  const renderStyledCode = (code: string, key: any) => {
    const fileMeta = getFileIcon(code);
    return (
      <code key={key} className={fileMeta.className}>
        {fileMeta.icon}
        {code}
      </code>
    );
  };

  const renderStyledLink = (text: string, url: string, key: any) => {
    const isFile = url.startsWith('file://') || url.includes('/file:/');
    const fileMeta = getFileIcon(text);

    if (isFile) {
      return (
        <a
          key={key}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className={`${fileMeta.className} hover:bg-white/10 transition-colors cursor-pointer border border-violet-500/30 text-violet-300 gap-1.5 focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none`}
          title={`Open ${text}`}
        >
          {fileMeta.icon || <FileCode className="w-3.5 h-3.5 text-violet-400 shrink-0" />}
          <span>{text}</span>
        </a>
      );
    }

    return (
      <a
        key={key}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-violet-400 hover:text-violet-300 hover:underline transition-all font-semibold focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none rounded px-0.5"
      >
        {text}
      </a>
    );
  };

  const renderMessageContent = (content: string) => {
    if (!content) return null;

    const lines = content.split('\n');

    return lines.map((line, lineIdx) => {
      const mdRegex = /(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))/g;
      const parts = line.split(mdRegex);

      const parsedLine = parts.map((part, partIdx) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          const boldText = part.slice(2, -2);
          return <strong key={partIdx} className="font-bold text-white">{boldText}</strong>;
        }

        if (part.startsWith('`') && part.endsWith('`')) {
          const codeText = part.slice(1, -1);
          return renderStyledCode(codeText, partIdx);
        }

        if (part.startsWith('[') && part.includes('](')) {
          const linkMatch = part.match(/\[(.*?)\]\((.*?)\)/);
          if (linkMatch) {
            const [, text, url] = linkMatch;
            return renderStyledLink(text, url, partIdx);
          }
        }

        return part;
      });

      return (
        <div key={lineIdx} className="min-h-[18px]">
          {parsedLine}
        </div>
      );
    });
  };

  useEffect(() => {
    // Scroll to bottom when messages update
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating, statusMessage, activeFeedTab]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isGenerating) return;
    onSendMessage(input.trim(), mode, autoApply);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
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
    <div className="h-full flex flex-col bg-[var(--dp-bg-dark)] text-[#cccccc] font-sans relative overflow-hidden">

      {/* Header Row - Compact */}
      <div className="p-2 border-b border-[#2d2d2d] bg-[var(--dp-bg-tertiary)] flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-violet-400 animate-pulse-subtle shrink-0" />
          <span className="text-xs font-semibold text-white tracking-wide">DevPilot Chat</span>
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" title="Agent Ready" />
        </div>
        <div className="flex items-center gap-0.5 text-gray-400">
          <button
            onClick={() => setShowHistoryDropdown(!showHistoryDropdown)}
            type="button"
            className="p-1 hover:bg-white/5 hover:text-white transition-colors cursor-pointer"
            title="Chat History"
          >
            <MessageSquare className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onNewSession}
            type="button"
            className="p-1 hover:bg-white/5 hover:text-white transition-colors cursor-pointer"
            title="New Conversation"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onOpenSettings}
            type="button"
            className="p-1 hover:bg-white/5 hover:text-white transition-colors cursor-pointer"
            title="Settings"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Chat History Dropdown */}
        {showHistoryDropdown && (
          <div className="absolute right-2 top-10 w-72 max-h-[360px] bg-[#181818] border border-[#2d2d2d] shadow-2xl z-50 p-2.5 flex flex-col gap-2 font-sans rounded-none">
            <div className="flex items-center justify-between border-b border-[#2d2d2d] pb-1.5">
              <span className="text-xs font-bold text-white">Chat History</span>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={async () => {
                    if (confirm("Are you sure you want to clear all chat sessions? This cannot be undone.")) {
                      try {
                        const res = await fetch('/api/chat/sessions', { method: 'DELETE' });
                        if (res.ok) {
                          window.location.reload();
                        }
                      } catch (e) {
                        console.error(e);
                      }
                    }
                  }}
                  className="text-[9px] bg-red-500/10 hover:bg-red-500/20 text-red-405 border border-red-500/20 px-1.5 py-0.2 rounded-none cursor-pointer transition-colors"
                >
                  Clear All
                </button>
                <button
                  onClick={() => setShowHistoryDropdown(false)}
                  className="text-gray-400 hover:text-white p-0.5 cursor-pointer"
                >
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
                      className={`group flex items-center justify-between p-1.5 transition-all text-xs border ${isActive
                        ? 'bg-violet-500/10 border-violet-500/30 text-white font-medium'
                        : 'bg-black/10 border-transparent text-gray-400 hover:bg-white/5 hover:text-gray-200'
                        } rounded-none`}
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
                            className="bg-[#1e1e1e] border border-[#2d2d2d] px-1.5 py-0.5 text-xs text-white focus:outline-none w-full rounded-none"
                            autoFocus
                          />
                          <button
                            onClick={() => {
                              if (renameText.trim()) {
                                onRenameSession?.(s.id, renameText.trim());
                                setRenamingSessionId(null);
                              }
                            }}
                            className="p-0.5 text-emerald-400 hover:bg-white/5 rounded-none"
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
                            className="p-0.5 hover:bg-white/5 text-gray-500 hover:text-white rounded-none"
                            title="Rename"
                          >
                            <FileText className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => onDeleteSession?.(s.id)}
                            className="p-0.5 hover:bg-white/5 text-gray-500 hover:text-red-400 rounded-none"
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
                <div className="text-[10px] text-gray-600 text-center py-4">
                  No saved conversations
                </div>
              )}
            </div>

            <button
              onClick={() => {
                onNewSession?.();
                setShowHistoryDropdown(false);
              }}
              className="mt-1 w-full py-1.5 bg-[#8b5cf6] hover:bg-[#7c4dff] text-white rounded-none text-xs font-bold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" /> New Conversation
            </button>
          </div>
        )}
      </div>

      {/* Agent Status Compact Bar */}
      <div className="px-2 py-1.5 bg-[#141414] border-b border-[#2d2d2d] flex items-center justify-between text-[10px] select-none font-mono text-gray-400 shrink-0">
        <span className="truncate max-w-[200px]" title={activeTask || 'Ready'}>
          Active Task: <span className="text-[#cccccc]">{activeTask ? `"${activeTask}"` : 'Listening for instructions'}</span>
        </span>
        {activeAgent && (
          <span className="text-[9px] bg-violet-500/10 text-violet-400 border border-violet-500/20 px-1 rounded-sm uppercase shrink-0 font-bold leading-normal">
            {activeAgent}
          </span>
        )}
      </div>

      {/* Message & Log Feed Container - Unified Inline Stream */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 bg-[#1e1e1e] scrollbar-thin select-text">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col justify-center items-center p-6 space-y-4 text-center">
            <div className="p-3 bg-[#8b5cf6]/10 border border-[#8b5cf6]/20 text-violet-400 shrink-0">
              <Sparkles className="w-5 h-5 text-violet-400" />
            </div>
            <h2 className="text-xs font-bold text-white tracking-wide uppercase">AI Assistant Ready</h2>
            <p className="text-[10px] text-gray-500 max-w-[220px] leading-relaxed font-sans">
              Enter your instruction below to analyze the codebase, scan for issues, write unit tests, or apply code changes.
            </p>

            <div className="grid grid-cols-2 gap-1.5 w-full pt-4">
              {[
                { label: "Refactor current file", prompt: "Explain how we can refactor this file to make it cleaner." },
                { label: "Find errors & bugs", prompt: "Inspect the current file for potential errors or bugs." },
                { label: "Write unit tests", prompt: "Draft unit tests for the functions defined in this file." },
                { label: "Explain codebase", prompt: "Summarize the layout and relationships in this codebase." }
              ].map((act, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setInput(act.prompt)}
                  className="p-1.5 text-left bg-[#181818] border border-[#2d2d2d] hover:border-[#8b5cf6]/40 rounded-none text-[10px] text-gray-400 hover:text-white transition-all truncate cursor-pointer font-sans"
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
            renderMessageContent={renderMessageContent}
          />
        )}

        {/* Streaming Loader / Thinking indicator inside message feed */}
        {showTypingIndicator && (
          <div className="flex gap-2.5 max-w-[95%] items-start select-none mb-4 animate-fade-in">
            <div className="w-6 h-6 rounded-md bg-[#8b5cf6]/10 border border-[#8b5cf6]/20 text-violet-400 shrink-0 flex items-center justify-center text-[10px] font-bold">
              AI
            </div>
            <div className="flex flex-col items-start max-w-[calc(100%-1.75rem)]">
              <div className="p-2.5 bg-[#141414] border border-[#2d2d2d] rounded-lg flex items-center gap-2 shadow-md">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
                </span>
                <span className="text-[11px] text-gray-400 font-medium font-sans animate-pulse">
                  {statusMessage || 'Thinking...'}
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Bar (fixed to bottom) */}
      <form onSubmit={handleSubmit} className="p-2.5 border-t border-[#2d2d2d] bg-[#131313] shrink-0 font-sans">

        {/* Token Usage Status Bar - Compact */}
        <AgentStatusBar
          contextPercentage={contextPercentage}
          contextTokens={contextTokens}
          activeProfileName={activeProfileName}
          onOpenSettings={onOpenSettings}
        />

        {/* Input Text Box Container */}
        <div className="bg-[#1e1e1e] border border-[#2d2d2d] rounded-none p-2 flex flex-col gap-1.5 focus-within:border-[#8b5cf6]/50">

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything, @ to mention, / for actions"
            className="w-full max-h-24 min-h-[36px] bg-transparent text-xs text-gray-200 focus:outline-none resize-none scrollbar-none font-sans placeholder:text-gray-600 rounded-none p-0.5"
          />

          {/* Action Row */}
          <div className="flex sm:items-center justify-between pt-1.5 border-t border-[#2d2d2d] select-none gap-2">
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="p-1 hover:bg-white/5 text-gray-500 hover:text-white rounded-none cursor-pointer"
                title="Attach file context"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1 hover:bg-white/5 hover:text-violet-300 text-violet-400 font-medium px-2 py-0.5 bg-violet-500/5 border border-violet-500/10 rounded-none text-[9px] cursor-pointer"
                title="Active Profile"
              >
                <span>{activeProfileName}</span>
                <ChevronDown className="w-2.5 h-2.5 text-violet-400 shrink-0" />
              </button>
            </div>

            <div className="flex items-center gap-1">
              {/* Agent Mode Selector */}
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                className="px-1.5 py-0.5 bg-[#181818] border border-[#2d2d2d] rounded-none text-[9px] font-semibold text-white focus:outline-none focus:border-[#8b5cf6] cursor-pointer"
              >
                <option value="Auto">Auto</option>
                <option value="Ask">Ask</option>
                <option value="Plan">Plan</option>
                <option value="Agent">Agent</option>
              </select>

              {/* Dictation */}
              <button
                type="button"
                className="p-1 hover:bg-white/5 text-gray-500 hover:text-white rounded-none cursor-pointer"
                title="Voice input"
              >
                <Mic className="w-3.5 h-3.5" />
              </button>

              {/* Stop or Submit button */}
              {isGenerating ? (
                <button
                  type="button"
                  onClick={onCancelGeneration}
                  className="p-1 bg-red-650 hover:bg-red-600 text-white rounded-none cursor-pointer border border-red-500/20"
                  title="Stop generating"
                >
                  <span className="w-3 h-3 flex items-center justify-center font-bold text-[8px]">■</span>
                </button>
              ) : isProcessRunning ? (
                <button
                  type="button"
                  onClick={() => onStopProcess?.()}
                  className="p-1 bg-red-650 hover:bg-red-600 text-white rounded-none cursor-pointer border border-red-500/20"
                  title="Stop running process"
                >
                  <span className="w-3 h-3 flex items-center justify-center font-bold text-[8px]">■</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="p-1 bg-[#8B5CF6] hover:bg-[#7c4dff] disabled:bg-transparent text-white disabled:text-gray-600 border border-violet-500/20 disabled:border-transparent rounded-none cursor-pointer disabled:cursor-not-allowed"
                  title="Send message"
                >
                  <Send className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>

        </div>

      </form>

    </div>
  );
}