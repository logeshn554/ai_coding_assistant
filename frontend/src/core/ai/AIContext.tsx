import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { useWorkspace } from '../workspace/WorkspaceContext';
import { useEditor } from '../editor/EditorContext';
import { useTerminal } from '../terminal/TerminalContext';
import { useGit } from '../git/GitContext';
import { useToast } from '../toast/ToastContext';

import type { ChatMessage, Session, SubTask, ChatMode, ToolExecutionItem } from '../../types/chat';

interface LiveFileChange { path: string; added: number; removed: number; }

interface AIContextType {
  messages: ChatMessage[];
  isGenerating: boolean;
  statusMessage: string | null;
  activeAgent: string | null;
  activeTask: string | null;
  collaborationLog: string[];
  subtasks: SubTask[];
  sessions: Session[];
  activeSessionId: string;
  isWsConnected: boolean;
  isModelFallback: boolean;
  contextTokens: string;
  contextPercentage: number;
  contextTokensRaw: number;
  contextTokensMax: number;
  wsRef: React.RefObject<WebSocket | null>;
  liveToolCalls: ToolExecutionItem[];
  liveFileChanges: LiveFileChange[];
  pendingFileChanges: string[];
  currentGoal: string;
  totalCostUsd: number;
  onSelectSession: (sessionId: string) => Promise<void>;
  onNewSession: () => Promise<void>;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onRenameSession: (sessionId: string, newTitle: string) => Promise<void>;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  handleSendMessage: (text: string, mode: ChatMode, autoApply: boolean, attachedFiles?: string[]) => void;
  handleConfirmTool: (toolCallId: string, approved: boolean, scope: string, hunkDecisions?: any) => void;
  handleConfirmPermission: (toolCallId: string, approved: boolean, scope: string, command?: string) => void;
  handleConfirmPortConflict: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  handleCancelGeneration: () => void;
  handleKillProcess: (procId: string) => void;
  handleSelectSession: (sessionId: string) => Promise<void>;
  handleNewSession: () => Promise<void>;
  handleDeleteSession: (sessionId: string) => Promise<void>;
  handleRenameSession: (sessionId: string, newTitle: string) => Promise<void>;
  handleApplyAllChanges: () => void;
  handleDiscardAllChanges: () => Promise<void>;
}

const AIContext = createContext<AIContextType | undefined>(undefined);

