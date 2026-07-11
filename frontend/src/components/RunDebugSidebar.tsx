import { useState, useEffect } from 'react';
import { Play, Square, RotateCcw, Bug, Terminal, List, Cpu } from 'lucide-react';

export default function RunDebugSidebar() {
  const [isRunning, setIsRunning] = useState(false);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const breakpoints = [
    'backend/app/main.py:L158',
    'backend/app/agent.py:L114'
  ];

  const fetchStatusAndLogs = async () => {
    try {
      // 1. Status
      const statusRes = await fetch('/api/debug/status');
      const statusData = await statusRes.json();
      setIsRunning(statusData.running);

      // 2. Logs
      const logsRes = await fetch('/api/debug/logs');
      const logsData = await logsRes.json();
      setConsoleLogs(logsData.logs || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchStatusAndLogs();
    const interval = setInterval(fetchStatusAndLogs, 1500);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      await fetch('/api/debug/start', { method: 'POST' });
      fetchStatusAndLogs();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStop = async () => {
    try {
      await fetch('/api/debug/stop', { method: 'POST' });
      fetchStatusAndLogs();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRestart = async () => {
    await handleStop();
    setTimeout(handleStart, 600);
  };

  return (
    <div className="h-full flex flex-col bg-[#0e1014] text-gray-300 font-sans select-none">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 bg-[#111318] flex items-center justify-between shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Bug className="w-3.5 h-3.5 text-violet-400" />
          Run & Debug
        </span>
      </div>

      {/* Control Buttons */}
      <div className="p-3 border-b border-white/5 bg-[#0e1014] flex gap-2 shrink-0">
        {!isRunning ? (
          <button
            onClick={handleStart}
            className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 border border-emerald-500/20 text-white rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition-all"
          >
            <Play className="w-3.5 h-3.5" /> Run Project
          </button>
        ) : (
          <>
            <button
              onClick={handleStop}
              className="flex-1 py-1.5 bg-red-650 hover:bg-red-600 border border-red-500/20 text-white rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition-all"
            >
              <Square className="w-3.5 h-3.5" /> Stop
            </button>
            <button
              onClick={handleRestart}
              className="py-1.5 px-3 bg-white/5 hover:bg-white/10 border border-white/5 rounded text-[10px] font-semibold flex items-center justify-center text-gray-300 transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </>
        )}
      </div>

      {/* Panels container */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Variables Panel */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-450 uppercase tracking-wider flex items-center gap-1">
            <Cpu className="w-3 h-3 text-violet-400" /> Variables
          </div>
          <div className="p-2 bg-black/15 border border-white/5 rounded font-mono text-[9px] text-gray-400 space-y-1">
            <div><span className="text-violet-400">workspace_state:</span> Object</div>
            <div><span className="text-violet-400">is_running:</span> {isRunning ? 'true' : 'false'}</div>
            <div><span className="text-violet-400">config_manager:</span> Loaded</div>
          </div>
        </div>

        {/* Breakpoints */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-450 uppercase tracking-wider flex items-center gap-1">
            <List className="w-3 h-3 text-violet-400" /> Breakpoints
          </div>
          <div className="space-y-1">
            {breakpoints.map((bp) => (
              <div key={bp} className="flex items-center gap-1.5 p-1 bg-black/15 border border-white/5 rounded text-[9px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                <span className="text-gray-350 truncate">{bp}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Debug Console Output */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-450 uppercase tracking-wider flex items-center gap-1">
            <Terminal className="w-3 h-3 text-violet-400" /> Console Logs
          </div>
          <div className="p-2 bg-black/30 border border-white/5 rounded font-mono text-[9px] text-gray-500 h-32 overflow-y-auto space-y-1 pr-1 select-text">
            {consoleLogs.length === 0 ? (
              <div className="text-gray-600 italic">No output received yet.</div>
            ) : (
              consoleLogs.map((log, index) => (
                <div key={index} className="leading-relaxed whitespace-pre-wrap break-all">
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
