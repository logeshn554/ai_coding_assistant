import { useState, useEffect } from 'react';
import { Play, Square, RotateCcw, Bug, Terminal, List, Cpu } from 'lucide-react';

export default function RunDebugSidebar() {
  const [isRunning, setIsRunning] = useState(false);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [bugReport, setBugReport] = useState<string[]>([]);
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

  const fetchBugReport = async () => {
    try {
      const res = await fetch('/api/scan-bugs', { method: 'POST' });
      const data = await res.json();
      const reportArray = typeof data.report === 'string' ? [data.report] : (data.report || []);
      setBugReport(reportArray);
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

  const handleScanBugs = async () => {
    await fetchBugReport();
  };

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#cccccc] font-sans select-none">
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-[#2d2d2d] bg-[#181818] flex items-center justify-between shrink-0">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Bug className="w-3.5 h-3.5 text-violet-400" />
          Run & Debug
        </span>
      </div>

      {/* Control Buttons */}
      <div className="p-2 border-b border-[#2d2d2d] bg-[#131313] flex gap-1.5 shrink-0">
        {!isRunning ? (
          <button
            onClick={handleStart}
            className="flex-1 py-1 bg-emerald-600 hover:bg-emerald-500 border border-emerald-500/20 text-white rounded-none text-[10px] font-semibold flex items-center justify-center gap-1 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" /> Run Project
          </button>
        ) : (
          <>
            <button
              onClick={handleStop}
              className="flex-1 py-1 bg-red-650 hover:bg-red-600 border border-red-500/20 text-white rounded-none text-[10px] font-semibold flex items-center justify-center gap-1 cursor-pointer"
            >
              <Square className="w-3.5 h-3.5" /> Stop
            </button>
            <button
              onClick={handleRestart}
              className="py-1 px-2.5 bg-white/5 hover:bg-white/10 border border-[#2d2d2d] rounded-none text-[10px] font-semibold flex items-center justify-center text-gray-300 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </>
        )}
        <button
          onClick={handleScanBugs}
          className="flex-1 py-1 bg-[#8b5cf6] hover:bg-[#7c4dff] border border-violet-500/20 text-white rounded-none text-[10px] font-semibold flex items-center justify-center gap-1 cursor-pointer"
        >
          <Bug className="w-3.5 h-3.5" /> Scan Bugs
        </button>
      </div>

      {/* Panels container */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Variables Panel */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-450 uppercase tracking-wider flex items-center gap-1">
            <Cpu className="w-3 h-3 text-violet-400" /> Variables
          </div>
          <div className="p-2 bg-[#131313] border border-[#2d2d2d] rounded-none font-mono text-[9px] text-gray-400 space-y-1">
            <div><span className="text-violet-400">workspace_state:</span> Object</div>
            <div><span className="text-violet-400">is_running:</span> {isRunning ? 'true' : 'false'}</div>
            <div><span className="text-violet-400">config_manager:</span> Loaded</div>
          </div>
        </div>

        {/* Breakpoints */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-450 uppercase tracking-wider flex items-center gap-1">
            <List className="w-3 h-3 text-[#8b5cf6]" /> Breakpoints
          </div>
          <div className="space-y-1">
            {breakpoints.map((bp) => (
              <div key={bp} className="flex items-center gap-1.5 p-1 bg-[#1e1e1e] border border-[#2d2d2d] rounded-none text-[9px] font-mono">
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
          <div className="p-2 bg-[#131313] border border-[#2d2d2d] rounded-none font-mono text-[9px] text-gray-550 h-32 overflow-y-auto space-y-1 pr-1 select-text scrollbar-thin">
            {consoleLogs.length === 0 ? (
              <div className="text-gray-650 italic">No output received yet.</div>
            ) : (
              consoleLogs.map((log, index) => (
                <div key={index} className="leading-relaxed whitespace-pre-wrap break-all text-gray-400">
                  {log}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Bug Report Panel */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-gray-450 uppercase tracking-wider flex items-center gap-1">
            <Bug className="w-3 h-3 text-violet-400" /> Bug Report
          </div>
          <div className="p-2 bg-[#131313] border border-[#2d2d2d] rounded-none font-mono text-[9px] text-gray-550 h-32 overflow-y-auto space-y-1 pr-1 select-text scrollbar-thin">
            {bugReport.length === 0 ? (
              <div className="text-gray-650 italic">No bugs detected. Click Scan Bugs to run checkers.</div>
            ) : (
              bugReport.map((item, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all text-gray-400">
                  {item}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}