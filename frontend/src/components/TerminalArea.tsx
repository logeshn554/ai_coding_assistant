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

export default function TerminalArea({ 
  workspacePath,
  activeTerminalCommand,
  activeTerminalStatus,
  activeTerminalExitCode,
  activeTerminalElapsed
}: TerminalAreaProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [history, setHistory] = useState<string[]>([
    'npm run test',
    'git status',
    'git diff',
    'npm run build',
    'ls -la'
  ]);
  const [showHistory, setShowHistory] = useState(false);
  const [filterText, setFilterText] = useState('');

  useEffect(() => {
    if (!terminalRef.current || !containerRef.current) return;

    // Initialize xterm.js Terminal
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

    // Fit addon setup
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);

    // Open terminal inside div
    term.open(terminalRef.current);
    fitAddon.fit();

    // Setup Websocket Connection
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

    // Handle resizing
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

  const handleRunCommand = (cmd: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Send string followed by return character to trigger execution
      wsRef.current.send(cmd + '\r');
      if (!history.includes(cmd)) {
        setHistory(prev => [cmd, ...prev]);
      }
    }
  };

  return (
    <div ref={containerRef} className="h-full flex flex-col bg-[#0d0f12] text-gray-300 overflow-hidden font-sans">
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#111318] border-b border-white/5 text-xs text-gray-400 font-medium select-none shrink-0">
        <div className="flex items-center gap-1.5 min-w-0">
          <TerminalIcon className="w-3.5 h-3.5 text-violet-400" />
          <span>Terminal Session</span>
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
        </div>
      </div>
      
      {/* Shell Area */}
      <div className="flex-1 p-2 overflow-hidden bg-[#0d0f12]">
        <div ref={terminalRef} className="h-full w-full" />
      </div>
    </div>
  );
}
