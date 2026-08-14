import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Terminal as TerminalIcon } from 'lucide-react';
import '@xterm/xterm/css/xterm.css';

interface TerminalAreaProps {
  workspacePath: string;
  activeTerminalCommand?: string | null;
  activeTerminalStatus?: 'running' | 'completed' | 'failed' | null;
  activeTerminalExitCode?: number | null;
  activeTerminalElapsed?: number | null;
}

interface CommandTrigger {
  id: number;
  cmd: string;
  timestamp: number;
}

interface TerminalPaneProps {
  id: number;
  workspacePath: string;
  isActive: boolean;
  onFocus: () => void;
  onClose: () => void;
  showClose: boolean;
  commandToRun: CommandTrigger | null;
  shell?: string;
  fontSize?: number;
  scrollback?: number;
  isAgent?: boolean;
}

function TerminalPane({
  id,
  workspacePath,
  isActive,
  onFocus,
  onClose,
  showClose,
  commandToRun,
  shell,
  fontSize = 13,
  scrollback = 5000,
  isAgent = false,
}: TerminalPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastDetectedUrlRef = useRef<string | null>(null);
  const pendingCommandRef = useRef<string | null>(null);
  const [shellName, setShellName] = useState('Terminal');

  useEffect(() => {
    if (isAgent) {
      setShellName('DevPilot Agent');
      return;
    }
    if (shell) {
      const name = shell === 'cmd' ? 'CMD' : shell.charAt(0).toUpperCase() + shell.slice(1);
      setShellName(`Terminal (${name})`);
    } else {
      fetch('/api/shell/name')
        .then(res => res.json())
        .then(data => {
          if (data && data.name) {
            setShellName(`Terminal (${data.name})`);
          }
        })
        .catch(() => {});
    }
  }, [shell, isAgent]);

  useEffect(() => {
    if (!terminalRef.current || !containerRef.current) return;

    const guard = { cancelled: false };

    const term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'underline',
      theme: {
        background: '#0d0f12',
        foreground: '#e2e8f0',
        cursor: '#a78bfa',
        black: '#1e222a',
        red: '#e06c75',
        green: '#98c379',
        yellow: '#d19a66',
        blue: '#61afef',
        magenta: '#c678dd',
        cyan: '#56b6c2',
        white: '#abb2bf',
      },
      fontFamily: "'Fira Code', monospace",
      fontSize,
      scrollback,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    let ws: WebSocket | null = null;
    let disposable: any = null;
    let reconnectAttempts = 0;
    let reconnectTimeout: any = null;

    const connectTerminal = () => {
      if (guard.cancelled) return;

      // Close previous socket if still lingering
      if (ws) {
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        try { ws.close(); } catch {}
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const sessionId = localStorage.getItem('devpilot_session_id') || '';
      const token = localStorage.getItem('session_token') || '';
      const params = new URLSearchParams();
      if (shell) params.set('shell', shell);
      if (workspacePath) params.set('workspace', workspacePath);
      if (sessionId) params.set('session_id', sessionId);
      if (token) params.set('token', token);
      const wsUrl = `${protocol}//${window.location.host}/ws/terminal?${params.toString()}`;
      const socket = new WebSocket(wsUrl);
      ws = socket;
      wsRef.current = socket;

      // Helper to send a resize control message
      const sendResize = () => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({
            type: 'resize',
            cols: term.cols,
            rows: term.rows,
          }));
        }
      };

      socket.onopen = () => {
        if (guard.cancelled) {
          try { socket.close(); } catch {}
          return;
        }
        reconnectAttempts = 0; // reset attempts on successful connection
        sendResize();

        if (pendingCommandRef.current) {
          socket.send(pendingCommandRef.current + '\r');
          pendingCommandRef.current = null;
        }
      };

      socket.onmessage = (event) => {
        // Intercept ping from server
        if (typeof event.data === 'string' && event.data.startsWith('{"type":')) {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'ping') {
              socket.send(JSON.stringify({ type: 'pong' }));
              return;
            }
          } catch {}
        }
        term.write(event.data);
        checkOutputForLocalhost(String(event.data || ''));
      };

      socket.onclose = (event) => {
        if (guard.cancelled) return;

        // Don't auto-reconnect if token is invalid/unauthorized
        if (event.code === 4401) {
          term.write('\r\n\x1b[31mTerminal session unauthorized. Please reload.\x1b[0m\r\n');
          return;
        }

        if (reconnectAttempts >= 5) {
          term.write('\r\n\x1b[31mTerminal disconnected. Refresh to reconnect.\x1b[0m\r\n');
          return;
        }

        const delay = Math.min(500 * 2 ** reconnectAttempts, 8000);
        reconnectAttempts++;
        term.write(`\r\n\x1b[90mReconnecting in ${delay}ms (attempt ${reconnectAttempts})...\x1b[0m\r\n`);
        
        reconnectTimeout = setTimeout(() => {
          if (!guard.cancelled) connectTerminal();
        }, delay);
      };

      socket.onerror = () => {
        term.write('\r\n\x1b[31mTerminal connection error.\x1b[0m\r\n');
      };

      if (disposable) disposable.dispose();
      disposable = term.onData((data) => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(data);
        }
      });
    };

    if (!isAgent) {
      connectTerminal();
    } else {
      term.write('\x1b[35m[DevPilot Agent Terminal Ready]\x1b[0m\r\n');
    }

    const checkOutputForLocalhost = (text: string) => {
      if (!text) return;
      const match = text.match(/https?:\/\/(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]):(\d+)/i);
      if (match) {
        const port = match[1];
        const detectedUrl = `http://localhost:${port}`;
        if (lastDetectedUrlRef.current !== detectedUrl) {
          lastDetectedUrlRef.current = detectedUrl;
          window.dispatchEvent(
            new CustomEvent('devpilot-localhost-detected', {
              detail: { url: detectedUrl, port }
            })
          );
        }
      }
    };

    // Send resize events when xterm's dimensions change (from fitAddon)
    const resizeDisposable = term.onResize(({ cols, rows }) => {
      if (!isAgent && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'resize', cols, rows }));
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch (e) {}
    });
    resizeObserver.observe(containerRef.current!);

    const timer = setTimeout(() => {
      try {
        fitAddon.fit();
      } catch (e) {}
    }, 100);

    const handleAgentStream = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail && isAgent) {
        term.write(customEvent.detail.replace(/\r?\n/g, '\r\n'));
        checkOutputForLocalhost(String(customEvent.detail || ''));
      }
    };
    window.addEventListener('devpilot_terminal_stream', handleAgentStream);

    return () => {
      guard.cancelled = true;
      clearTimeout(timer);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (disposable) disposable.dispose();
      resizeDisposable.dispose();
      window.removeEventListener('devpilot_terminal_stream', handleAgentStream);
      term.dispose();
      resizeObserver.disconnect();
      const activeWs = wsRef.current || ws;
      if (activeWs) {
        activeWs.onmessage = null;
        activeWs.onerror = null;
        activeWs.onclose = null;
        if (activeWs.readyState === WebSocket.OPEN) {
          activeWs.close();
        }
      }
    };
  }, [workspacePath, isAgent]);

  // Handle command triggers from parent history
  useEffect(() => {
    if (commandToRun && commandToRun.id === id) {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(commandToRun.cmd + '\r');
      } else {
        pendingCommandRef.current = commandToRun.cmd;
      }
    }
  }, [commandToRun, id]);

  return (
    <div
      ref={containerRef}
      onMouseDown={onFocus}
      className={`flex-1 flex flex-col min-w-[200px] h-full relative transition-all duration-150 ${
        isActive ? 'bg-[#0d0f12]' : 'bg-[#090b0d] opacity-90'
      }`}
    >
      {/* Pane Toolbar Header */}
      <div className={`flex items-center justify-between px-3 py-1 bg-[#14171f] border-b border-white/5 text-[10px] select-none shrink-0 font-sans ${
        isActive ? 'text-[#4C8DFF] font-semibold' : 'text-gray-550 font-medium'
      }`}>
        <div className="flex items-center gap-1.5 min-w-0">
          <TerminalIcon className={`w-3 h-3 ${isActive ? 'text-[#4C8DFF]' : 'text-gray-555'}`} />
          <span className="truncate">{shellName}</span>
          {isActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#4C8DFF] animate-pulse ml-1" />
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {showClose && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClose();
              }}
              className="text-gray-550 hover:text-red-400 p-0.5 rounded hover:bg-white/5 transition-all cursor-pointer"
              title="Close Terminal Pane"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 p-2 overflow-hidden bg-[#0d0f12]">
        <div ref={terminalRef} className="h-full w-full" />
      </div>
    </div>
  );
}

