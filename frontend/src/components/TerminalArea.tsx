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
}

function TerminalPane({
  id,
  workspacePath,
  isActive,
  onFocus,
  onClose,
  showClose,
  commandToRun
}: TerminalPaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [shellName, setShellName] = useState('Terminal');

  useEffect(() => {
    fetch('/api/shell/name')
      .then(res => res.json())
      .then(data => {
        if (data && data.name) {
          setShellName(`Terminal (${data.name})`);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!terminalRef.current || !containerRef.current) return;

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
      fontSize: 12,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      term.write('\r\nConnected to DevPilot Terminal Shell...\r\n');
    };

    ws.onmessage = (event) => {
      term.write(event.data);
    };

    ws.onclose = () => {
      term.write('\r\nTerminal WebSocket connection closed.\r\n');
    };

    ws.onerror = () => {
      term.write('\r\nTerminal WebSocket connection error.\r\n');
    };

    const disposable = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
      } catch (e) {}
    });
    resizeObserver.observe(containerRef.current);

    const timer = setTimeout(() => {
      try {
        fitAddon.fit();
      } catch (e) {}
    }, 100);

    return () => {
      clearTimeout(timer);
      disposable.dispose();
      term.dispose();
      resizeObserver.disconnect();
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [workspacePath]);

  // Handle command triggers from parent history
  useEffect(() => {
    if (commandToRun && commandToRun.id === id && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(commandToRun.cmd + '\r');
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
        isActive ? 'text-violet-400 font-semibold' : 'text-gray-550 font-medium'
      }`}>
        <div className="flex items-center gap-1.5 min-w-0">
          <TerminalIcon className={`w-3 h-3 ${isActive ? 'text-violet-400' : 'text-gray-555'}`} />
          <span className="truncate">{shellName}</span>
          {isActive && (
            <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse ml-1" />
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

export default function TerminalArea({ 
  workspacePath,
  activeTerminalCommand,
  activeTerminalStatus,
  activeTerminalExitCode,
  activeTerminalElapsed
}: TerminalAreaProps) {
  const [history, setHistory] = useState<string[]>([
    'npm run test',
    'git status',
    'git diff',
    'npm run build',
    'ls -la'
  ]);
  const [showHistory, setShowHistory] = useState(false);
  const [filterText, setFilterText] = useState('');
  
  // Split terminals management
  const [splitTerminals, setSplitTerminals] = useState<number[]>([0]);
  const [nextId, setNextId] = useState(1);
  const [activePaneId, setActivePaneId] = useState<number>(0);
  const [commandToRun, setCommandToRun] = useState<CommandTrigger | null>(null);

  const handleSplit = () => {
    if (splitTerminals.length >= 3) {
      return; // max 3 columns for space constraints
    }
    const newId = nextId;
    setSplitTerminals(prev => [...prev, newId]);
    setNextId(prev => prev + 1);
    setActivePaneId(newId);
  };

  const removeSplit = (id: number) => {
    setSplitTerminals(prev => {
      const remaining = prev.filter(t => t !== id);
      // fallback activePaneId if the closed one was active
      if (activePaneId === id && remaining.length > 0) {
        setActivePaneId(remaining[remaining.length - 1]);
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
    if (!history.includes(cmd)) {
      setHistory(prev => [cmd, ...prev]);
    }
  };

  return (
    <div className="h-full w-full flex flex-col bg-[#0d0f12] text-gray-300 overflow-hidden font-sans">
      {/* Title bar / Controls */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#111318] border-b border-white/5 text-xs text-gray-400 font-medium select-none shrink-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <TerminalIcon className="w-3.5 h-3.5 text-violet-400" />
          <span className="font-semibold">Terminal</span>
          {activeTerminalStatus === 'running' && (
            <span className="ml-2 px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-400 font-mono text-[9px] animate-pulse truncate">
              Running: {activeTerminalCommand} ({activeTerminalElapsed}s)
            </span>
          )}
          {activeTerminalStatus === 'completed' && (
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
            className="bg-black/40 text-[10px] border border-white/5 hover:border-violet-500/30 focus:border-violet-500/50 rounded px-2 py-0.5 text-white focus:outline-none transition-all w-32"
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
                      className="w-full text-left px-2 py-1 rounded hover:bg-violet-600/20 hover:text-white text-[10px] truncate font-mono block"
                    >
                      {cmd}
                    </button>
                  ))}
                {history.filter(cmd => cmd.toLowerCase().includes(filterText.toLowerCase())).length === 0 && (
                  <div className="text-[9px] text-gray-650 px-2 py-2 text-center">
                    No matching commands
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Split Terminal button */}
          <button
            onClick={handleSplit}
            disabled={splitTerminals.length >= 3}
            className={`px-2 py-0.5 rounded text-[10px] flex items-center gap-1 font-semibold transition-all cursor-pointer ${
              splitTerminals.length >= 3 
                ? 'bg-white/5 text-gray-600 cursor-not-allowed'
                : 'bg-violet-600/80 hover:bg-violet-600 text-white'
            }`}
            title="Split Terminal side-by-side"
          >
            <span>Split</span>
            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
          </button>
        </div>
      </div>
      
      {/* Shell Area: Displays active split panels side-by-side */}
      <div className="flex-1 flex flex-row bg-[#0d0f12] overflow-hidden divide-x divide-white/10">
        {splitTerminals.map((id) => (
          <TerminalPane
            key={id}
            id={id}
            workspacePath={workspacePath}
            isActive={activePaneId === id}
            onFocus={() => setActivePaneId(id)}
            onClose={() => removeSplit(id)}
            showClose={splitTerminals.length > 1}
            commandToRun={commandToRun}
          />
        ))}
      </div>
    </div>
  );
}