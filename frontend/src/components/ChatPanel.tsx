import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Settings,
  Sparkles,
  User,
  Terminal,
  Check,
  X,
  FileDiff,
  Play,
  Plus,
  Mic,
  ChevronDown,
  FileCode,
  Braces,
  Search,
  FileText,
  ChevronRight,
  MessageSquare,
  ListTodo,
  AlertTriangle
} from 'lucide-react';

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
  const [activeFeedTab, setActiveFeedTab] = useState<'chat' | 'logs'>('chat');
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
      <div key={hunk.id} className="border border-white/5 bg-black/40 rounded-lg overflow-hidden text-[10px] my-2">
        <div className="flex items-center justify-between px-3 py-1.5 bg-white/3 border-b border-white/5 select-none font-sans">
          <span className="text-gray-400 font-semibold uppercase text-[8px] tracking-wider font-mono">Hunk #{idx + 1}</span>
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
              className={`px-2 py-0.5 rounded transition-all font-bold cursor-pointer focus-visible:ring-1 focus-visible:ring-red-500 focus-visible:outline-none ${
                !isAccepted 
                  ? 'bg-red-500/20 text-red-400 border border-red-500/40 font-bold' 
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
              className={`px-2 py-0.5 rounded transition-all font-bold cursor-pointer focus-visible:ring-1 focus-visible:ring-emerald-500 focus-visible:outline-none ${
                isAccepted 
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-bold' 
                  : 'bg-white/5 text-gray-500 hover:text-gray-300'
              }`}
            >
              Accept
            </button>
          </div>
        </div>

        <pre className="p-2.5 font-mono max-h-48 overflow-y-auto whitespace-pre overflow-x-auto leading-relaxed select-text bg-black/20 text-gray-300">
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

  const chatMessagesCount = messages.filter(m => m.role === 'user' || m.role === 'assistant').length;
  const toolMessagesCount = messages.filter(m => m.role === 'tool' || m.isConfirmPending).length;
  const pendingCount = messages.filter(m => m.isConfirmPending).length;
  const lastMessage = messages[messages.length - 1];
  const showTypingIndicator = isGenerating && (!lastMessage || lastMessage.role === 'user');

  return (
    <div className="h-full flex flex-col bg-[#0c0d12] text-gray-200 border-l border-white/5 font-sans relative overflow-hidden">
      
      {/* Header / Mode Selector Row */}
      <div className="p-3 border-b border-white/5 bg-[#0e1015] shrink-0 flex flex-col gap-3">
        {/* Profile and Settings top row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-400 animate-pulse-subtle" />
            <span className="text-xs font-bold text-white tracking-wide">DevPilot Core Assistant</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onOpenSettings}
              className="p-1.5 rounded hover:bg-white/5 text-gray-400 hover:text-white transition-colors focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 1. Mode Selector (top bar) */}
        <div className="flex gap-2 items-center">
          <div className="flex bg-[#12141c]/90 rounded-xl p-1 border border-white/5 flex-1">
            {(['Ask', 'Plan', 'Agent'] as const).map((m) => {
              const Icon = m === 'Ask' ? Search : m === 'Plan' ? FileText : ChevronRight;
              const isActive = mode === m;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex-1 py-1.5 rounded-lg text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5 cursor-pointer focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none ${
                    isActive
                      ? 'bg-[#8B5CF6] text-white shadow-md font-bold'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
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
            <label className="flex items-center gap-2 cursor-pointer text-[10px] text-gray-400 hover:text-gray-250 font-medium shrink-0 select-none border border-white/5 rounded-xl px-2.5 py-1.5 bg-[#12141c]/50 transition-colors focus-within:ring-2 focus-within:ring-violet-500">
              <input
                type="checkbox"
                checked={autoApply}
                onChange={(e) => setAutoApply(e.target.checked)}
                className="accent-violet-500 rounded bg-black/40 border-white/10 w-3 h-3 cursor-pointer focus-visible:outline-none"
              />
              <span>Auto-Apply</span>
            </label>
          )}
        </div>
      </div>

      {/* 2. Agent Status Card */}
      <div className="px-3 pt-2 shrink-0">
        <div className="p-3 bg-[#151720] border border-white/5 rounded-xl shadow-md">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="motion-safe:animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
              </span>
              <span className="text-[11px] font-bold text-gray-200">
                Active Agent: {activeAgent || 'DevPilot Core'}
              </span>
            </div>
            {subtasks && subtasks.length > 0 && (
              <span className="text-[9px] text-gray-400 bg-white/5 px-1.5 py-0.5 rounded font-mono font-medium">
                Workers: {subtasks.filter((s: any) => s.status === 'running').length}
              </span>
            )}
          </div>
          
          <p className="text-[10px] text-gray-450 italic mt-1 font-sans">
            Current task: "{activeTask || 'Listening for inputs and user prompts'}"
          </p>

          <hr className="border-white/5 my-2" />

          {/* Collapsible collaboration logs */}
          <details className="group">
            <summary className="flex items-center gap-1 cursor-pointer select-none text-[10px] font-semibold text-gray-400 hover:text-gray-200 transition-colors focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none rounded py-0.5 list-none [&::-webkit-details-marker]:hidden">
              <ChevronRight className="w-3.5 h-3.5 text-gray-500 transition-transform duration-200 group-open:rotate-90 motion-reduce:transition-none" />
              <span>Agent Collaboration Logs ({collaborationLog.length})</span>
            </summary>
            
            <div className="mt-2 max-h-24 overflow-y-auto font-mono text-[9px] text-gray-400 space-y-1 bg-black/35 rounded-lg p-2.5 border border-white/5">
              {collaborationLog.length === 0 ? (
                <div className="text-gray-500 italic">No logs recorded yet.</div>
              ) : (
                collaborationLog.map((logStr, i) => (
                  <div key={i} className="border-l border-violet-500/30 pl-2 py-0.5 leading-normal break-all">
                    {logStr}
                  </div>
                ))
              )}
            </div>
          </details>

          {/* Subtasks pipeline render if available */}
          {subtasks && subtasks.length > 0 && (
            <div className="mt-2 pt-2 border-t border-white/5 space-y-1.5 max-h-24 overflow-y-auto pr-1">
              {subtasks.map((task: any) => (
                <div key={task.id} className="p-1.5 bg-black/20 rounded-lg border border-white/5 space-y-1">
                  <div className="flex items-center justify-between text-[9px]">
                    <span className="font-semibold text-gray-300 truncate max-w-[180px]">
                      #{task.id} - {task.agent}
                    </span>
                    <span className={`px-1 rounded text-[8px] font-bold uppercase ${
                      task.status === 'completed'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/10'
                        : task.status === 'running'
                        ? 'bg-violet-500/20 text-violet-400 border border-violet-500/10 animate-pulse'
                        : 'bg-gray-500/10 text-gray-400 border border-white/5'
                    }`}>
                      {task.status === 'completed' ? 'Done' : task.status === 'running' ? 'Running' : 'Waiting'}
                    </span>
                  </div>
                  <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-305 ${
                        task.status === 'completed' 
                          ? 'bg-emerald-500' 
                          : 'bg-violet-500'
                      }`}
                      style={{ width: `${task.progress || 0}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 3. Visual separator & Tab Switch for Logs / Chat sections */}
      <div className="px-3 pt-2 shrink-0">
        <div className="flex bg-[#12141c] rounded-xl p-1 border border-white/5 justify-between items-center text-xs">
          <div className="flex bg-black/20 rounded-lg p-0.5 border border-white/5 flex-1">
            <button
              type="button"
              onClick={() => setActiveFeedTab('chat')}
              className={`flex-1 py-1 rounded-md font-semibold transition-all flex items-center justify-center gap-1.5 cursor-pointer focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none ${
                activeFeedTab === 'chat'
                  ? 'bg-white/10 text-white font-bold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Chat</span>
              {chatMessagesCount > 0 && (
                <span className="bg-violet-500/20 text-violet-300 px-1.5 rounded-full text-[9px] font-bold">
                  {chatMessagesCount}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => setActiveFeedTab('logs')}
              className={`flex-1 py-1 rounded-md font-semibold transition-all flex items-center justify-center gap-1.5 cursor-pointer relative focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none ${
                activeFeedTab === 'logs'
                  ? 'bg-white/10 text-white font-bold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <ListTodo className="w-3.5 h-3.5" />
              <span>Tool Logs</span>
              {toolMessagesCount > 0 && (
                <span className="bg-white/15 text-gray-300 px-1.5 rounded-full text-[9px] font-bold font-mono">
                  {toolMessagesCount}
                </span>
              )}
              {pendingCount > 0 && (
                <span className="absolute top-1.5 right-2.5 flex h-1.5 w-1.5">
                  <span className="motion-safe:animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-red-500"></span>
                </span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Alert banner if in Chat tab and actions are pending in Tool Logs */}
      {activeFeedTab === 'chat' && pendingCount > 0 && (
        <div className="mx-3 mt-2 p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-between text-[11px] text-yellow-300 motion-safe:animate-pulse-subtle shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-yellow-400" />
            <span>{pendingCount} tool command{pendingCount > 1 ? 's' : ''} pending approval.</span>
          </div>
          <button
            type="button"
            onClick={() => setActiveFeedTab('logs')}
            className="px-2 py-0.5 rounded bg-yellow-500/20 hover:bg-yellow-500/30 text-white font-bold transition-all text-[10px] focus-visible:ring-2 focus-visible:ring-yellow-500 focus-visible:outline-none"
          >
            Open Logs
          </button>
        </div>
      )}

      {/* Message Feed / Log Feed Container */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 bg-[#07080b]/30">
        
        {/* Chat Feed Mode */}
        {activeFeedTab === 'chat' && (
          messages.length === 0 ? (
            <div className="h-full flex flex-col justify-center items-center p-6 space-y-4 text-center">
              <div className="p-3 bg-violet-600/10 border border-violet-500/20 rounded-2xl glow-purple animate-pulse-subtle">
                <Sparkles className="w-6 h-6 text-violet-400" />
              </div>
              <h2 className="text-sm font-bold text-white tracking-tight">Welcome to DevPilot</h2>
              <p className="text-[10px] text-gray-550 max-w-[220px]">
                Your next-generation multi-agent coding engine. Ask a question or request a task code edit below.
              </p>
              
              <div className="grid grid-cols-2 gap-1.5 w-full pt-2">
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
                    className="p-2 text-left bg-white/2 border border-white/5 rounded-lg text-[9px] text-gray-450 hover:text-white hover:bg-[#151720] hover:border-white/10 transition-all truncate cursor-pointer focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
                  >
                    💡 {act.label}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages
                .filter(msg => msg.role === 'user' || msg.role === 'assistant')
                .map((msg) => {
                  const isUser = msg.role === 'user';
                  return (
                    <div
                      key={msg.id}
                      className={`group flex gap-2.5 max-w-[95%] items-start relative ${
                        isUser ? 'ml-auto flex-row-reverse' : ''
                      }`}
                    >
                      {/* Avatar */}
                      <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold shadow-md border ${
                        isUser 
                          ? 'bg-violet-650 text-white border-violet-500/30' 
                          : 'bg-zinc-800 text-violet-400 border-white/5'
                      }`}>
                        {isUser ? <User className="w-3.5 h-3.5" /> : <Sparkles className="w-3.5 h-3.5" />}
                      </div>

                      {/* Message Bubble & Details */}
                      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[calc(100%-2.5rem)]`}>
                        <div className={`p-3 rounded-2xl text-xs leading-relaxed whitespace-pre-wrap select-text shadow-sm ${
                          isUser
                            ? 'bg-violet-950/45 border border-violet-500/25 text-white rounded-tr-none'
                            : 'bg-[#151720] border border-white/5 text-gray-250 rounded-tl-none'
                        }`}>
                          {renderMessageContent(msg.content?.trim() || (msg.isConfirmPending ? "Executing operations and pending authorization..." : "Processing task operations..."))}
                        </div>

                        {/* Direct log reviewer link for assistant bubble if it's pending */}
                        {!isUser && msg.isConfirmPending && (
                          <div className="mt-1.5 w-full bg-violet-500/5 border border-violet-500/10 rounded-lg p-2 text-[10px] text-violet-300 flex items-center justify-between">
                            <span className="flex items-center gap-1.5 font-sans">
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                              <span>Authorizations pending in Tool Logs.</span>
                            </span>
                            <button
                              type="button"
                              onClick={() => setActiveFeedTab('logs')}
                              className="px-2 py-0.5 rounded bg-violet-500/20 hover:bg-violet-500/30 text-white font-bold transition-all focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
                            >
                              Review Now
                            </button>
                          </div>
                        )}

                        {/* Timestamp showing on hover */}
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 text-[9px] text-gray-500 mt-1 select-none font-mono">
                          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  );
                })
              }

              {/* Loader/Typing indicator if assistant is streaming/generating */}
              {showTypingIndicator && (
                <div className="flex gap-2.5 max-w-[95%] items-start">
                  <div className="w-7 h-7 rounded-full shrink-0 bg-zinc-800 text-violet-400 flex items-center justify-center border border-white/5">
                    <Sparkles className="w-3.5 h-3.5 animate-pulse-subtle" />
                  </div>
                  <div className="flex flex-col items-start max-w-[calc(100%-2.5rem)]">
                    <div className="p-3 bg-[#151720] border border-white/5 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-1.5 py-2.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce motion-reduce:animate-none" style={{ animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce motion-reduce:animate-none" style={{ animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce motion-reduce:animate-none" style={{ animationDelay: '300ms' }} />
                      <span className="text-[10px] text-gray-500 font-mono ml-2 select-none">
                        {statusMessage || 'Thinking...'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        )}

        {/* 3. Tool Execution Log Feed Mode */}
        {activeFeedTab === 'logs' && (
          toolMessagesCount === 0 ? (
            <div className="h-full flex flex-col justify-center items-center p-6 space-y-3 text-center">
              <div className="p-3.5 bg-white/5 border border-white/5 rounded-2xl text-gray-400">
                <Terminal className="w-6 h-6" />
              </div>
              <h2 className="text-sm font-bold text-white tracking-tight">No Tool Calls Yet</h2>
              <p className="text-[10px] text-gray-550 max-w-[200px]">
                When the agent makes directory listings, file edits, or runs terminal commands, they will be logged here.
              </p>
            </div>
          ) : (
            <div className="space-y-3 font-mono">
              {messages.map((msg) => {
                // RENDER: Completed Tool Cards
                if (msg.role === 'tool') {
                  const isSuccess = msg.status === 'success';
                  return (
                    <div key={msg.id} className="border border-white/5 bg-[#141620] rounded-xl p-3 space-y-2 text-xs shadow-sm">
                      {/* Tool Card Header */}
                      <div className="flex items-center justify-between border-b border-white/5 pb-2 font-mono">
                        <span className="text-[11px] font-bold text-gray-300">
                          TOOL: {msg.name || 'unknown_tool'}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase ${
                          isSuccess
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                          {isSuccess ? 'SUCCESS' : 'FAILED'}
                        </span>
                      </div>
                      
                      {/* Tool Card Body */}
                      <pre className="text-[10px] leading-normal text-gray-400 max-h-40 overflow-y-auto whitespace-pre-wrap select-text bg-black/25 p-2 rounded-lg border border-white/5 scrollbar-thin">
                        {msg.content}
                      </pre>
                    </div>
                  );
                }

                // RENDER: Pending Authorizations / Commands in Logs
                if (msg.isConfirmPending) {
                  // Case A: Smart Permission dialog
                  if (msg.isPermissionRequest) {
                    return (
                      <div key={msg.id} className="border border-violet-500/25 bg-[#161a25] rounded-xl p-3 space-y-3 shadow-md font-sans">
                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-white/5 pb-2 font-mono">
                          <span className="text-[11px] font-bold text-violet-300 flex items-center gap-1">
                            <Terminal className="w-3.5 h-3.5 text-violet-400" /> TOOL: run_command
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase border animate-pulse motion-reduce:animate-none ${
                            msg.permissionRisk === 'destructive' 
                              ? 'bg-red-500/15 text-red-400 border-red-500/20' 
                              : msg.permissionRisk === 'safe'
                              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
                              : 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20'
                          }`}>
                            {msg.permissionRisk || 'medium'} Risk
                          </span>
                        </div>

                        {/* Body content */}
                        <div className="space-y-2 text-[10px] text-gray-300 leading-normal">
                          {msg.permissionExplanation && (
                            <div className="bg-black/20 p-2.5 rounded-lg border border-white/5">
                              <span className="text-[9px] uppercase font-bold text-gray-500 block mb-1">Reason & Intent</span>
                              {msg.permissionExplanation}
                            </div>
                          )}

                          {msg.permissionReason && (
                            <div className="text-[9px] border border-violet-500/10 p-2 rounded bg-violet-500/5 italic text-violet-300">
                              💡 Risk Profile: {msg.permissionReason}
                            </div>
                          )}

                          {/* Editable command field */}
                          <div className="space-y-1 font-mono">
                            <span className="text-[9px] text-gray-500 block uppercase font-bold">Exact Command (Editable):</span>
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
                              className="w-full bg-black/40 font-mono text-[10px] border border-white/10 hover:border-violet-500/30 focus:border-violet-500/60 rounded p-2 text-white focus:outline-none transition-colors focus-visible:ring-2 focus-visible:ring-violet-500"
                            />
                          </div>

                          {/* Actions */}
                          <div className="grid grid-cols-2 gap-1.5 text-[9px] pt-1">
                            <button
                              type="button"
                              onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, true, 'once', editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || ''))}
                              className="py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-bold transition-all cursor-pointer text-center focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
                            >
                              Allow Once
                            </button>
                            <button
                              type="button"
                              onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, true, 'session', editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || ''))}
                              className="py-1.5 rounded-lg bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/25 text-violet-400 font-bold transition-all cursor-pointer text-center focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
                            >
                              Allow Session
                            </button>
                            <button
                              type="button"
                              onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, true, 'project', editingCommandId === msg.id ? editedCommandText : (msg.permissionCommand || ''))}
                              className="py-1.5 rounded-lg bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/25 text-violet-400 font-bold transition-all cursor-pointer text-center focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
                            >
                              Allow Project
                            </button>
                            <button
                              type="button"
                              onClick={() => msg.tool_call_id && onConfirmPermission && onConfirmPermission(msg.tool_call_id, false, 'once', '')}
                              className="py-1.5 rounded-lg bg-red-650/10 hover:bg-red-650/20 border border-red-500/20 text-red-405 font-bold transition-all cursor-pointer text-center focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none"
                            >
                              Deny
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  // Case B: Proposed file edits (diff hunk validation)
                  if (msg.confirmDiff) {
                    return (
                      <div key={msg.id} className="border border-violet-500/25 bg-[#161a25] rounded-xl p-3 space-y-3 shadow-md font-sans">
                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-white/5 pb-2 font-mono">
                          <span className="text-[11px] font-bold text-violet-300 flex items-center gap-1">
                            <FileDiff className="w-3.5 h-3.5 text-violet-450" /> TOOL: edit_file
                          </span>
                          <span className="px-2 py-0.5 rounded text-[8px] font-bold uppercase bg-yellow-500/10 border border-yellow-500/20 text-yellow-450 animate-pulse motion-reduce:animate-none font-mono">
                            PENDING APPROVAL
                          </span>
                        </div>

                        {/* Diff Metadata */}
                        <div className="text-[10px] text-gray-300 space-y-1.5">
                          <div className="flex items-center justify-between bg-black/20 p-2 rounded-lg border border-white/5">
                            <span className="font-semibold truncate max-w-[190px]">Path: {msg.confirmDiff.path}</span>
                            <span className="text-[9px] text-gray-500 uppercase font-mono">Diff</span>
                          </div>
                          
                          {/* Arguments text snippet */}
                          <div className="bg-black/25 p-2 rounded text-[9px] border border-white/5 max-h-20 overflow-y-auto font-mono text-gray-400">
                            <strong>Arguments:</strong>
                            <pre className="mt-1 whitespace-pre-wrap">{formatArgs(msg.confirmArgs)}</pre>
                          </div>
                        </div>

                        {/* Diff Hunks */}
                        {msg.confirmDiff.hunks && msg.confirmDiff.hunks.length > 0 && (
                          <div className="space-y-2">
                            <span className="text-[9px] uppercase font-bold text-gray-500 block">File Diff Hunks:</span>
                            {msg.confirmDiff.hunks.map((hunk: any, idx: number) => renderDiffHunk(msg.id, hunk, idx))}
                          </div>
                        )}

                        {/* Parent Controls */}
                        <div className="flex gap-2 text-[9px] pt-1 font-sans">
                          <button
                            onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
                            className="flex-1 py-1.5 rounded-lg border border-red-500/20 bg-red-655/10 hover:bg-red-655/20 text-red-400 font-bold flex items-center justify-center gap-1 transition-all focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:outline-none cursor-pointer"
                          >
                            <X className="w-3.5 h-3.5" /> Reject All
                          </button>
                          <button
                            onClick={() => {
                              if (msg.tool_call_id) {
                                const decisions = hunkDecisions[msg.id] || {};
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
                            className="flex-1 py-1.5 rounded-lg bg-violet-650 hover:bg-violet-600 text-white font-bold flex items-center justify-center gap-1 transition-all focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none cursor-pointer"
                          >
                            <Check className="w-3.5 h-3.5" /> Accept All Edits
                          </button>
                        </div>
                      </div>
                    );
                  }

                  // Case C: Dangerous command block
                  return (
                    <div key={msg.id} className="border border-red-500/25 bg-[#251515] rounded-xl p-3 space-y-3 shadow-md font-sans">
                      {/* Header */}
                      <div className="flex items-center justify-between border-b border-white/5 pb-2 font-mono">
                        <span className="text-[11px] font-bold text-red-400 flex items-center gap-1">
                          <Terminal className="w-3.5 h-3.5" /> TOOL: run_command
                        </span>
                        <span className="px-2 py-0.5 rounded text-[8px] font-bold uppercase bg-red-500/20 border border-red-500/30 text-red-400 animate-pulse motion-reduce:animate-none font-mono">
                          WARNING
                        </span>
                      </div>

                      {/* Body */}
                      <div className="space-y-2 text-[10px] text-gray-300">
                        <p className="text-[10px] leading-relaxed font-semibold text-red-400">
                          This command is flagged as potentially destructive. Please review:
                        </p>
                        <pre className="font-mono text-[9px] bg-black/40 p-2.5 rounded-lg border border-white/5 text-gray-400 overflow-x-auto select-all">
                          {msg.confirmArgs?.command}
                        </pre>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2 text-[9px] pt-1">
                        <button
                          onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
                          className="flex-1 py-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 text-gray-300 font-bold flex items-center justify-center gap-1 transition-all focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none cursor-pointer"
                        >
                          <X className="w-3.5 h-3.5" /> Cancel Execution
                        </button>
                        <button
                          onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, true)}
                          className="flex-1 py-1.5 rounded-lg bg-red-650 hover:bg-red-600 text-white font-bold flex items-center justify-center gap-1 transition-all focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:outline-none cursor-pointer"
                        >
                          <Play className="w-3.5 h-3.5" /> Run Command
                        </button>
                      </div>
                    </div>
                  );
                }

                return null;
              })}
            </div>
          )
        )}

        {/* Global stream loader status and Stop button */}
        {isGenerating && (
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#151720] border border-white/5 text-xs text-gray-300 w-full motion-safe:animate-pulse-subtle select-none">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 motion-safe:animate-ping shrink-0" />
              <span className="text-[10px] text-gray-400 truncate font-mono">
                {statusMessage || 'Analyzing workspace components...'}
              </span>
            </div>
            <button
              type="button"
              onClick={onCancelGeneration}
              className="px-2.5 py-1 bg-red-600/15 hover:bg-red-600/30 border border-red-500/20 hover:border-red-500/40 text-[9px] text-red-400 rounded-md transition-all font-semibold cursor-pointer shrink-0 focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:outline-none"
            >
              Stop
            </button>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* 5. Input Bar (fixed to bottom) */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-white/5 bg-[#0e1015] shrink-0">
        <div className="bg-[#151720] border border-white/5 rounded-xl p-3 flex flex-col gap-2 shadow-2xl focus-within:border-violet-500/35 transition-colors">
          {/* Text Area */}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything, @ to mention, / for actions"
            className="w-full max-h-32 min-h-[48px] bg-transparent text-xs text-gray-200 focus:outline-none resize-none scrollbar-none py-1 placeholder:text-gray-500 font-sans focus-visible:ring-2 focus-visible:ring-violet-500 rounded p-1"
          />

          {/* Bottom Toolbar Row */}
          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            {/* Left Side */}
            <div className="flex items-center gap-2">
              {/* Attach File Button */}
              <button
                type="button"
                className="p-1.5 hover:bg-white/5 hover:text-gray-255 text-gray-550 rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none cursor-pointer"
                title="Attach file context"
              >
                <Plus className="w-4 h-4" />
              </button>
              
              {/* Connection profile / Model provider selector dropdown */}
              <button
                type="button"
                onClick={onOpenSettings}
                className="flex items-center gap-1.5 hover:bg-white/5 hover:text-violet-300 text-violet-400 font-medium px-2.5 py-1 rounded-full bg-violet-500/5 border border-violet-500/10 transition-colors text-[10px] focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none cursor-pointer"
                title="Model profiles selector"
              >
                <span>{activeProfileName}</span>
                <ChevronDown className="w-3 h-3 text-violet-400 shrink-0" />
              </button>
            </div>

            {/* Right Side */}
            <div className="flex items-center gap-2.5 text-gray-500">
              {/* Token Usage Indicator */}
              <span className="text-[10px] text-gray-500 font-mono select-none" title="Token Usage">
                {contextTokens} ({contextPercentage}%)
              </span>
              
              {/* Keybinding hint */}
              <span className="text-[9px] text-gray-650 hidden sm:inline select-none font-sans">
                ctrl+p commands
              </span>
              
              {/* Microphone icon */}
              <button
                type="button"
                className="p-1.5 hover:bg-white/5 hover:text-gray-255 text-gray-550 rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none cursor-pointer"
                title="Voice input dictation"
              >
                <Mic className="w-4 h-4" />
              </button>

              {/* Send Button */}
              <button
                type="submit"
                disabled={!input.trim() || isGenerating}
                className="p-1.5 rounded-lg bg-[#8B5CF6] hover:bg-[#7c4dff] disabled:bg-transparent text-white disabled:text-gray-650 border border-violet-500/20 disabled:border-transparent transition-all focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:outline-none cursor-pointer disabled:cursor-not-allowed"
                title="Send message"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </form>

    </div>
  );
}