const SHELL_OPTIONS = [
  { value: '', label: 'Default (OS)' },
  { value: 'powershell', label: 'PowerShell' },
  { value: 'cmd', label: 'CMD' },
  { value: 'bash', label: 'Git Bash' },
  { value: 'wsl', label: 'WSL (Linux)' },
  { value: 'sh', label: 'Sh' },
];

export default function TerminalArea({ 
  workspacePath,
  activeTerminalCommand,
  activeTerminalStatus,
  activeTerminalExitCode,
  activeTerminalElapsed
}: TerminalAreaProps) {
  const [history, setHistory] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('devpilot_terminal_history');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const recordCommandHistory = (cmd: string) => {
    if (!cmd || !cmd.trim()) return;
    const trimmed = cmd.trim();
    setHistory((prev) => {
      const filtered = prev.filter((item) => item !== trimmed);
      const updated = [trimmed, ...filtered].slice(0, 50);
      try {
        localStorage.setItem('devpilot_terminal_history', JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };
  const [showHistory, setShowHistory] = useState(false);
  const [filterText, setFilterText] = useState('');
  const [viewMode, setViewMode] = useState<'split' | 'tabs'>('split');

  // Terminal preferences loaded from backend settings
  const [fontSize, setFontSize] = useState(13);
  const [scrollback, setScrollback] = useState(5000);

  // Split terminals management — default shell starts empty until settings load
  const [splitTerminals, setSplitTerminals] = useState<{ id: number; shell: string; name?: string; isAgent?: boolean }[]>([
    { id: 0, shell: '', name: 'Terminal 1' }
  ]);
  const [selectedShell, setSelectedShell] = useState<string>('');
  const [nextId, setNextId] = useState(1);
  const [activePaneId, setActivePaneId] = useState<number>(0);
  const [commandToRun, setCommandToRun] = useState<CommandTrigger | null>(null);

  // Load saved terminal preferences from the backend on mount.
  useEffect(() => {
    fetch('/api/config/settings', {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('session_token') || ''}` }
    })
      .then(r => r.json())
      .then(data => {
        const shell = data.default_shell || '';
        setSelectedShell(shell);
        setSplitTerminals([{ id: 0, shell, name: 'Terminal 1' }]);
        if (data.terminal_font_size) setFontSize(data.terminal_font_size);
        if (data.terminal_scrollback) setScrollback(data.terminal_scrollback);
      })
      .catch(() => {});
  }, []);

  const handleShellChange = (newShell: string) => {
    setSelectedShell(newShell);
    fetch('/api/config/settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('session_token') || ''}`
      },
      body: JSON.stringify({
        exclude_list: [],
        auto_backup_enabled: true,
        default_shell: newShell,
        terminal_font_size: fontSize,
        terminal_scrollback: scrollback,
      })
    }).catch(() => {});
  };

  const handleAddTerminal = () => {
    if (splitTerminals.length >= 6) return;
    const newId = nextId;
    const count = splitTerminals.length + 1;
    setSplitTerminals(prev => [...prev, { id: newId, shell: selectedShell, name: `Terminal ${count}` }]);
    setNextId(prev => prev + 1);
    setActivePaneId(newId);
  };

  const handleSplit = () => {
    if (splitTerminals.length >= 4) return;
    setViewMode('split');
    handleAddTerminal();
  };

  const removeSplit = (id: number) => {
    setSplitTerminals(prev => {
      const remaining = prev.filter(t => t.id !== id);
      if (activePaneId === id && remaining.length > 0) {
        setActivePaneId(remaining[remaining.length - 1].id);
      }
      return remaining;
    });
  };

  const handleRunCommand = (cmd: string) => {
    setCommandToRun({
      id: activePaneId,
      cmd,
      timestamp: Date.now()
    });
    recordCommandHistory(cmd);
  };

  useEffect(() => {
    const handleRunCommandEvent = (e: Event) => {
      const detail = (e as CustomEvent<{ command: string }>).detail;
      if (!detail?.command) return;

      const rawCmd = detail.command.trim();
      const commands = rawCmd.split('\n').map(c => c.trim()).filter(Boolean);

      if (commands.length === 1) {
        handleRunCommand(commands[0]);
      } else if (commands.length > 1) {
        handleRunCommand(commands[0]);

        const newPanes: { id: number; shell: string; name?: string }[] = [];
        const commandsToTrigger: { id: number; cmd: string }[] = [];

        let tempNextId = nextId;
        for (let idx = 1; idx < Math.min(commands.length, 3); idx++) {
          const cmd = commands[idx];
          const newId = tempNextId;
          newPanes.push({ id: newId, shell: selectedShell, name: `Terminal ${splitTerminals.length + idx + 1}` });
          commandsToTrigger.push({ id: newId, cmd });
          tempNextId++;
        }

        if (newPanes.length > 0) {
          setSplitTerminals(prev => [...prev, ...newPanes]);
          setNextId(tempNextId);

          commandsToTrigger.forEach((item) => {
            setTimeout(() => {
              setCommandToRun({
                id: item.id,
                cmd: item.cmd,
                timestamp: Date.now()
              });
              recordCommandHistory(item.cmd);
            }, 450);
          });
        }
      }
    };
    window.addEventListener('devpilot-run-terminal-command', handleRunCommandEvent);
    return () => window.removeEventListener('devpilot-run-terminal-command', handleRunCommandEvent);
  }, [activePaneId, nextId, selectedShell, splitTerminals.length]);

  useEffect(() => {
    if (activeTerminalStatus === 'running') {
      setSplitTerminals(prev => {
        const hasAgentTerm = prev.some(t => t.isAgent);
        if (!hasAgentTerm) {
          const newId = nextId;
          setTimeout(() => {
            setActivePaneId(newId);
          }, 0);
          setNextId(prevId => prevId + 1);
          return [...prev, { id: newId, shell: selectedShell, name: 'DevPilot Agent', isAgent: true }];
        } else {
          const agentTerm = prev.find(t => t.isAgent);
          if (agentTerm) {
            setTimeout(() => {
              setActivePaneId(agentTerm.id);
            }, 0);
          }
          return prev;
        }
      });
    }
  }, [activeTerminalStatus, selectedShell, nextId]);

  const visiblePanes = viewMode === 'split' 
    ? splitTerminals 
    : splitTerminals.filter(p => p.id === activePaneId);

  return (
    <div className="h-full w-full flex flex-col bg-[#0d0f12] text-gray-300 overflow-hidden font-sans">
      {/* Title bar / Controls */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#111318] border-b border-white/5 text-xs text-gray-400 font-medium select-none shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <TerminalIcon className="w-3.5 h-3.5 text-[#4C8DFF]" />
          
          {/* View mode & Terminal Tabs */}
          <div className="flex items-center gap-1 bg-[#181a24] p-0.5 rounded-lg border border-white/5">
            {splitTerminals.map(t => (
              <button
                key={t.id}
                onClick={() => setActivePaneId(t.id)}
                className={`px-2 py-0.5 rounded text-[10px] font-mono flex items-center gap-1 cursor-pointer transition-colors ${
                  activePaneId === t.id ? 'bg-[#3B7AE8] text-white font-semibold' : 'text-gray-400 hover:text-white'
                }`}
              >
                <span>{t.name || `Term ${t.id + 1}`}</span>
              </button>
            ))}
            <button
              onClick={handleAddTerminal}
              className="px-1.5 py-0.5 text-[10px] text-[#4C8DFF] hover:text-[#4C8DFF] font-bold"
              title="Add Terminal"
            >
              +
            </button>
          </div>

          {activeTerminalStatus === 'running' && (
            <span className="ml-2 px-1.5 py-0.5 rounded bg-[#4C8DFF]/20 text-[#4C8DFF] font-mono text-[9px] animate-pulse truncate">
              Running: {activeTerminalCommand} ({activeTerminalElapsed}s)
            </span>
          )}
          {activeTerminalStatus === 'completed' && activeTerminalExitCode !== undefined && (
            <span className={`ml-2 px-1.5 py-0.5 rounded font-mono text-[9px] truncate ${
              activeTerminalExitCode === 0 ? 'bg-emerald-500/25 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/25 text-red-400 border border-red-500/20'
            }`}>
              Exit {activeTerminalExitCode} ({activeTerminalElapsed}s)
            </span>
          )}

        </div>

        <div className="flex items-center gap-2 relative">
          <input
            type="text"
            placeholder="Filter/run history..."
            value={filterText}
            onChange={(e) => {
              setFilterText(e.target.value);
              setShowHistory(true);
            }}
            onFocus={() => setShowHistory(true)}
            className="bg-black/40 text-[10px] border border-white/5 hover:border-[#4C8DFF]/30 focus:border-[#4C8DFF]/50 rounded px-2 py-0.5 text-white focus:outline-none transition-all w-32"
          />
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 hover:text-white transition-all text-[10px]"
          >
            History ▾
          </button>

          {showHistory && (
            <div className="absolute right-0 top-6 w-52 bg-[#161822] border border-white/10 rounded-lg shadow-xl z-50 p-1 space-y-1">
              <div className="text-[9px] text-gray-500 px-2 py-1 font-bold border-b border-white/5 uppercase">
                Command History
              </div>
              <div className="max-h-32 overflow-y-auto pr-1">
                {history
                  .filter(cmd => cmd.toLowerCase().includes(filterText.toLowerCase()))
                  .map((cmd, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        handleRunCommand(cmd);
                        setShowHistory(false);
                      }}
                      className="w-full text-left px-2 py-1 rounded hover:bg-[#3B7AE8]/20 hover:text-white text-[10px] truncate font-mono block"
                    >
                      {cmd}
                    </button>
                  ))}
              </div>
            </div>
          )}

          {/* Shell Selector Dropdown */}
          <select
            value={selectedShell}
            onChange={(e) => handleShellChange(e.target.value)}
            className="bg-black/40 text-[10px] border border-white/5 hover:border-[#4C8DFF]/30 focus:border-[#4C8DFF]/50 rounded px-2 py-0.5 text-white focus:outline-none transition-all cursor-pointer font-mono"
            title="Default shell profile"
          >
            {SHELL_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} className="bg-[#161822] text-white font-mono">
                {opt.label}
              </option>
            ))}
          </select>

          {/* View Switcher Button */}
          <button
            onClick={() => setViewMode(viewMode === 'split' ? 'tabs' : 'split')}
            className="px-2 py-0.5 bg-white/5 hover:bg-white/10 text-gray-300 rounded text-[10px] font-semibold cursor-pointer"
            title="Toggle Split View / Single Tab View"
          >
            {viewMode === 'split' ? 'Tabs' : 'Split'}
          </button>

          {/* Split Terminal button */}
          <button
            onClick={handleSplit}
            disabled={splitTerminals.length >= 4}
            className={`px-2 py-0.5 rounded text-[10px] flex items-center gap-1 font-semibold transition-all cursor-pointer ${
              splitTerminals.length >= 4 
                ? 'bg-white/5 text-gray-600 cursor-not-allowed'
                : 'bg-[#3B7AE8]/80 hover:bg-[#3B7AE8] text-white'
            }`}
            title="Split Terminal side-by-side"
          >
            <span>Split</span>
          </button>
        </div>
      </div>
      
      {/* Shell Area: Displays active split or tab panels */}
      <div className="flex-1 flex flex-row bg-[#0d0f12] overflow-hidden divide-x divide-white/10">
        {visiblePanes.map((pane) => (
          <TerminalPane
            key={pane.id}
            id={pane.id}
            workspacePath={workspacePath}
            isActive={activePaneId === pane.id}
            onFocus={() => setActivePaneId(pane.id)}
            onClose={() => removeSplit(pane.id)}
            showClose={splitTerminals.length > 1}
            commandToRun={commandToRun}
            shell={pane.shell}
            fontSize={fontSize}
            scrollback={scrollback}
            isAgent={pane.isAgent}
          />
        ))}
      </div>
    </div>
  );
}