export const AIProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<string | null>(null);
  const [collaborationLog, setCollaborationLog] = useState<string[]>([]);
  const [subtasks, setSubtasks] = useState<SubTask[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState('default-session');
  const [liveToolCalls, setLiveToolCalls] = useState<ToolExecutionItem[]>([]);
  const [liveFileChanges, setLiveFileChanges] = useState<LiveFileChange[]>([]);
  const [pendingFileChanges, setPendingFileChanges] = useState<string[]>([]);

  const [currentGoal, setCurrentGoal] = useState('');
  const [totalCostUsd, setTotalCostUsd] = useState<number>(0.0);
  const toolStartTimesRef = useRef<Record<string, number>>({});
  
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [isModelFallback, setIsModelFallback] = useState(false);
  const [contextTokens, setContextTokens] = useState('0');
  const [contextPercentage, setContextPercentage] = useState(0);
  const [contextTokensRaw, setContextTokensRaw] = useState(0);
  const [contextTokensMax, setContextTokensMax] = useState(200000);

  const { workspacePath, triggerRefresh } = useWorkspace();
  const { setProposedDiff, handleSelectFile, openFiles } = useEditor();
  const {
    setActiveTerminalCommand,
    setActiveTerminalStatus,
    setActiveTerminalExitCode,
    setActiveTerminalElapsed,
    setActiveProcesses,
    setConsoleLogs,
    setBottomTab
  } = useTerminal();
  const { updateStatusBarInfo } = useGit();
  const { showToast } = useToast();

  const wsRef = useRef<WebSocket | null>(null);
  const lastAssistantMsgIdRef = useRef<string | null>(null);
  const reconnectDelayRef = useRef(1000);

  // Listen for localhost URL detections in terminal / process execution
  useEffect(() => {
    const handleLocalhostDetected = (e: Event) => {
      const detail = (e as CustomEvent<{ url: string; port: string }>).detail;
      if (detail?.url) {
        showToast(`Localhost server running at ${detail.url}`, 'info');
        setMessages((prev) => {
          const exists = prev.some((m) => typeof m.content === 'string' && m.content.includes(detail.url));
          if (exists) return prev;
          return [
            ...prev,
            {
              id: `localhost_${Date.now()}`,
              role: 'assistant',
              content: `🚀 **Localhost Server Detected**\n\nYour application server is running at: [${detail.url}](${detail.url})`
            }
          ];
        });
      }
    };
    window.addEventListener('devpilot-localhost-detected', handleLocalhostDetected);
    return () => window.removeEventListener('devpilot-localhost-detected', handleLocalhostDetected);
  }, [showToast]);

  // Debounced tokenization from the backend
  useEffect(() => {
    const updateTokenCount = async () => {
      try {
        const res = await fetch('/api/chat/tokenize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: messages.map(m => ({ role: m.role, content: m.content })),
            open_files: openFiles
          })
        });
        if (res.ok) {
          const data = await res.json();
          const tokens = data.tokens || 0;
          setContextTokens(tokens >= 1000 ? (tokens / 1000).toFixed(1) + 'K' : tokens.toString());
          setContextPercentage(Math.min(100, Math.round((tokens / 200000) * 100)));
        }
      } catch (e) {
        console.error('Failed to tokenize chat context:', e);
      }
    };

    const timer = setTimeout(updateTokenCount, 500);
    return () => clearTimeout(timer);
  }, [messages, openFiles]);

  useEffect(() => {
    const handleExplainError = (e: Event) => {
      const detail = (e as CustomEvent)?.detail;
      if (detail?.prompt) {
        handleSendMessage(detail.prompt, 'Agent', true);
      }
    };
    window.addEventListener('devpilot_explain_error', handleExplainError);
    return () => window.removeEventListener('devpilot_explain_error', handleExplainError);
  }, [isGenerating]);

  const fetchSessions = async (syncActive: boolean = false) => {
    try {
      const res = await fetch('/api/chat/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
        if (syncActive && data.active_session_id) {
          setActiveSessionId(data.active_session_id);
        }
      }
    } catch (e) {
      console.error('Failed to fetch sessions:', e);
    }
  };

  const fetchChatHistory = async () => {
    try {
      const res = await fetch('/api/chat/history');
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
      await fetchSessions(true);
    } catch (e) {
      console.error('Failed to load chat history:', e);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      const res = await fetch(`/api/chat/sessions/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveSessionId(sessionId);
        setMessages(data.session?.messages || []);
        await fetchSessions(false);
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'change_profile' }));
        }
      }
    } catch (e) {
      console.error('Failed to select session:', e);
    }
  };

  const handleNewSession = async () => {
    try {
      const res = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat' })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          setActiveSessionId(data.session.id);
          setMessages([]);
          await fetchSessions();
        }
      }
    } catch (e) {
      console.error('Failed to create new session:', e);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      const res = await fetch(`/api/chat/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await fetchSessions();
        const res2 = await fetch('/api/chat/sessions');
        if (res2.ok) {
          const data = await res2.json();
          const newActiveId = data.active_session_id;
          setActiveSessionId(newActiveId);
          const sessionDetailsRes = await fetch(`/api/chat/sessions/${newActiveId}`);
          if (sessionDetailsRes.ok) {
            const detailsData = await sessionDetailsRes.json();
            setMessages(detailsData.session?.messages || []);
          }
        }
      }
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
  };

  const handleRenameSession = async (sessionId: string, title: string) => {
    try {
      const res = await fetch(`/api/chat/sessions/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      });
      if (res.ok) {
        await fetchSessions();
      }
    } catch (e) {
      console.error('Failed to rename session:', e);
    }
  };

  const connectChatSocket = (guard?: { cancelled: boolean }) => {
    // Tear down any previously open/connecting socket
    if (wsRef.current) {
      const oldWs = wsRef.current;
      wsRef.current = null;
      oldWs.onopen = null;
      oldWs.onclose = null;
      oldWs.onerror = null;
      oldWs.onmessage = null;
      if (oldWs.readyState === WebSocket.OPEN) {
        oldWs.close();
      } else if (oldWs.readyState === WebSocket.CONNECTING) {
        oldWs.onopen = () => { try { oldWs.close(); } catch {} };
      }
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/chat?session_id=${activeSessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      // React StrictMode unmounts then remounts — if cleanup ran first, abort
      if (guard?.cancelled) {
        try { ws.close(); } catch {}
        return;
      }
      logger.info("Chat socket connected.");
      setIsWsConnected(true);
      reconnectDelayRef.current = 1000;
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      switch (data.type) {
        case 'text_delta':
          const currentAssistantId = lastAssistantMsgIdRef.current;
          if (currentAssistantId) {
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== currentAssistantId) return msg;
                const newContent = (msg.content || '') + data.content;
                
                // Parse run command blocks and store in localStorage
                const runMatch = newContent.match(/```run\s*\n([\s\S]*?)\n```/);
                if (runMatch) {
                  localStorage.setItem('devpilot_detected_run_command', runMatch[1].trim());
                }
                
                // Filter out raw JSON or reasoning objects
                const trimmed = newContent.trim();
                if (trimmed.startsWith('{')) {
                  try {
                    const parsed = JSON.parse(trimmed);
                    const steps: string[] = [];
                    if (parsed.reasoning) {
                      steps.push(parsed.reasoning);
                    }
                    if (parsed.descriptions && Array.isArray(parsed.descriptions)) {
                      steps.push(...parsed.descriptions);
                    }
                    if (parsed.agents && Array.isArray(parsed.agents)) {
                      steps.push(...parsed.agents.map((a: string) => `Routing: ${a}`));
                    }
                    
                    // Filter duplicate steps
                    const currentSteps = msg.thinkingSteps || [];
                    const uniqueNewSteps = steps.filter(s => !currentSteps.includes(s));
                    
                    return {
                      ...msg,
                      content: '', // Hide raw JSON content
                      thinkingSteps: [...currentSteps, ...uniqueNewSteps]
                    };
                  } catch {
                    // If it contains JSON routing keys but is not fully parsed yet, hide it from rendering raw JSON
                    if (trimmed.includes('"reasoning"') || trimmed.includes('"agents"') || trimmed.includes('"descriptions"')) {
                      return {
                        ...msg,
                        content: '', // Keep content hidden while streaming JSON
                      };
                    }
                  }
                }
                
                return { ...msg, content: newContent };
              })
            );
          }
          break;
        case 'thinking':
          const thinkingAssistantId = lastAssistantMsgIdRef.current;
          if (thinkingAssistantId && data.content) {
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id !== thinkingAssistantId) return msg;
                const currentSteps = msg.thinkingSteps || [];
                if (currentSteps.includes(data.content)) return msg;
                return {
                  ...msg,
                  thinkingSteps: [...currentSteps, data.content]
                };
              })
            );
          }
          break;
        case 'status':
          setStatusMessage(data.message);
          if (data.status === 'tool_executing' && data.tool_call?.name) {
            const tc = data.tool_call;
            toolStartTimesRef.current[tc.id] = Date.now();
            const toolType = (): ToolExecutionItem['tool'] => {
              const n = (tc.name || '').toLowerCase();
              if (n.includes('terminal') || n.includes('command')) return 'terminal';
              if (n.includes('read')) return 'file_read';
              if (n.includes('edit') || n.includes('write')) return 'file_edit';
              if (n.includes('search')) return 'search';
              if (n.includes('git')) return 'git';
              return 'other';
            };
            const displayName = tc.name.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
            const paramLabel = tc.args?.path || tc.args?.query || tc.args?.command || '';
            setLiveToolCalls(prev => [
              ...prev,
              { id: tc.id, tool: toolType(), name: displayName, params: { path: paramLabel }, status: 'running' }
            ]);
          }
          break;
        case 'tool_result': {
          const isSuccess = data.status === 'success';
          const elapsed = toolStartTimesRef.current[data.tool_call_id]
            ? Date.now() - toolStartTimesRef.current[data.tool_call_id]
            : undefined;
          delete toolStartTimesRef.current[data.tool_call_id];
          setLiveToolCalls(prev => prev.map(t =>
            t.id === data.tool_call_id
              ? { ...t, status: isSuccess ? 'success' : 'error', durationMs: elapsed, output: String(data.result || '').slice(0, 200) }
              : t
          ));
          // Track file write/edit operations for the live file changes list and pending changes review bar
          if (data.name === 'write_file' || data.name === 'edit_file' || (data.name && data.name.includes('file'))) {
            const rawPath: string = data.args?.path || String(data.result || '').match(/([^\s]+\.\w+)/)?.[1] || '';
            if (rawPath && rawPath !== 'unknown') {
              setLiveFileChanges(prev => {
                const existing = prev.find(f => f.path === rawPath);
                if (existing) return prev;
                return [...prev, { path: rawPath, added: 0, removed: 0 }];
              });
              setPendingFileChanges(prev => {
                if (prev.includes(rawPath)) return prev;
                return [...prev, rawPath];
              });
            }
          }

          setMessages((prev) => [
            ...prev,
            {
              id: `tool_${data.tool_call_id}_${Date.now()}`,
              role: 'tool',
              name: data.name,
              tool_call_id: data.tool_call_id,
              content: data.result,
              status: isSuccess ? 'success' : 'error'
            }
          ]);
          triggerRefresh();
          updateStatusBarInfo();
          break;
        }
        case 'confirm_request':
          setStatusMessage(null);
          if (data.diff) {
            setProposedDiff({
              path: data.diff.path,
              original: data.diff.original,
              proposed: data.diff.proposed
            });
            handleSelectFile(data.diff.path);
          }
          const currentConfirmId = lastAssistantMsgIdRef.current;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === currentConfirmId
                ? {
                    ...msg,
                    isConfirmPending: true,
                    tool_call_id: data.tool_call_id,
                    confirmArgs: data.args,
                    confirmDiff: data.diff
                      ? {
                          path: data.diff.path,
                          original: data.diff.original,
                          proposed: data.diff.proposed,
                          hunks: data.diff.hunks
                        }
                      : undefined
                  }
                : msg
            )
          );
          break;
        case 'session_done':
          setIsGenerating(false);
          setStatusMessage(null);
          lastAssistantMsgIdRef.current = null;
          updateStatusBarInfo();
          if (typeof data.total_cost_usd === 'number') {
            setTotalCostUsd(prev => prev + data.total_cost_usd);
          }
          break;
        case 'agent_state':
          setActiveAgent(data.active_agent);
          setActiveTask(data.active_task);
          setCollaborationLog(data.collaboration_log);
          setSubtasks(data.subtasks || []);
          break;
        case 'permission_request':
          setIsGenerating(false);
          setStatusMessage(null);
          setMessages((prev) => [
            ...prev,
            {
              id: `perm_${data.tool_call_id}_${Date.now()}`,
              role: 'assistant',
              content: `Permission requested: \`${data.command}\``,
              tool_call_id: data.tool_call_id,
              isConfirmPending: true,
              isPermissionRequest: true,
              permissionCommand: data.command,
              permissionRisk: data.risk,
              permissionReason: data.reason,
              permissionExplanation: data.explanation,
              confirmArgs: data.args
            }
          ]);
          break;
        case 'terminal_status':
          setActiveTerminalCommand(data.command);
          setActiveTerminalStatus(data.status);
          setActiveTerminalExitCode(data.exit_code);
          setActiveTerminalElapsed(data.elapsed);
          if (data.status === 'running') {
            setBottomTab('terminal');
          }
          break;
        case 'terminal_stream':
          if (data.content) {
            setConsoleLogs((prev) => [...prev, data.content]);
            window.dispatchEvent(new CustomEvent('devpilot_terminal_stream', { detail: data.content }));
          }
          break;
        case 'processes_update':
          setActiveProcesses(data.processes || []);
          break;
        case 'port_conflict_request':
          setIsGenerating(false);
          setStatusMessage(null);
          setMessages((prev) => [
            ...prev,
            {
              id: `port_conflict_${data.tool_call_id}_${Date.now()}`,
              role: 'assistant',
              content: `⚠️ Port conflict: Port ${data.port} is already in use by process \`${data.process_name}\` (PID: ${data.pid}).`,
              tool_call_id: data.tool_call_id,
              isConfirmPending: true,
              isPortConflictRequest: true,
              portConflictPort: data.port,
              portConflictPid: data.pid,
              portConflictProcessName: data.process_name
            }
          ]);
          break;
        case 'context_update':
          if (typeof data.tokens_used === 'number' && typeof data.tokens_max === 'number') {
            const used: number = data.tokens_used;
            const max: number = data.tokens_max;
            const pct: number = data.percentage ?? Math.min(100, Math.round((used / max) * 100));
            setContextTokensRaw(used);
            setContextTokensMax(max);
            setContextTokens(used >= 1000 ? (used / 1000).toFixed(1) + 'K' : String(used));
            setContextPercentage(pct);
          }
          break;
        case 'context_compressed':
          if (data.summary) {
            setMessages((prev) => [
              ...prev,
              {
                id: `ctx_compressed_${Date.now()}`,
                role: 'system' as const,
                content: `🗜️ Context compressed: ${data.summary}`,
                isContextCompressed: true,
                timestamp: Math.floor(Date.now() / 1000)
              }
            ]);
            showToast('Context compressed — oldest messages summarized to save space.', 'info');
          }
          break;
        case 'model_fallback':
          setIsModelFallback(true);
          showToast(`⚠️ Configured model failed! Fallback to local Ollama llama3. Error: ${data.error}`, 'error');
          break;
        default:
          break;
      }
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) {
        // This close was intentional (cleanup) or a new socket is already active
        return;
      }
      setIsWsConnected(false);
      logger.info(`Chat socket closed. Reconnecting in ${reconnectDelayRef.current}ms...`);
      setTimeout(() => {
        if (wsRef.current !== ws) return;
        connectChatSocket(guard);
      }, reconnectDelayRef.current);
      reconnectDelayRef.current = Math.min(16000, reconnectDelayRef.current * 2);
    };
  };

  const handleSendMessage = (text: string, mode: ChatMode, autoApply: boolean, attachedFiles?: string[]) => {
    if (!text.trim() || isGenerating) return;

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      showToast('Chat connection is not ready. Reconnecting...', 'error');
      return;
    }

    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `assistant_${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) },
      { id: assistantMsgId, role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) }
    ]);

    lastAssistantMsgIdRef.current = assistantMsgId;
    setIsGenerating(true);
    setStatusMessage('Analyzing workspace...');
    // Reset plan tab state for new message
    setLiveToolCalls([]);
    setLiveFileChanges([]);
    setCurrentGoal(text.slice(0, 100));
    localStorage.removeItem('devpilot_detected_run_command');

    // Map 'Auto' to ask-mode behavior (direct LLM call, no orchestrator)
    const effectiveMode = mode === 'Auto' ? 'Ask' : mode;

    wsRef.current.send(
      JSON.stringify({
        type: 'user_message',
        text,
        mode: effectiveMode,
        auto_apply: autoApply,
        attached_files: attachedFiles && attachedFiles.length > 0 ? attachedFiles : undefined,
      })
    );
  };

  const handleConfirmTool = (toolCallId: string, approved: boolean, scope: string, hunkDecisions?: any) => {
    setProposedDiff(null);
    setMessages((prev) =>
      prev.map((msg) => (msg.tool_call_id === toolCallId ? { ...msg, isConfirmPending: false } : msg))
    );
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'confirm_response',
          tool_call_id: toolCallId,
          approved,
          scope,
          hunk_decisions: hunkDecisions
        })
      );
    }
  };

  const handleConfirmPermission = (
    toolCallId: string,
    approved: boolean,
    scope: string,
    command?: string
  ) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.tool_call_id === toolCallId ? { ...msg, isConfirmPending: false } : msg))
    );
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'confirm_response',
          tool_call_id: toolCallId,
          approved,
          scope,
          command
        })
      );
    }
  };

  const handleConfirmPortConflict = (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => {
    setMessages((prev) =>
      prev.map((msg) => (msg.tool_call_id === toolCallId ? { ...msg, isConfirmPending: false } : msg))
    );
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'confirm_response',
          tool_call_id: toolCallId,
          approved: action !== 'cancel',
          scope: 'once',
          command: action // We piggyback action name as confirmation parameters
        })
      );
    }
  };

  const handleCancelGeneration = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'cancel_generation' }));
    }
    setIsGenerating(false);
    setStatusMessage(null);
    lastAssistantMsgIdRef.current = null;
  };

  const handleKillProcess = (procId: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop_process', process_id: procId }));
    }
  };

  // Reconnect socket and load history when activeSessionId changes
  useEffect(() => {
    const guard = { cancelled: false };
    connectChatSocket(guard);
    fetchChatHistory();
    setIsModelFallback(false); // Reset fallback warnings on session change
    return () => {
      guard.cancelled = true;
      if (wsRef.current) {
        const socket = wsRef.current;
        wsRef.current = null;
        socket.onopen = null;
        socket.onclose = null;
        socket.onerror = null;
        socket.onmessage = null;
        if (socket.readyState === WebSocket.OPEN) {
          socket.close();
        } else if (socket.readyState === WebSocket.CONNECTING) {
          // Don't call close() — onopen handler checks guard.cancelled
        }
      }
    };
  }, [activeSessionId]);

  // Hot reload workspace profiles
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'change_profile' }));
    }
  }, [workspacePath]);

  const handleApplyAllChanges = () => {
    setPendingFileChanges([]);
    setLiveFileChanges([]);
    triggerRefresh();
    showToast('All file changes applied successfully!', 'success');
  };

  const handleDiscardAllChanges = async () => {
    for (const filePath of pendingFileChanges) {
      try {
        await fetch('/api/rollback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: filePath })
        });
      } catch (e) {
        console.error(`Failed to rollback ${filePath}:`, e);
      }
    }
    setPendingFileChanges([]);
    setLiveFileChanges([]);
    triggerRefresh();
    showToast('File changes discarded and reverted to original state.', 'info');
  };

  return (
    <AIContext.Provider
      value={{
        messages,
        isGenerating,
        statusMessage,
        activeAgent,
        activeTask,
        collaborationLog,
        subtasks,
        sessions,
        activeSessionId,
        isWsConnected,
        isModelFallback,
        contextTokens,
        contextPercentage,
        contextTokensRaw,
        contextTokensMax,
        wsRef,
        liveToolCalls,
        liveFileChanges,
        pendingFileChanges,
        currentGoal,
        totalCostUsd,
        onSelectSession: handleSelectSession,
        onNewSession: handleNewSession,
        onDeleteSession: handleDeleteSession,
        onRenameSession: handleRenameSession,
        setMessages,
        handleSendMessage,
        handleConfirmTool,
        handleConfirmPermission,
        handleConfirmPortConflict,
        handleCancelGeneration,
        handleKillProcess,
        handleSelectSession,
        handleNewSession,
        handleDeleteSession,
        handleRenameSession,
        handleApplyAllChanges,
        handleDiscardAllChanges
      }}
    >

      {children}
    </AIContext.Provider>
  );
};

export const useAI = () => {
  const context = useContext(AIContext);
  if (!context) {
    throw new Error('useAI must be used within an AIProvider');
  }
  return context;
};

// Global logger helper
const logger = {
  info: (msg: string) => console.log(`[AIContext] INFO: ${msg}`),
  error: (msg: string) => console.error(`[AIContext] ERROR: ${msg}`)
};
