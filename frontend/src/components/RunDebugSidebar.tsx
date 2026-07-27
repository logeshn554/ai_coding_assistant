import React, { useState, useEffect } from 'react';
import {
  Play,
  Square,
  RotateCcw,
  Bug,
  Terminal,
  List,
  Cpu,
  Plus,
  Layers,
  Eye
} from 'lucide-react';

interface Breakpoint {
  id: string;
  file: string;
  line: number;
  enabled: boolean;
}

interface StackFrame {
  id: number;
  name: string;
  file: string;
  line: number;
}

export default function RunDebugSidebar() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeFrame, setActiveFrame] = useState('Idle');
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [bugReport, setBugReport] = useState<string[]>([]);
  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [callstack, setCallstack] = useState<StackFrame[]>([]);

  
  // New breakpoint inputs
  const [newBpFile, setNewBpFile] = useState('');
  const [newBpLine, setNewBpLine] = useState('');
  const [showAddBp, setShowAddBp] = useState(false);

  // Watch expressions & REPL
  const [watchExprs, setWatchExprs] = useState<{ id: string; expr: string; val: string }[]>([
    { id: '1', expr: 'workspace_state.root', val: 'Active' },
    { id: '2', expr: 'global_process_manager', val: 'Loaded' }
  ]);
  const [newWatchInput, setNewWatchInput] = useState('');
  const [replInput, setReplInput] = useState('');
  const [replHistory, setReplHistory] = useState<{ query: string; result?: string; error?: string }[]>([]);

  const fetchDebugInfo = async () => {
    try {
      // 1. Status
      const statusRes = await fetch('/api/debug/status');
      const statusData = await statusRes.json();
      setIsRunning(statusData.running);
      if (statusData.active_frame) setActiveFrame(statusData.active_frame);

      // 2. Logs
      const logsRes = await fetch('/api/debug/logs');
      const logsData = await logsRes.json();
      setConsoleLogs(logsData.logs || []);

      // 3. Breakpoints
      const bpRes = await fetch('/api/debug/breakpoints');
      const bpData = await bpRes.json();
      setBreakpoints(bpData.breakpoints || []);

      // 4. Callstack
      const csRes = await fetch('/api/debug/callstack');
      const csData = await csRes.json();
      setCallstack(csData.stack || []);
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
    fetchDebugInfo();
    const interval = setInterval(fetchDebugInfo, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      await fetch('/api/debug/start', { method: 'POST' });
      fetchDebugInfo();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStop = async () => {
    try {
      await fetch('/api/debug/stop', { method: 'POST' });
      fetchDebugInfo();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRestart = async () => {
    await handleStop();
    setTimeout(handleStart, 600);
  };

  const handleAddBreakpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBpFile.trim() || !newBpLine.trim()) return;
    try {
      await fetch('/api/debug/breakpoints', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file: newBpFile.trim(), line: parseInt(newBpLine.trim()) || 1 })
      });
      setNewBpFile('');
      setNewBpLine('');
      setShowAddBp(false);
      fetchDebugInfo();
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleBreakpoint = async (id: string) => {
    try {
      await fetch('/api/debug/breakpoints/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ breakpoint_id: id })
      });
      fetchDebugInfo();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddWatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWatchInput.trim()) return;
    const expr = newWatchInput.trim();
    setNewWatchInput('');
    try {
      const res = await fetch('/api/debug/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression: expr })
      });
      const data = await res.json();
      setWatchExprs(prev => [...prev, { id: String(Date.now()), expr, val: data.result || data.error || 'None' }]);
    } catch {
      setWatchExprs(prev => [...prev, { id: String(Date.now()), expr, val: 'Error' }]);
    }
  };

  const handleRunRepl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replInput.trim()) return;
    const query = replInput.trim();
    setReplInput('');
    try {
      const res = await fetch('/api/debug/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression: query })
      });
      const data = await res.json();
      setReplHistory(prev => [...prev, { query, result: data.result, error: data.error }]);
    } catch (err: any) {
      setReplHistory(prev => [...prev, { query, error: String(err) }]);
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0f1017] text-[#c8ccd8] font-sans select-none border-r border-zinc-800">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-800 bg-[#13141f] flex items-center justify-between shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5 font-sans">
          <Bug className="w-4 h-4 text-violet-400" />
          Run & Debug
        </span>
        <span className="text-[10px] font-mono text-zinc-400 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800">
          {isRunning ? 'RUNNING' : 'STOPPED'}
        </span>
      </div>

      {/* Control Action Toolbar */}
      <div className="p-2 border-b border-zinc-800 bg-[#11121a] flex gap-1.5 shrink-0">
        {!isRunning ? (
          <button
            onClick={handleStart}
            className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-colors shadow-sm"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Run Project
          </button>
        ) : (
          <>
            <button
              onClick={handleStop}
              className="flex-1 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-colors shadow-sm"
            >
              <Square className="w-3.5 h-3.5 fill-current" /> Stop
            </button>
            <button
              onClick={handleRestart}
              className="py-1.5 px-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 rounded-lg text-[11px] font-semibold flex items-center justify-center cursor-pointer transition-colors"
              title="Restart Session"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </>
        )}
        <button
          onClick={fetchBugReport}
          className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1 cursor-pointer transition-colors shadow-sm"
          title="Scan workspace for bugs"
        >
          <Bug className="w-3.5 h-3.5" /> Scan
        </button>
      </div>

      {/* Main Panels Feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 font-sans scrollbar-none">
        
        {/* 1. Variables & Scope */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-violet-400" /> Variables & Scope
          </div>
          <div className="p-2.5 bg-zinc-950 border border-zinc-800/80 rounded-xl font-mono text-[10.5px] text-zinc-300 space-y-1 shadow-inner">
            <div className="flex justify-between items-center"><span className="text-violet-400 font-semibold">active_frame:</span> <span className="text-zinc-300">{activeFrame}</span></div>
            <div className="flex justify-between items-center"><span className="text-violet-400 font-semibold">is_running:</span> <span className={isRunning ? 'text-emerald-400 font-bold' : 'text-zinc-500'}>{isRunning ? 'true' : 'false'}</span></div>
            <div className="flex justify-between items-center"><span className="text-violet-400 font-semibold">breakpoints:</span> <span className="text-zinc-300">{breakpoints.length} active</span></div>
          </div>
        </div>

        {/* 2. Watch Expressions */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-blue-400" /> Watch
            </div>
          </div>
          <form onSubmit={handleAddWatch} className="flex gap-1">
            <input
              type="text"
              value={newWatchInput}
              onChange={e => setNewWatchInput(e.target.value)}
              placeholder="Add watch expression (e.g. state.root)"
              className="flex-1 px-2 py-1 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-violet-500"
            />
            <button type="submit" className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded-lg text-xs font-bold cursor-pointer">+</button>
          </form>
          <div className="space-y-1">
            {watchExprs.map(w => (
              <div key={w.id} className="flex items-center justify-between p-2 bg-zinc-950 border border-zinc-800/80 rounded-xl text-[10.5px] font-mono">
                <span className="text-violet-300 truncate max-w-[140px]">{w.expr}</span>
                <span className="text-zinc-400 truncate max-w-[100px]">{w.val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 3. Call Stack */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-amber-400" /> Call Stack
          </div>
          <div className="space-y-1">
            {callstack.length === 0 ? (
              <div className="p-2 bg-zinc-950 border border-zinc-800/80 rounded-xl text-[10.5px] text-zinc-500 italic">No stack frame active.</div>
            ) : (
              callstack.map(frame => (
                <div key={frame.id} className="flex items-center justify-between p-2 bg-zinc-950 border border-zinc-800/80 rounded-xl text-[10.5px] font-mono">
                  <span className="font-bold text-zinc-200">{frame.name}()</span>
                  <span className="text-zinc-400 text-[9.5px] truncate max-w-[150px]">{frame.file.split('/').pop()}:L{frame.line}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 4. Breakpoints Management */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <List className="w-3.5 h-3.5 text-violet-400" /> Breakpoints
            </div>
            <button
              onClick={() => setShowAddBp(!showAddBp)}
              className="text-violet-400 hover:text-violet-300 text-xs font-bold p-0.5"
              title="Add Breakpoint"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {showAddBp && (
            <form onSubmit={handleAddBreakpoint} className="p-2 bg-zinc-900 border border-zinc-800 rounded-xl space-y-1.5">
              <input
                type="text"
                placeholder="File path (e.g. main.py)"
                value={newBpFile}
                onChange={e => setNewBpFile(e.target.value)}
                className="w-full px-2 py-1 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-violet-500"
              />
              <div className="flex gap-1.5">
                <input
                  type="number"
                  placeholder="Line #"
                  value={newBpLine}
                  onChange={e => setNewBpLine(e.target.value)}
                  className="w-20 px-2 py-1 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-violet-500"
                />
                <button type="submit" className="flex-1 py-1 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-[11px] font-semibold cursor-pointer">
                  Add
                </button>
              </div>
            </form>
          )}

          <div className="space-y-1">
            {breakpoints.map((bp) => (
              <div
                key={bp.id}
                onClick={() => handleToggleBreakpoint(bp.id)}
                className="flex items-center justify-between p-2 bg-zinc-950 hover:bg-zinc-900 border border-zinc-800/80 rounded-xl text-[10.5px] font-mono cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${bp.enabled !== false ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]' : 'bg-zinc-600'}`} />
                  <span className={`truncate ${bp.enabled !== false ? 'text-zinc-200' : 'text-zinc-500 line-through'}`}>{bp.file}:{bp.line}</span>
                </div>
                <span className="text-[9.5px] text-zinc-500 font-sans">{bp.enabled !== false ? 'Active' : 'Disabled'}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 5. Debug REPL Console */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-emerald-400" /> Debug Console
          </div>
          <div className="p-2 bg-zinc-950 border border-zinc-800/80 rounded-xl font-mono text-[10px] text-zinc-400 h-28 overflow-y-auto space-y-1 pr-1 scrollbar-none">
            {replHistory.length === 0 ? (
              <div className="text-zinc-600 italic">Enter python or expression query below to evaluate in debug context.</div>
            ) : (
              replHistory.map((item, idx) => (
                <div key={idx} className="space-y-0.5">
                  <div className="text-violet-400 font-semibold">&gt; {item.query}</div>
                  {item.result && <div className="text-zinc-200 pl-2">{item.result}</div>}
                  {item.error && <div className="text-red-400 pl-2">{item.error}</div>}
                </div>
              ))
            )}
          </div>
          <form onSubmit={handleRunRepl} className="flex gap-1">
            <input
              type="text"
              value={replInput}
              onChange={e => setReplInput(e.target.value)}
              placeholder="Evaluate expression (e.g. sys.version)"
              className="flex-1 px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-violet-500"
            />
            <button type="submit" className="px-2.5 py-1 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-semibold cursor-pointer">
              Eval
            </button>
          </form>
        </div>

        {/* 6. Console Output Stream */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-blue-400" /> Stdout Logs
          </div>
          <div className="p-2 bg-zinc-950 border border-zinc-800/80 rounded-xl font-mono text-[9.5px] text-zinc-400 h-24 overflow-y-auto space-y-1 pr-1 select-text scrollbar-none">
            {consoleLogs.length === 0 ? (
              <div className="text-zinc-600 italic">No output logged yet.</div>
            ) : (
              consoleLogs.map((log, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all text-zinc-300">{log}</div>
              ))
            )}
          </div>
        </div>

        {/* 7. Bug Scanner Report */}
        {bugReport.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10.5px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Bug className="w-3.5 h-3.5 text-violet-400" /> Bug Scan Report
            </div>
            <div className="p-2 bg-zinc-950 border border-zinc-800/80 rounded-xl font-mono text-[9.5px] text-zinc-300 h-24 overflow-y-auto space-y-1 pr-1 select-text scrollbar-none">
              {bugReport.map((item, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all text-zinc-300">{item}</div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}