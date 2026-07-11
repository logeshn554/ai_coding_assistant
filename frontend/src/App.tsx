import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import SearchSidebar from './components/SearchSidebar';
import GitSidebar from './components/GitSidebar';
import RunDebugSidebar from './components/RunDebugSidebar';
import ExtensionsSidebar from './components/ExtensionsSidebar';
import TestingSidebar from './components/TestingSidebar';
import PackagesSidebar from './components/PackagesSidebar';
import EditorArea from './components/EditorArea';
import TerminalArea from './components/TerminalArea';
import ChatPanel from './components/ChatPanel';
import type { ChatMessage } from './components/ChatPanel';
import SettingsModal from './components/SettingsModal';
import { Folder, Search, Settings, ChevronDown, GitBranch, Play, Puzzle, Beaker, Box } from 'lucide-react';

export default function App() {
  // File Explorer and Editor tab states
  const [openFiles, setOpenFiles] = useState<string[]>([]);
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Dynamic Workspace states
  const [workspacePath, setWorkspacePath] = useState('');
  const [isOpenFolderModalOpen, setIsOpenFolderModalOpen] = useState(false);
  const [folderPathInput, setFolderPathInput] = useState('');

  // Sidebar toggling (Explorer, Search, Git, Debug, Extensions, Testing, Packages)
  const [sidebarTab, setSidebarTab] = useState<'explorer' | 'search' | 'git' | 'debug' | 'extensions' | 'testing' | 'packages'>('explorer');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // VS Code top menu dropdown state
  const [activeMenu, setActiveMenu] = useState<'file' | 'help' | null>(null);

  // AI chat states
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [activeProfileName, setActiveProfileName] = useState<string>('Default');
  const [proposedDiff, setProposedDiff] = useState<{
    path: string;
    original: string;
    proposed: string;
  } | null>(null);

  // Collaboration and Terminal state hooks
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<string | null>(null);
  const [collaborationLog, setCollaborationLog] = useState<string[]>([]);
  const [subtasks, setSubtasks] = useState<any[]>([]);

  const [activeTerminalCommand, setActiveTerminalCommand] = useState<string | null>(null);
  const [activeTerminalStatus, setActiveTerminalStatus] = useState<'running' | 'completed' | 'failed' | null>(null);
  const [activeTerminalExitCode, setActiveTerminalExitCode] = useState<number | null>(null);
  const [activeTerminalElapsed, setActiveTerminalElapsed] = useState<number | null>(null);

  // Settings modal state
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Status Bar and Command Palette states
  const [statusBarBranch, setStatusBarBranch] = useState('Not a Git Repo');
  const [statusBarDebug, setStatusBarDebug] = useState('Idle');
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [commandSearch, setCommandSearch] = useState('');
  const [gitChanges, setGitChanges] = useState<Record<string, string>>({});

  // Sleek React Toast Notification System
  interface Toast {
    id: string;
    message: string;
    type: 'success' | 'info' | 'error';
  }
  const [toasts, setToasts] = useState<Toast[]>([]);
  const showToast = (message: string, type: 'success' | 'info' | 'error' = 'success') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const updateStatusBarInfo = async () => {
    try {
      const gitRes = await fetch('/api/git/status');
      if (gitRes.ok) {
        const gitData = await gitRes.json();
        setStatusBarBranch(gitData.branch || 'Not a Git Repo');
        
        const mapping: Record<string, string> = {};
        if (gitData.files) {
          gitData.files.forEach((f: any) => {
            mapping[f.path] = f.status;
          });
        }
        setGitChanges(mapping);
      }

      const debugRes = await fetch('/api/debug/status');
      if (debugRes.ok) {
        const debugData = await debugRes.json();
        setStatusBarDebug(debugData.running ? 'Running' : 'Idle');
      }
    } catch (e) {
      // ignore
    }
  };

  useEffect(() => {
    updateStatusBarInfo();
    const timer = setInterval(updateStatusBarInfo, 4000);
    return () => clearInterval(timer);
  }, [workspacePath]);

  // Command palette toggle keyboard shortcut (Ctrl+Shift+P / Cmd+Shift+P)
  useEffect(() => {
    const handlePaletteKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        setIsCommandPaletteOpen(prev => !prev);
      } else if (e.key === 'Escape') {
        setIsCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handlePaletteKey);
    return () => window.removeEventListener('keydown', handlePaletteKey);
  }, []);

  const fetchChatHistory = async () => {
    try {
      const res = await fetch('/api/chat/history');
      if (res.ok) {
        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
        }
      }
    } catch (e) {
      console.error('Failed to load chat history:', e);
    }
  };

  const wsRef = useRef<WebSocket | null>(null);
  const lastAssistantMsgIdRef = useRef<string | null>(null);

  // Fetch workspace path and connect websocket
  useEffect(() => {
    fetchWorkspacePath();
    connectChatSocket();
    fetchActiveProfile();
    fetchChatHistory();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Persist chat history to backend when it changes
  useEffect(() => {
    const timer = setTimeout(() => {
      fetch('/api/chat/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages })
      }).catch(err => console.error('Failed to save chat history:', err));
    }, 1000);
    return () => clearTimeout(timer);
  }, [messages]);

  // Close menus when clicking outside
  useEffect(() => {
    const handleOutsideClick = () => {
      setActiveMenu(null);
    };
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, []);

  const fetchWorkspacePath = async () => {
    try {
      const res = await fetch('/api/workspace');
      const data = await res.json();
      setWorkspacePath(data.workspace);
      setFolderPathInput(data.workspace);
    } catch (e) {
      console.error(e);
    }
  };

  const connectChatSocket = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'text_delta':
          setMessages((prev) => {
            const lastId = lastAssistantMsgIdRef.current;
            return prev.map((msg) => {
              if (msg.id === lastId) {
                return { ...msg, content: (msg.content || '') + data.content };
              }
              return msg;
            });
          });
          break;

        case 'status':
          setStatusMessage(data.message);
          break;

        case 'tool_result':
          const isSuccess = data.status === 'success';
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
          setRefreshTrigger((prev) => prev + 1);
          break;

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

          setMessages((prev) => {
            const lastId = lastAssistantMsgIdRef.current;
            return prev.map((msg) => {
              if (msg.id === lastId) {
                return {
                  ...msg,
                  isConfirmPending: true,
                  tool_call_id: data.tool_call_id,
                  confirmArgs: data.args,
                  confirmDiff: data.diff ? {
                    path: data.diff.path,
                    original: data.diff.original,
                    proposed: data.diff.proposed,
                    hunks: data.diff.hunks
                  } : undefined
                };
              }
              return msg;
            });
          });
          break;

        case 'session_done':
          setIsGenerating(false);
          setStatusMessage(null);
          lastAssistantMsgIdRef.current = null;
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
          break;
      }
    };

    ws.onclose = () => {
      console.log('Chat WebSocket closed. Reconnecting in 3s...');
      setTimeout(connectChatSocket, 3000);
    };
  };

  const fetchActiveProfile = async () => {
    try {
      const res = await fetch('/api/profiles');
      const data = await res.json();
      const active = data.profiles.find((p: any) => p.id === data.active_profile_id);
      if (active) {
        setActiveProfileName(active.name);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendMessage = (text: string, mode: 'Ask' | 'Plan' | 'Agent', autoApply: boolean) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      alert('Connection lost. Please try again in a few seconds.');
      return;
    }

    setActiveAgent(null);
    setActiveTask(null);
    setCollaborationLog([]);
    setSubtasks([]);

    setIsGenerating(true);
    setStatusMessage('Thinking...');

    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `assistant_${Date.now()}`;
    lastAssistantMsgIdRef.current = assistantMsgId;

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: 'user', content: text },
      { id: assistantMsgId, role: 'assistant', content: '' }
    ]);

    wsRef.current.send(JSON.stringify({
      type: 'user_message',
      text,
      mode,
      auto_apply: autoApply
    }));
  };

  const handleConfirmTool = (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    setProposedDiff(null);

    wsRef.current.send(JSON.stringify({
      type: 'confirm_response',
      tool_call_id: toolCallId,
      approved,
      hunk_decisions: hunkDecisions
    }));

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.tool_call_id === toolCallId) {
          return { ...msg, isConfirmPending: false };
        }
        return msg;
      })
    );

    setIsGenerating(true);
    setStatusMessage('Processing approval...');
  };

  const handleCancelGeneration = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'cancel_generation' }));
    }
    setIsGenerating(false);
    setStatusMessage(null);
  };

  const handleConfirmPermission = (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    wsRef.current.send(JSON.stringify({
      type: 'confirm_response',
      tool_call_id: toolCallId,
      approved,
      scope,
      command
    }));

    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.tool_call_id === toolCallId) {
          return { ...msg, isConfirmPending: false };
        }
        return msg;
      })
    );

    setIsGenerating(approved);
    if (approved) {
      setStatusMessage('Executing command...');
    } else {
      setStatusMessage(null);
    }
  };

  const handleSelectFile = (filePath: string) => {
    if (!openFiles.includes(filePath)) {
      setOpenFiles((prev) => [...prev, filePath]);
    }
    setActiveFilePath(filePath);
  };

  const handleFileClose = (filePath: string) => {
    const newOpenFiles = openFiles.filter((p) => p !== filePath);
    setOpenFiles(newOpenFiles);
    
    if (activeFilePath === filePath) {
      setActiveFilePath(newOpenFiles.length > 0 ? newOpenFiles[newOpenFiles.length - 1] : null);
    }
  };

  const handleSettingsChanged = () => {
    fetchActiveProfile();
    showToast('AI Profile settings updated!', 'info');
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'change_profile' }));
    }
  };

  // Helper to change workspace path in backend and reload
  const changeWorkspacePath = async (path: string) => {
    try {
      const res = await fetch('/api/workspace/change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await res.json();
      
      if (res.ok && data.success) {
        setWorkspacePath(data.workspace);
        setFolderPathInput(data.workspace);
        setOpenFiles([]);
        setActiveFilePath(null);
        setRefreshTrigger((prev) => prev + 1);
        setIsOpenFolderModalOpen(false);
        showToast(data.workspace ? 'Workspace folder opened successfully!' : 'Workspace folder closed.', 'success');

        // Force hot-reload WebSocket connections by closing them
        if (wsRef.current) {
          wsRef.current.close();
        }

        // Add System message indicating new directory
        setMessages((prev) => [
          ...prev,
          {
            id: `sys_${Date.now()}`,
            role: 'system',
            content: data.workspace 
              ? `[System]: Opened workspace folder: ${data.workspace}`
              : `[System]: Workspace closed.`
          }
        ]);
      } else {
        alert('Failed to open folder: ' + data.detail);
      }
    } catch (err) {
      alert('Error opening folder: ' + err);
    }
  };

  // Open Folder handler (checks for pywebview native selector first)
  const handleOpenWorkspaceFolder = async () => {
    const win = window as any;
    if (win.pywebview && win.pywebview.api && typeof win.pywebview.api.select_folder === 'function') {
      try {
        const selectedPath = await win.pywebview.api.select_folder();
        if (selectedPath) {
          await changeWorkspacePath(selectedPath);
        }
      } catch (err) {
        alert('Failed to open native folder dialog: ' + err);
      }
    } else {
      // Fallback to manual text input modal
      setIsOpenFolderModalOpen(true);
    }
  };

  const handleOpenFolderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderPathInput.trim()) return;
    await changeWorkspacePath(folderPathInput.trim());
  };

  const getWorkspaceFolderBasename = () => {
    if (!workspacePath) return 'No Folder';
    const normalized = workspacePath.replace(/\\/g, '/');
    return normalized.split('/').pop() || normalized;
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0d0f12] text-gray-200 overflow-hidden font-sans select-none">
      
      {/* VS Code Title Menu bar */}
      <div className="h-[35px] border-b border-white/5 bg-[#0e1014] flex items-center px-3 justify-between shrink-0 select-none z-30">
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-400 to-fuchsia-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded bg-gradient-to-r from-violet-500 to-fuchsia-500 animate-pulse-subtle" />
            DevPilot
          </span>
          
          {/* File Menu */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActiveMenu(activeMenu === 'file' ? null : 'file');
              }}
              className={`px-3 py-1 text-xs rounded hover:bg-white/5 transition-colors flex items-center gap-1 ${
                activeMenu === 'file' ? 'bg-white/5 text-white' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              File <ChevronDown className="w-3 h-3" />
            </button>
            {activeMenu === 'file' && (
              <div className="absolute left-0 mt-1 w-48 bg-[#111318] border border-white/5 rounded-lg shadow-2xl py-1 z-40 text-xs text-gray-400">
                <button
                  onClick={() => {
                    setActiveMenu(null);
                    handleOpenWorkspaceFolder();
                  }}
                  className="w-full text-left px-4 py-2 hover:bg-white/5 hover:text-white transition-colors"
                >
                  Open Folder...
                </button>
                {workspacePath && (
                  <>
                    <button
                      onClick={() => {
                        setActiveMenu(null);
                        changeWorkspacePath("");
                      }}
                      className="w-full text-left px-4 py-2 hover:bg-red-600/20 hover:text-red-400 transition-colors"
                    >
                      Close Folder
                    </button>
                  </>
                )}
                <div className="border-t border-white/5 my-1" />
                <button
                  onClick={() => setRefreshTrigger(prev => prev + 1)}
                  className="w-full text-left px-4 py-2 hover:bg-white/5 hover:text-white transition-colors"
                >
                  Refresh File Tree
                </button>
              </div>
            )}
          </div>

          {/* Help Menu */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActiveMenu(activeMenu === 'help' ? null : 'help');
              }}
              className={`px-3 py-1 text-xs rounded hover:bg-white/5 transition-colors flex items-center gap-1 ${
                activeMenu === 'help' ? 'bg-white/5 text-white' : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Help <ChevronDown className="w-3 h-3" />
            </button>
            {activeMenu === 'help' && (
              <div className="absolute left-0 mt-1 w-52 bg-[#111318] border border-white/5 rounded-lg shadow-2xl py-2 px-4 z-40 text-xs text-gray-400 space-y-1.5">
                <p className="font-semibold text-white">DevPilot v1.0.0</p>
                <p>AI Code Editor Shell</p>
                <div className="border-t border-white/5 my-1" />
                <p className="text-[10px] text-gray-500">Shortcut: Ctrl+S to save files.</p>
              </div>
            )}
          </div>
        </div>

        {/* Center Path Indicator */}
        <div className="text-[11px] text-gray-500 font-mono truncate max-w-lg select-text">
          {activeFilePath ? `${activeFilePath} — ` : ''}{workspacePath}
        </div>

        {/* Workspace Folder name badge */}
        <div className="text-[10px] bg-violet-600/10 border border-violet-500/20 text-violet-400 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide select-none">
          {getWorkspaceFolderBasename()}
        </div>
      </div>

      {/* Main layout container */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Activity Bar (50px) */}
        <div className="w-[50px] bg-[#181818] border-r border-white/5 flex flex-col justify-between py-2 shrink-0 select-none">
          <div className="flex flex-col w-full">
            {[
              { id: 'explorer', icon: Folder, label: 'Explorer' },
              { id: 'search', icon: Search, label: 'Search' },
              { id: 'git', icon: GitBranch, label: 'Source Control' },
              { id: 'debug', icon: Play, label: 'Run & Debug' },
              { id: 'extensions', icon: Puzzle, label: 'Extensions' },
              { id: 'testing', icon: Beaker, label: 'Testing' },
              { id: 'packages', icon: Box, label: 'Dependencies' }
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = isSidebarOpen && sidebarTab === tab.id;
              return (
                <div key={tab.id} className="relative group w-full flex justify-center py-2">
                  {/* Active Left Accent Bar (3px blue/pink gradient) */}
                  {isActive && (
                    <div className="absolute left-0 top-2 bottom-2 w-[3px] bg-gradient-to-b from-violet-500 to-fuchsia-500 rounded-r" />
                  )}
                  <button
                    onClick={() => {
                      if (isSidebarOpen && sidebarTab === tab.id) {
                        setIsSidebarOpen(false);
                      } else {
                        setSidebarTab(tab.id as any);
                        setIsSidebarOpen(true);
                      }
                    }}
                    className={`p-2 rounded-lg transition-all duration-200 hover:scale-110 flex items-center justify-center ${
                      isActive
                        ? 'bg-black/20 text-white'
                        : 'text-gray-500 hover:text-gray-200'
                    }`}
                    title={tab.label}
                  >
                    <Icon className="w-[20px] h-[20px]" />
                  </button>
                </div>
              );
            })}
          </div>

          <div className="flex flex-col w-full items-center py-2">
            {/* Settings Button */}
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2 text-gray-500 hover:text-gray-205 transition-colors"
              title="Settings"
            >
              <Settings className="w-[20px] h-[20px]" />
            </button>
          </div>
        </div>

        {/* Dynamic Sidebar Explorer/Search/Git/RunDebug/Extensions/Testing/Packages Panels (260px) */}
        {isSidebarOpen && (
          <div className="w-[260px] h-full shrink-0 border-r border-white/5 bg-[#0e1014]">
            {sidebarTab === 'explorer' && (
              <Sidebar
                onSelectFile={handleSelectFile}
                selectedFilePath={activeFilePath}
                refreshTrigger={refreshTrigger}
                workspacePath={workspacePath}
                onOpenFolder={handleOpenWorkspaceFolder}
                gitChanges={gitChanges}
              />
            )}
            {sidebarTab === 'search' && (
              <SearchSidebar onSelectFile={handleSelectFile} />
            )}
            {sidebarTab === 'git' && (
              <GitSidebar />
            )}
            {sidebarTab === 'debug' && (
              <RunDebugSidebar />
            )}
            {sidebarTab === 'extensions' && (
              <ExtensionsSidebar />
            )}
            {sidebarTab === 'testing' && (
              <TestingSidebar />
            )}
            {sidebarTab === 'packages' && (
              <PackagesSidebar />
            )}
          </div>
        )}

        {/* Center Panels (Monaco Editor & Terminal) */}
        <div className="flex-1 h-full flex flex-col min-w-0">
          <div className="h-[70%] border-b border-white/5 overflow-hidden">
            <EditorArea
              activeFilePath={activeFilePath}
              openFiles={openFiles}
              onFileClose={handleFileClose}
              onFileSelect={handleSelectFile}
              proposedDiff={proposedDiff}
              onRefreshWorkspace={() => setRefreshTrigger(prev => prev + 1)}
              refreshTrigger={refreshTrigger}
            />
          </div>
          <div className="h-[30%] overflow-hidden bg-[#0d0f12]">
            <TerminalArea 
              workspacePath={workspacePath} 
              activeTerminalCommand={activeTerminalCommand}
              activeTerminalStatus={activeTerminalStatus}
              activeTerminalExitCode={activeTerminalExitCode}
              activeTerminalElapsed={activeTerminalElapsed}
            />
          </div>
        </div>

        {/* Right Panel (AI Sidebar) */}
        <div className="w-[380px] h-full shrink-0">
          {(() => {
            let totalChars = 0;
            messages.forEach(m => {
              totalChars += (m.content || '').length;
              if (m.tool_calls) totalChars += JSON.stringify(m.tool_calls).length;
            });
            totalChars += openFiles.length * 8000;
            const estimatedTokens = Math.max(120, Math.round(totalChars / 3.8));
            const maxTokens = 128000;
            const percentage = Math.min(100, Math.round((estimatedTokens / maxTokens) * 100));
            let formattedTokens = '';
            if (estimatedTokens >= 1000) {
              formattedTokens = (estimatedTokens / 1000).toFixed(1) + 'K';
            } else {
              formattedTokens = estimatedTokens.toString();
            }
            return (
              <ChatPanel
                messages={messages}
                onSendMessage={handleSendMessage}
                onConfirmTool={handleConfirmTool}
                onConfirmPermission={handleConfirmPermission}
                isGenerating={isGenerating}
                statusMessage={statusMessage}
                activeProfileName={activeProfileName}
                onOpenSettings={() => setIsSettingsOpen(true)}
                onCancelGeneration={handleCancelGeneration}
                activeAgent={activeAgent}
                activeTask={activeTask}
                collaborationLog={collaborationLog}
                subtasks={subtasks}
                contextTokens={formattedTokens}
                contextPercentage={percentage}
              />
            );
          })()}
        </div>

      </div>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onProfileChanged={handleSettingsChanged}
      />

      {/* Open Folder Modal Dialog */}
      {isOpenFolderModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <form 
            onSubmit={handleOpenFolderSubmit} 
            className="w-[450px] bg-[#111318] border border-white/5 rounded-xl shadow-2xl p-5"
          >
            <h3 className="text-sm font-semibold text-white mb-2">Open Workspace Folder</h3>
            <p className="text-[10px] text-gray-500 mb-4">
              Enter the absolute folder path on your computer. DevPilot will load its file tree and run commands inside it.
            </p>
            <input
              autoFocus
              type="text"
              value={folderPathInput}
              onChange={(e) => setFolderPathInput(e.target.value)}
              className="w-full px-3 py-2 bg-[#171922] border border-white/5 rounded-lg text-xs text-white focus:outline-none focus:border-violet-500 mb-4 font-mono"
              placeholder="e.g. E:/my-project"
            />
            <div className="flex justify-end gap-2 text-xs">
              <button
                type="button"
                onClick={() => setIsOpenFolderModalOpen(false)}
                className="px-4 py-2 bg-transparent text-gray-400 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-colors font-medium"
              >
                Open Folder
              </button>
            </div>
          </form>
        </div>
      )}

      {/* VS Code Interactive Status Bar (24px) */}
      <div className="h-[24px] bg-[#181818] border-t border-white/5 flex items-center justify-between px-3 text-[10px] text-gray-400 shrink-0 select-none z-20">
        <div className="flex items-center gap-4">
          {/* Active Branch toggle */}
          <button
            onClick={() => {
              setSidebarTab('git');
              setIsSidebarOpen(true);
            }}
            className="flex items-center gap-1.5 hover:text-white transition-colors"
            title="Open Source Control view"
          >
            <GitBranch className="w-3 h-3 text-violet-400" />
            <span className="font-mono">{statusBarBranch}</span>
          </button>

          {/* Active Workspace */}
          <span className="text-gray-500 font-mono hidden md:inline truncate max-w-sm">
            {workspacePath || 'No Folder Open'}
          </span>
        </div>

        <div className="flex items-center gap-4">
          {/* Selected profile */}
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="hover:text-white transition-colors"
            title="Click to open settings modal"
          >
            Profile: <span className="text-violet-400 font-semibold">{activeProfileName}</span>
          </button>

          {/* Debug running toggle state */}
          <button
            onClick={async () => {
              const method = statusBarDebug === 'Running' ? 'stop' : 'start';
              await fetch(`/api/debug/${method}`, { method: 'POST' });
              updateStatusBarInfo();
            }}
            className="flex items-center gap-1.5 hover:text-white transition-colors"
            title={statusBarDebug === 'Running' ? 'Click to STOP process execution' : 'Click to START project runner'}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${statusBarDebug === 'Running' ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'}`} />
            <span>Process: {statusBarDebug}</span>
          </button>
        </div>
      </div>

      {/* VS Code Command Palette Overlay */}
      {isCommandPaletteOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-sm pt-[80px]"
          onClick={() => setIsCommandPaletteOpen(false)}
        >
          <div 
            className="w-[500px] bg-[#111318]/90 border border-violet-500/20 rounded-xl shadow-2xl overflow-hidden backdrop-blur-xl animate-slide-down glow-purple"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Input search */}
            <div className="p-3 bg-[#0e1014]/95 border-b border-white/5 flex items-center gap-2">
              <Search className="w-4 h-4 text-violet-400 shrink-0" />
              <input
                autoFocus
                type="text"
                value={commandSearch}
                onChange={(e) => setCommandSearch(e.target.value)}
                placeholder="Search commands (e.g. Open Folder, Start Debug)..."
                className="w-full bg-transparent text-xs text-white focus:outline-none placeholder:text-gray-600 font-mono"
              />
              <span className="text-[9px] bg-white/5 text-gray-500 px-1.5 py-0.2 rounded font-mono shrink-0">
                ESC to close
              </span>
            </div>

            {/* List */}
            <div className="max-h-72 overflow-y-auto py-1">
              {[
                { label: 'File: Open Workspace Folder', action: () => { setIsCommandPaletteOpen(false); handleOpenWorkspaceFolder(); } },
                { label: 'AI: Configure Model Profile Settings', action: () => { setIsCommandPaletteOpen(false); setIsSettingsOpen(true); } },
                { label: 'AI: Clear Assistant Chat Logs', action: () => { setIsCommandPaletteOpen(false); setMessages([]); } },
                { label: 'Debug: Start Project Execution', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/debug/start', { method: 'POST' }); updateStatusBarInfo(); } },
                { label: 'Debug: Stop Project Execution', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/debug/stop', { method: 'POST' }); updateStatusBarInfo(); } },
                { label: 'Git: Pull latest updates', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/git/action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({action:'pull'}) }); } },
                { label: 'Git: Push local commits', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/git/action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({action:'push'}) }); } },
                { label: 'View: Open File Explorer Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('explorer'); setIsSidebarOpen(true); } },
                { label: 'View: Open Code Search Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('search'); setIsSidebarOpen(true); } },
                { label: 'View: Open Git Control Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('git'); setIsSidebarOpen(true); } },
                { label: 'View: Open Run/Debug Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('debug'); setIsSidebarOpen(true); } },
                { label: 'View: Open Extensions Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('extensions'); setIsSidebarOpen(true); } },
                { label: 'View: Open Testing Explorer', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('testing'); setIsSidebarOpen(true); } },
                { label: 'View: Open Dependencies manager', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('packages'); setIsSidebarOpen(true); } },
              ]
                .filter(cmd => cmd.label.toLowerCase().includes(commandSearch.toLowerCase()))
                .map((cmd, idx) => (
                  <button
                    key={idx}
                    onClick={cmd.action}
                    className="w-full text-left px-4 py-2 hover:bg-violet-600/10 hover:text-white transition-colors text-xs text-gray-305 font-mono"
                  >
                    {cmd.label}
                  </button>
                ))}
              {commandSearch && ![].length && (
                <div className="px-4 py-3 text-xs text-gray-600 italic">No command matches search.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Sleek React Toast Notification System Overlay */}
      <div className="fixed bottom-10 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none select-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`px-4 py-2.5 rounded-lg shadow-2xl text-xs font-semibold text-white flex items-center gap-2 border border-white/5 animate-slide-in-right ${
              t.type === 'success' ? 'bg-emerald-600/90 glow-emerald' : t.type === 'error' ? 'bg-red-650/90' : 'bg-violet-650/90 glow-purple'
            }`}
          >
            <span>{t.message}</span>
          </div>
        ))}
      </div>

    </div>
  );
}
