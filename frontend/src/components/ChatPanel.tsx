import React, { useState, useEffect, useRef } from 'react';
import { Send, Settings, Sparkles, User, Terminal, Check, X, FileDiff, Play, Plus, Mic, ChevronDown, FileCode, Braces, Search } from 'lucide-react';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string;
  tool_calls?: any[];
  tool_call_id?: string;
  name?: string;
  status?: 'success' | 'error';
  isConfirmPending?: boolean;
  confirmArgs?: any;
  confirmDiff?: {
    path: string;
    original: string;
    proposed: string;
    hunks?: any[];
  };
  
  // Permission Request Fields
  isPermissionRequest?: boolean;
  permissionCommand?: string;
  permissionRisk?: string;
  permissionReason?: string;
  permissionExplanation?: string;
}

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (text: string, mode: 'Ask' | 'Plan' | 'Agent', autoApply: boolean) => void;
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
  collaborationLog = [],
  subtasks = [],
  contextTokens = '0',
  contextPercentage = 0
}: ChatPanelProps) {
  const [editingCommandId, setEditingCommandId] = useState<string | null>(null);
  const [editedCommandText, setEditedCommandText] = useState<string>('');
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<'Ask' | 'Plan' | 'Agent'>('Agent');
  const [autoApply, setAutoApply] = useState(false);
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'py':
        return {
          icon: <FileCode className="w-3.5 h-3.5 text-emerald-400 shrink-0" />,
          className: "text-emerald-400 font-mono bg-emerald-500/5 border border-emerald-500/10 px-1 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'ts':
      case 'tsx':
        return {
          icon: <FileCode className="w-3.5 h-3.5 text-sky-400 shrink-0" />,
          className: "text-sky-400 font-mono bg-sky-500/5 border border-sky-500/10 px-1 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'js':
      case 'jsx':
        return {
          icon: <FileCode className="w-3.5 h-3.5 text-amber-400 shrink-0" />,
          className: "text-amber-400 font-mono bg-amber-500/5 border border-amber-500/10 px-1 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'json':
        return {
          icon: <Braces className="w-3.5 h-3.5 text-yellow-400 shrink-0" />,
          className: "text-yellow-400 font-mono bg-yellow-500/5 border border-yellow-500/10 px-1 py-0.5 rounded inline-flex items-center gap-1 select-all"
        };
      case 'bat':
      case 'sh':
        return {
          icon: <Terminal className="w-3.5 h-3.5 text-rose-400 shrink-0" />,
          className: "text-rose-400 font-mono bg-rose-500/5 border border-rose-500/10 px-1 py-0.5 rounded inline-flex items-center gap-1 select-all"
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
          className={`${fileMeta.className} hover:bg-white/10 transition-colors cursor-pointer border border-violet-500/30 text-violet-300 gap-1.5`}
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
        className="text-violet-400 hover:text-violet-300 hover:underline transition-all font-semibold"
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
  }, [messages, isGenerating, statusMessage]);

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

  // Helper to format tool arguments
  const formatArgs = (args: any) => {
    try {
      if (typeof args === 'string') return args;
      return JSON.stringify(args, null, 2);
    } catch {
      return String(args);
    }
  };
  
  const renderDiffHunk = (msgId: string, hunk: any, idx: number) => {
    const isAccepted = hunkDecisions[msgId]?.[hunk.id] ?? true;

    return (
      <div key={hunk.id} className="border border-white/5 bg-black/30 rounded-xl overflow-hidden text-[10px] my-2">
        <div className="flex items-center justify-between px-3 py-1.5 bg-white/3 border-b border-white/5 select-none font-sans">
          <span className="text-gray-400 font-semibold uppercase text-[8px] tracking-wider">Hunk #{idx + 1}</span>
          <div className="flex gap-1.5 text-[8px]">
            <button
              type="button"
              onClick={() => {
                setHunkDecisions(prev => ({
                  ...prev,
                  [msgId]: {
                    ...(prev[msgId] || {}),
                    [hunk.id]: false
                  }
                }));
              }}
              className={`px-2 py-0.5 rounded transition-all font-bold cursor-pointer ${
                !isAccepted 
                  ? 'bg-red-500/20 text-red-400 border border-red-500/40' 
                  : 'bg-white/5 text-gray-500 hover:text-gray-300'
              }`}
            >
              Reject
            </button>
            <button
              type="button"
              onClick={() => {
                setHunkDecisions(prev => ({
                  ...prev,
                  [msgId]: {
                    ...(prev[msgId] || {}),
                    [hunk.id]: true
                  }
                }));
              }}
              className={`px-2 py-0.5 rounded transition-all font-bold cursor-pointer ${
                isAccepted 
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' 
                  : 'bg-white/5 text-gray-500 hover:text-gray-300'
              }`}
            >
              Accept
            </button>
          </div>
        </div>

        <pre className="p-2.5 font-mono max-h-48 overflow-y-auto whitespace-pre overflow-x-auto leading-relaxed select-text">
          {hunk.lines.map((l: string, i: number) => {
            const isAdded = l.startsWith('+');
            const isRemoved = l.startsWith('-');
            const lineClass = isAdded
              ? 'bg-emerald-500/10 text-emerald-400 px-1 rounded-sm w-full block'
              : isRemoved
              ? 'bg-red-500/10 text-red-400 line-through px-1 rounded-sm w-full block'
              : 'text-gray-400 w-full block';
            return (
              <span key={i} className={lineClass}>
                {l}
              </span>
            );
          })}
        </pre>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-[#111318] text-gray-200 border-l border-white/5">
      
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#14171f] shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-400 animate-pulse-subtle" />
          <span className="text-sm font-semibold text-white">DevPilot Agent</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500 bg-white/5 border border-white/5 px-2 py-0.5 rounded-full font-medium">
            {activeProfileName}
          </span>
          <button
            onClick={onOpenSettings}
            className="p-1 rounded hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="p-3 border-b border-white/5 bg-[#0e1014] shrink-0 flex items-center justify-between gap-3">
        <div className="flex bg-black/35 rounded-xl p-1 flex-1 border border-white/5">
          {(['Ask', 'Plan', 'Agent'] as const).map((m) => {
            const Icon = m === 'Ask' ? Search : m === 'Plan' ? FileDiff : Terminal;
            return (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 py-1.5 rounded-lg text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  mode === m
                    ? 'bg-violet-600 text-white shadow-md glow-purple font-bold'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/3'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{m}</span>
              </button>
            );
          })}
        </div>

        {/* Auto apply toggle (only visible in Agent mode) */}
        {mode === 'Agent' && (
          <label className="flex items-center gap-1.5 cursor-pointer text-[10px] text-gray-400 font-medium shrink-0">
            <input
              type="checkbox"
              checked={autoApply}
              onChange={(e) => setAutoApply(e.target.checked)}
              className="accent-violet-600 rounded"
            />
            <span>Auto-Apply</span>
          </label>
        )}
      </div>

      {/* Collaboration State Dashboard */}
      {activeAgent && (
        <div className="mx-4 my-2 p-3 bg-[#161922] border border-violet-500/20 rounded-xl space-y-2 shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
              </span>
              <span className="text-[11px] font-bold text-gray-200">Active Agent: {activeAgent}</span>
            </div>
            {subtasks && subtasks.length > 0 && (
              <span className="text-[9px] text-gray-450 bg-white/5 px-1.5 py-0.5 rounded font-medium">
                Workers: {subtasks.filter((s: any) => s.status === 'running').length}
              </span>
            )}
          </div>
          {activeTask && (
            <p className="text-[10px] text-gray-400 italic">Current task: "{activeTask}"</p>
          )}

          {/* Parallel Subtasks Progress */}
          {subtasks && subtasks.length > 0 && (
            <div className="space-y-2 pt-2 border-t border-white/5 select-none max-h-40 overflow-y-auto pr-1">
              <div className="text-[9px] font-bold text-violet-400 uppercase tracking-wider">
                Execution Pipeline & Subtasks
              </div>
              <div className="space-y-1.5">
                {subtasks.map((task: any) => (
                  <div key={task.id} className="p-1.5 bg-black/20 rounded border border-white/5 space-y-1">
                    <div className="flex items-center justify-between text-[9px]">
                      <span className="font-semibold text-gray-300 truncate max-w-[180px]">
                        #{task.id} - {task.agent}
                      </span>
                      <span className={`px-1 rounded text-[8px] font-bold uppercase ${
                        task.status === 'completed'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/10'
                          : task.status === 'running'
                          ? 'bg-violet-500/20 text-violet-400 border border-violet-500/10 animate-pulse'
                          : task.status === 'failed'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/10'
                          : 'bg-gray-500/10 text-gray-400 border border-white/5'
                      }`}>
                        {task.status === 'completed' ? '✓ Done' : task.status === 'running' ? '⟳ Running' : task.status === 'failed' ? '✗ Failed' : '⏳ Waiting'}
                      </span>
                    </div>
                    <div className="text-[8px] text-gray-400 truncate">
                      {task.description}
                      {task.dependencies && task.dependencies.length > 0 && (
                        <span className="text-gray-500 ml-1.5">
                          (needs #{task.dependencies.join(', #')})
                        </span>
                      )}
                    </div>
                    <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          task.status === 'completed' 
                            ? 'bg-emerald-500' 
                            : task.status === 'failed' 
                            ? 'bg-red-500' 
                            : 'bg-violet-500'
                        }`}
                        style={{ width: `${task.progress || 0}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {collaborationLog && collaborationLog.length > 0 && (
            <div className="border-t border-white/5 pt-1.5 mt-1.5">
              <details className="cursor-pointer group">
                <summary className="text-[9px] text-gray-500 font-semibold select-none group-open:text-violet-400">
                  Agent Collaboration Logs ({collaborationLog.length})
                </summary>
                <div className="mt-1 max-h-24 overflow-y-auto font-mono text-[8px] text-gray-500 space-y-1 pr-1">
                  {collaborationLog.map((logStr, i) => (
                    <div key={i} className="border-l border-violet-500/30 pl-1.5 py-0.5">
                      {logStr}
                    </div>
                  ))}
                </div>
              </details>
            </div>
          )}
        </div>
      )}

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0 bg-[#0e1014]/40">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col justify-center p-6 space-y-6 text-gray-300">
            <div className="flex flex-col items-center text-center space-y-2">
              <div className="p-3.5 bg-violet-600/10 border border-violet-500/20 rounded-2xl glow-purple animate-pulse-subtle">
                <Sparkles className="w-6 h-6 text-violet-400" />
              </div>
              <h2 className="text-sm font-bold text-white tracking-tight pt-2">DevPilot AI Assistant</h2>
              <p className="text-[10px] text-gray-500 max-w-[240px]">
                Your next-generation multi-agent coding engine. Choose a mode below to begin:
              </p>
            </div>

            {/* Structured assistant feature cards */}
            <div className="space-y-2 text-xs">
              <div
                onClick={() => setMode('Ask')}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex gap-3 items-start ${
                  mode === 'Ask'
                    ? 'bg-violet-600/5 border-violet-500/30'
                    : 'bg-white/2 border-white/5 hover:border-white/10 hover:bg-white/5'
                }`}
              >
                <div className="p-1.5 rounded bg-violet-500/10 text-violet-400 mt-0.5">
                  <Search className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-white text-[11px]">Ask Mode</div>
                  <div className="text-[9px] text-gray-500 leading-normal">Read-only code analysis, queries, and prompt explanations.</div>
                </div>
              </div>

              <div
                onClick={() => setMode('Plan')}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex gap-3 items-start ${
                  mode === 'Plan'
                    ? 'bg-violet-600/5 border-violet-500/30'
                    : 'bg-white/2 border-white/5 hover:border-white/10 hover:bg-white/5'
                }`}
              >
                <div className="p-1.5 rounded bg-violet-500/10 text-violet-400 mt-0.5">
                  <FileDiff className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-white text-[11px]">Plan Mode</div>
                  <div className="text-[9px] text-gray-500 leading-normal">Build interactive plans and gather user feedback before editing files.</div>
                </div>
              </div>

              <div
                onClick={() => setMode('Agent')}
                className={`p-3 rounded-xl border transition-all cursor-pointer flex gap-3 items-start ${
                  mode === 'Agent'
                    ? 'bg-violet-600/5 border-violet-500/30'
                    : 'bg-white/2 border-white/5 hover:border-white/10 hover:bg-white/5'
                }`}
              >
                <div className="p-1.5 rounded bg-violet-500/10 text-violet-400 mt-0.5">
                  <Terminal className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-white text-[11px]">Agent Mode</div>
                  <div className="text-[9px] text-gray-500 leading-normal">Dynamic router coordinator that edits code and verifies runs automatically.</div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="space-y-1.5 pt-2">
              <span className="text-[9px] uppercase font-bold text-gray-500 tracking-wider">Quick Prompts</span>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  { label: "Refactor active file", prompt: "Explain how we can refactor this file to make it cleaner." },
                  { label: "Check for errors", prompt: "Inspect the current file for potential errors or bugs." },
                  { label: "Write unit tests", prompt: "Draft unit tests for the functions defined in this file." },
                  { label: "Explain structure", prompt: "Summarize the layout and relationships in this codebase." }
                ].map((act, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setInput(act.prompt)}
                    className="p-2 text-left bg-white/2 border border-white/5 rounded-lg text-[9px] text-gray-400 hover:text-white hover:bg-[#1a1c24] hover:border-white/10 transition-all truncate cursor-pointer"
                  >
                    💡 {act.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            
            if (msg.role === 'tool') {
              const isSuccess = msg.status === 'success';
              return (
                <div key={msg.id} className="text-xs border border-white/5 bg-black/25 rounded-lg p-2.5 space-y-1.5 font-mono">
                  <div className="flex items-center justify-between text-[10px] text-gray-400 font-semibold uppercase">
                    <span className="flex items-center gap-1.5">
                      <Terminal className="w-3.5 h-3.5" /> Tool: {msg.name}
                    </span>
                    <span className={isSuccess ? "text-emerald-400" : "text-red-400"}>
                      {isSuccess ? "SUCCESS" : "ERROR"}
                    </span>
                  </div>
                  <pre className="text-[10px] max-h-40 overflow-y-auto text-gray-400 p-2 bg-[#171922] rounded whitespace-pre-wrap select-text">
                    {msg.content}
                  </pre>
                </div>
              );
            }

            return (
              <div key={msg.id} className={`flex gap-3 max-w-[90%] ${isUser ? 'ml-auto flex-row-reverse' : ''}`}>
                <div className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center text-[10px] ${
                  isUser ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-300'
                }`}>
                  {isUser ? <User className="w-3.5 h-3.5" /> : <Sparkles className="w-3.5 h-3.5" />}
                </div>
                
                <div className="flex flex-col gap-1.5">
                  <div className={`p-3 rounded-xl text-xs leading-relaxed whitespace-pre-wrap select-text ${
                    isUser 
                      ? 'bg-violet-600/10 border border-violet-500/20 text-white rounded-tr-none' 
                      : 'bg-white/5 border border-white/5 text-gray-200 rounded-tl-none'
                  }`}>
                    {renderMessageContent(msg.content || '')}
                  </div>

                  {/* If assistant yields tool calls that are currently pending user verification */}
                  {msg.isConfirmPending && msg.confirmDiff && (
                    <div className="mt-2 border border-violet-500/30 bg-[#161a25] rounded-lg p-3 space-y-3">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-violet-400">
                        <FileDiff className="w-4 h-4" />
                        <span>Proposed Edits: {msg.confirmDiff.path}</span>
                      </div>
                      
                      <div className="text-[10px] text-gray-400 bg-black/30 p-2 rounded">
                        <span className="font-semibold">Tool args:</span>
                        <pre className="mt-1 font-mono max-h-24 overflow-y-auto whitespace-pre-wrap">
                          {formatArgs(msg.confirmArgs)}
                        </pre>
                      </div>

                      {/* Display Hunks if available */}
                      {msg.confirmDiff.hunks && msg.confirmDiff.hunks.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-[9px] uppercase font-bold text-gray-500 block">Diff Hunks:</span>
                          {msg.confirmDiff.hunks.map((hunk: any, idx: number) => renderDiffHunk(msg.id, hunk, idx))}
                        </div>
                      )}

                      <div className="flex gap-2">
                        <button
                          onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
                          className="flex-1 py-1.5 rounded-lg border border-red-500/30 bg-red-500/5 hover:bg-red-500/10 text-[10px] font-semibold text-red-400 flex items-center justify-center gap-1 transition-all"
                        >
                          <X className="w-3.5 h-3.5" /> Reject
                        </button>
                        <button
                          onClick={() => {
                            if (msg.tool_call_id) {
                              const decisions = hunkDecisions[msg.id] || {};
                              // Fill defaults (true) for any hunks not toggled
                              if (msg.confirmDiff?.hunks) {
                                msg.confirmDiff.hunks.forEach((h: any) => {
                                  if (decisions[h.id] === undefined) {
                                    decisions[h.id] = true;
                                  }
                                });
                              }
                              onConfirmTool(msg.tool_call_id, true, decisions);
                            }
                          }}
                          className="flex-1 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-[10px] font-semibold text-white flex items-center justify-center gap-1 transition-all"
                        >
                          <Check className="w-3.5 h-3.5" /> Accept
                        </button>
                      </div>
                    </div>
                  )}
                  
                  {/* Destructive terminal confirmation */}
                  {msg.isConfirmPending && !msg.confirmDiff && !msg.isPermissionRequest && (
                    <div className="mt-2 border border-red-500/30 bg-red-950/10 rounded-lg p-3 space-y-3">
                      <div className="text-xs font-semibold text-red-400 flex items-center gap-1.5">
                        <Terminal className="w-4 h-4 animate-bounce" />
                        <span>Dangerous Command Warning</span>
                      </div>
                      <p className="text-[10px] text-gray-400 font-mono bg-black/20 p-2 rounded">
                        {msg.confirmArgs?.command}
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
                          className="flex-1 py-1.5 rounded-lg border border-white/5 bg-white/5 hover:bg-white/10 text-[10px] font-semibold text-gray-300 flex items-center justify-center gap-1 transition-all"
                        >
                          <X className="w-3.5 h-3.5" /> Cancel
                        </button>
                        <button
                          onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, true)}
                          className="flex-1 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-[10px] font-semibold text-white flex items-center justify-center gap-1 transition-all"
                        >
                          <Play className="w-3.5 h-3.5" /> Run Command
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Smart Permission Dialog */}
                  {msg.isPermissionRequest && msg.isConfirmPending && (
                    <div className="mt-2 border border-violet-500/30 bg-[#161a25] rounded-lg p-3.5 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-violet-400">
                          <Terminal className="w-4 h-4" />
                          <span>Terminal Permission Dialog</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase ${
                          msg.permissionRisk === 'destructive' 
                            ? 'bg-red-500/25 text-red-400 border border-red-500/30' 
                            : msg.permissionRisk === 'safe'
                            ? 'bg-emerald-500/25 text-emerald-400 border border-emerald-500/30'
                            : 'bg-yellow-500/25 text-yellow-400 border border-yellow-500/30'
                        }`}>
                          {msg.permissionRisk} Risk
                        </span>
                      </div>

                      {msg.permissionExplanation && (
                        <p className="text-[10px] text-gray-400 leading-normal bg-black/15 p-2 rounded">
                          <strong className="text-gray-300">Why it's needed:</strong> {msg.permissionExplanation}
                        </p>
                      )}

                      {msg.permissionReason && (
                        <div className="text-[9px] text-gray-400 border border-violet-500/10 p-1.5 rounded-md bg-[#1d2232]/50 italic">
                          ℹ️ {msg.permissionReason}
                        </div>
                      )}

                      <div className="space-y-1 text-[10px] text-gray-400">
                        <span className="font-semibold text-gray-300">Exact command (editable):</span>
                        <input
                          type="text"
                          value={editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || '')}
                          onFocus={() => {
                            if (editingCommandId !== msg.id) {
                              setEditingCommandId(msg.id);
                              setEditedCommandText(msg.permissionCommand || '');
                            }
                          }}
                          onChange={(e) => setEditedCommandText(e.target.value)}
                          className="w-full bg-[#0d0f12] font-mono text-[10px] border border-white/10 hover:border-violet-500/35 focus:border-violet-500/55 rounded p-2 text-white focus:outline-none transition-all"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-[10px] pt-1">
                        <button
                          type="button"
                          onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, true, 'once', editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || ''))}
                          className="py-1.5 rounded bg-violet-600/10 hover:bg-violet-600/20 border border-violet-500/20 text-violet-400 font-semibold transition-all cursor-pointer text-center"
                        >
                          Allow Once
                        </button>
                        <button
                          type="button"
                          onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, true, 'session', editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || ''))}
                          className="py-1.5 rounded bg-violet-600/10 hover:bg-violet-600/20 border border-violet-500/20 text-violet-400 font-semibold transition-all cursor-pointer text-center"
                        >
                          Allow Session
                        </button>
                        <button
                          type="button"
                          onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, true, 'project', editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || ''))}
                          className="py-1.5 rounded bg-violet-600/10 hover:bg-violet-600/20 border border-violet-500/20 text-violet-400 font-semibold transition-all cursor-pointer text-center"
                        >
                          Allow Project
                        </button>
                        <button
                          type="button"
                          onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, false, 'once', '')}
                          className="py-1.5 rounded bg-red-600/10 hover:bg-red-600/20 border border-red-500/20 text-red-400 font-semibold transition-all cursor-pointer text-center"
                        >
                          Deny
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}

        {/* Status Indicator & Cancel Button */}
        {isGenerating && (
          <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#161922] border border-white/5 text-xs text-gray-300 w-full animate-pulse-subtle select-none">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-ping shrink-0" />
              <span className="text-[10px] text-gray-400 truncate">{statusMessage || 'Thinking...'}</span>
            </div>
            <button
              type="button"
              onClick={onCancelGeneration}
              className="px-2.5 py-1 bg-red-600/15 hover:bg-red-600/30 border border-red-500/20 hover:border-red-500/40 text-[10px] text-red-400 rounded-md transition-all font-semibold cursor-pointer shrink-0"
            >
              Stop
            </button>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-white/5 bg-[#0d0e12] shrink-0">
        <div className="bg-[#181920] border border-white/5 rounded-2xl p-3 flex flex-col gap-2 shadow-2xl">
          {/* Text Area */}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything, @ to mention, / for actions"
            className="w-full max-h-32 min-h-[48px] bg-transparent text-xs text-gray-200 focus:outline-none resize-none scrollbar-none py-1 placeholder:text-gray-600 font-sans"
          />

          {/* Bottom Toolbar Row */}
          <div className="flex items-center justify-between text-gray-500 text-[11px] pt-1 border-t border-white/2">
            <div className="flex items-center gap-2.5">
              {/* Plus button */}
              <button
                type="button"
                className="hover:text-gray-300 transition-colors p-0.5 rounded cursor-pointer"
                title="Add attachment"
              >
                <Plus className="w-4 h-4 text-gray-500" />
              </button>

              {/* Model Pill button */}
              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1 hover:text-violet-400 text-violet-400/90 font-medium px-2 py-0.5 rounded-full bg-violet-500/5 border border-violet-500/10 cursor-pointer transition-colors text-[10px]"
                title="Active Connection Profile"
              >
                <span>{activeProfileName}</span>
                <ChevronDown className="w-3 h-3 text-violet-400" />
              </button>

              {/* Context indicator */}
              <div className="flex items-center gap-1 text-[9px] text-gray-500 font-mono pl-1 select-none">
                <span className="text-amber-500/90 font-bold">{contextTokens}</span>
                <span>({contextPercentage}%)</span>
                <span className="text-gray-600 font-sans ml-1 text-[8px] hidden sm:inline">ctrl+p commands</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Microphone icon */}
              <button
                type="button"
                className="hover:text-gray-300 transition-colors p-1 rounded cursor-pointer"
                title="Voice input"
              >
                <Mic className="w-4 h-4 text-gray-500" />
              </button>

              {/* Send / Stop button */}
              {isGenerating ? (
                <button
                  type="button"
                  onClick={onCancelGeneration}
                  className="p-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg transition-all flex items-center justify-center shrink-0 cursor-pointer animate-pulse-subtle shadow-md"
                  title="Cancel Generation"
                >
                  <div className="w-2.5 h-2.5 bg-red-400 rounded-sm" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim()}
                  className="p-1.5 bg-violet-650/10 hover:bg-violet-650/20 disabled:bg-transparent text-violet-400 disabled:text-gray-700 border border-violet-500/15 disabled:border-transparent rounded-lg transition-all shrink-0 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </form>

    </div>
  );
}
