import React, { useState, useEffect, useCallback } from 'react';
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
  Eye,
  Trash2,
  ChevronRight,
  Loader2
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

interface WatchItem {
  id: string;
  expr: string;
  val: string;
  loading?: boolean;
}

export default function RunDebugSidebar() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeFrame, setActiveFrame] = useState('Idle');
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [bugReport, setBugReport] = useState<string[]>([]);
  const [isScanningBugs, setIsScanningBugs] = useState(false);
  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [callstack, setCallstack] = useState<StackFrame[]>([]);
  
  // New breakpoint inputs
  const [newBpFile, setNewBpFile] = useState('');
  const [newBpLine, setNewBpLine] = useState('');
  const [showAddBp, setShowAddBp] = useState(false);

  // Dynamic Watch expressions (loaded from local storage, default empty)
  const [watchExprs, setWatchExprs] = useState<WatchItem[]>(() => {
    try {
      const saved = localStorage.getItem('loopix_debug_watches');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [newWatchInput, setNewWatchInput] = useState('');
  
  // REPL Console
  const [replInput, setReplInput] = useState('');
  const [replHistory, setReplHistory] = useState<{ query: string; result?: string; error?: string }[]>([]);

  const fetchDebugInfo = useCallback(async () => {
    try {
      // 1. Status
      const statusRes = await fetch('/api/debug/status');
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setIsRunning(Boolean(statusData.running));
        setActiveFrame(statusData.active_frame || (statusData.running ? 'Running' : 'Idle'));
      }

      // 2. Logs
      const logsRes = await fetch('/api/debug/logs');
      if (logsRes.ok) {
        const logsData = await logsRes.json();
        setConsoleLogs(logsData.logs || []);
      }

      // 3. Breakpoints
      const bpRes = await fetch('/api/debug/breakpoints');
      if (bpRes.ok) {
        const bpData = await bpRes.json();
        setBreakpoints(bpData.breakpoints || []);
      }

      // 4. Callstack
      const csRes = await fetch('/api/debug/callstack');
      if (csRes.ok) {
        const csData = await csRes.json();
        setCallstack(csData.stack || []);
      }
    } catch (e) {
      console.error('Failed to fetch debug info:', e);
    }
  }, []);

  useEffect(() => {
    fetchDebugInfo();
    const interval = setInterval(fetchDebugInfo, 2500);
    return () => clearInterval(interval);
  }, [fetchDebugInfo]);

  // Re-evaluate watch expressions dynamically when running state changes
  useEffect(() => {
    if (watchExprs.length === 0) return;
    let isMounted = true;
    
    watchExprs.forEach(async (w) => {
      try {
        const res = await fetch('/api/debug/evaluate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ expression: w.expr })
        });
        if (res.ok && isMounted) {
          const data = await res.json();
          setWatchExprs(prev =>
            prev.map(item => item.id === w.id ? { ...item, val: data.result || data.error || (isRunning ? 'undefined' : 'idle') } : item)
          );
        }
      } catch {
        // keep existing val
      }
    });

    return () => { isMounted = false; };
  }, [isRunning]);

  const saveWatches = (list: WatchItem[]) => {
    setWatchExprs(list);
    try {
      localStorage.setItem('loopix_debug_watches', JSON.stringify(list));
    } catch {}
  };

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

  const handleScanBugs = async () => {
    setIsScanningBugs(true);
    try {
      const res = await fetch('/api/scan-bugs', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const reportArray = typeof data.report === 'string' ? [data.report] : (data.report || []);
        setBugReport(reportArray);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsScanningBugs(false);
    }
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

    const newItem: WatchItem = { id: String(Date.now()), expr, val: 'evaluating...', loading: true };
    const updated = [...watchExprs, newItem];
    saveWatches(updated);

    try {
      const res = await fetch('/api/debug/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression: expr })
      });
      const data = await res.json();
      saveWatches(updated.map(w => w.id === newItem.id ? { ...w, val: data.result || data.error || 'None', loading: false } : w));
    } catch {
      saveWatches(updated.map(w => w.id === newItem.id ? { ...w, val: 'offline', loading: false } : w));
    }
  };

  const handleDeleteWatch = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = watchExprs.filter(w => w.id !== id);
    saveWatches(updated);
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
    <div className="h-full flex flex-col font-sans select-none border-r border-[#2A3146] bg-[#11131A] text-zinc-200">
      
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-[#2A3146] bg-[#161922] flex items-center justify-between shrink-0">
        <span className="text-xs font-bold uppercase tracking-wider text-zinc-200 flex items-center gap-2">
          <Bug className="w-4 h-4 text-[#4C8DFF]" />
          Run & Debug
        </span>
        <span
          className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border ${
            isRunning
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 animate-pulse'
              : 'bg-zinc-800 text-zinc-400 border-zinc-700'
          }`}
        >
          {isRunning ? 'RUNNING' : 'STOPPED'}
        </span>
      </div>

      {/* Control Action Toolbar */}
      <div className="p-2 border-b border-[#2A3146] bg-[#141620] flex gap-1.5 shrink-0">
        {!isRunning ? (
          <button
            onClick={handleStart}
            className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer shadow-sm transition-all"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Run Project
          </button>
        ) : (
          <>
            <button
              onClick={handleStop}
              className="flex-1 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer shadow-sm transition-all"
            >
              <Square className="w-3.5 h-3.5 fill-current" /> Stop
            </button>
            <button
              onClick={handleRestart}
              className="py-1.5 px-3 bg-[#1A1F2E] hover:bg-white/10 text-zinc-300 border border-[#2A3146] rounded-lg text-xs font-semibold flex items-center justify-center cursor-pointer transition-colors"
              title="Restart Session"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </>
        )}
        <button
          onClick={handleScanBugs}
          disabled={isScanningBugs}
          className="px-3 py-1.5 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1 cursor-pointer transition-colors shadow-sm disabled:opacity-50"
          title="Scan workspace for bugs"
        >
          {isScanningBugs ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Bug className="w-3.5 h-3.5" />}
          <span>Scan</span>
        </button>
      </div>

      {/* Main Panels Feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3.5 font-sans">
        
        {/* 1. Variables & Scope */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-[#4C8DFF]" /> Variables & Scope
          </div>
          <div className="p-2.5 border border-[#2A3146] bg-[#161922] rounded-xl font-mono text-[10.5px] space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-[#4C8DFF] font-semibold">active_frame:</span>
              <span className="text-zinc-200 truncate max-w-[140px]">{activeFrame}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#4C8DFF] font-semibold">is_running:</span>
              <span className={isRunning ? 'text-emerald-400 font-bold' : 'text-zinc-500'}>
                {isRunning ? 'true' : 'false'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[#4C8DFF] font-semibold">breakpoints:</span>
              <span className="text-zinc-200">{breakpoints.length} active</span>
            </div>
          </div>
        </div>

        {/* 2. Dynamic Watch Expressions */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-[#4C8DFF]" /> Watch
            </div>
          </div>
          <form onSubmit={handleAddWatch} className="flex gap-1">
            <input
              type="text"
              value={newWatchInput}
              onChange={e => setNewWatchInput(e.target.value)}
              placeholder="Add watch expression..."
              className="flex-1 px-2.5 py-1 bg-black/40 border border-[#2A3146] rounded-lg text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-[#4C8DFF]"
            />
            <button
              type="submit"
              className="px-2.5 py-1 bg-[#161922] hover:bg-white/10 border border-[#2A3146] rounded-lg text-xs font-bold text-zinc-200 cursor-pointer"
            >
              +
            </button>
          </form>

          <div className="space-y-1">
            {watchExprs.length === 0 ? (
              <div className="p-2 border border-[#2A3146] bg-[#161922] rounded-xl text-[10.5px] text-zinc-500 italic font-mono text-center">
                No watch expressions added.
              </div>
            ) : (
              watchExprs.map(w => (
                <div
                  key={w.id}
                  className="flex items-center justify-between p-2 border border-[#2A3146] bg-[#161922] rounded-xl text-[10.5px] font-mono group"
                >
                  <span className="text-[#4C8DFF] truncate max-w-[120px]" title={w.expr}>{w.expr}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-300 truncate max-w-[90px]">{w.val}</span>
                    <button
                      onClick={(e) => handleDeleteWatch(w.id, e)}
                      className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition-opacity p-0.5 cursor-pointer"
                      title="Remove watch expression"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 3. Call Stack */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-amber-400" /> Call Stack
          </div>
          <div className="space-y-1">
            {callstack.length === 0 ? (
              <div className="p-2 border border-[#2A3146] bg-[#161922] rounded-xl text-[10.5px] text-zinc-500 italic font-mono text-center">
                No stack frame active.
              </div>
            ) : (
              callstack.map(frame => (
                <div
                  key={frame.id}
                  className="flex items-center justify-between p-2 border border-[#2A3146] bg-[#161922] rounded-xl text-[10.5px] font-mono"
                >
                  <span className="font-bold text-zinc-100">{frame.name}()</span>
                  <span className="text-zinc-400 text-[9.5px] truncate max-w-[140px]">
                    {frame.file.split(/[/\\]/).pop()}:L{frame.line}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 4. Breakpoints Management */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <List className="w-3.5 h-3.5 text-[#4C8DFF]" /> Breakpoints
            </div>
            <button
              onClick={() => setShowAddBp(!showAddBp)}
              className="text-[#4C8DFF] hover:text-[#6AA3FF] text-xs font-bold p-0.5 cursor-pointer"
              title="Add Breakpoint"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {showAddBp && (
            <form onSubmit={handleAddBreakpoint} className="p-2.5 border border-[#2A3146] bg-[#161922] rounded-xl space-y-1.5">
              <input
                type="text"
                placeholder="File path (e.g. main.py, app.js)"
                value={newBpFile}
                onChange={e => setNewBpFile(e.target.value)}
                className="w-full px-2.5 py-1 bg-black/40 border border-[#2A3146] rounded-lg text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-[#4C8DFF]"
              />
              <div className="flex gap-1.5">
                <input
                  type="number"
                  placeholder="Line #"
                  value={newBpLine}
                  onChange={e => setNewBpLine(e.target.value)}
                  className="w-20 px-2.5 py-1 bg-black/40 border border-[#2A3146] rounded-lg text-xs font-mono text-zinc-200 focus:outline-none focus:border-[#4C8DFF]"
                />
                <button
                  type="submit"
                  className="flex-1 py-1 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-lg text-xs font-bold cursor-pointer transition-colors"
                >
                  Add
                </button>
              </div>
            </form>
          )}

          <div className="space-y-1">
            {breakpoints.length === 0 ? (
              <div className="p-2 border border-[#2A3146] bg-[#161922] rounded-xl text-[10.5px] text-zinc-500 italic font-mono text-center">
                0 breakpoints registered.
              </div>
            ) : (
              breakpoints.map((bp) => (
                <div
                  key={bp.id}
                  onClick={() => handleToggleBreakpoint(bp.id)}
                  className="flex items-center justify-between p-2 hover:bg-white/5 border border-[#2A3146] bg-[#161922] rounded-xl text-[10.5px] font-mono cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${
                        bp.enabled !== false ? 'bg-[#FF6B6B] shadow-[0_0_8px_rgba(255,107,107,0.8)]' : 'bg-zinc-600'
                      }`}
                    />
                    <span
                      className={`truncate ${
                        bp.enabled !== false ? 'text-zinc-200' : 'text-zinc-500 line-through'
                      }`}
                    >
                      {bp.file}:{bp.line}
                    </span>
                  </div>
                  <span className="text-[9px] text-zinc-500 uppercase">{bp.enabled !== false ? 'active' : 'off'}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 5. Bug Scanner Results (if triggered) */}
        {bugReport.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                <Bug className="w-3.5 h-3.5" /> Bug Scanner Report
              </div>
              <button
                onClick={() => setBugReport([])}
                className="text-zinc-500 hover:text-zinc-300 text-[10px] cursor-pointer"
              >
                Clear
              </button>
            </div>
            <div className="p-2.5 border border-amber-500/30 bg-[#161922] rounded-xl font-mono text-[10.5px] text-zinc-300 space-y-1 max-h-40 overflow-y-auto">
              {bugReport.map((b, i) => (
                <p key={i} className="leading-snug">{b}</p>
              ))}
            </div>
          </div>
        )}

        {/* 6. Interactive Debug REPL / Console */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-emerald-400" /> Debug Console
            </div>
            {replHistory.length > 0 && (
              <button
                onClick={() => setReplHistory([])}
                className="text-zinc-500 hover:text-zinc-300 text-[10px] cursor-pointer"
              >
                Clear
              </button>
            )}
          </div>

          <div className="p-2 border border-[#2A3146] bg-[#161922] rounded-xl space-y-2">
            <div className="max-h-32 overflow-y-auto space-y-1 font-mono text-[10.5px]">
              {replHistory.length === 0 ? (
                <div className="text-zinc-500 italic text-[10px] py-1 text-center">
                  Enter expressions to evaluate in active runtime context.
                </div>
              ) : (
                replHistory.map((h, i) => (
                  <div key={i} className="space-y-0.5 border-b border-white/5 pb-1 last:border-0 last:pb-0">
                    <div className="flex items-center gap-1 text-zinc-400">
                      <ChevronRight className="w-3 h-3 text-[#4C8DFF] shrink-0" />
                      <span className="truncate">{h.query}</span>
                    </div>
                    {h.result && <div className="text-emerald-400 pl-4">{h.result}</div>}
                    {h.error && <div className="text-red-400 pl-4">{h.error}</div>}
                  </div>
                ))
              )}
            </div>

            <form onSubmit={handleRunRepl} className="flex gap-1 pt-1 border-t border-[#2A3146]">
              <input
                type="text"
                value={replInput}
                onChange={e => setReplInput(e.target.value)}
                placeholder="Evaluate expression..."
                className="flex-1 px-2 py-1 bg-black/40 border border-[#2A3146] rounded-lg text-xs font-mono text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-[#4C8DFF]"
              />
              <button
                type="submit"
                className="px-2.5 py-1 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-lg text-xs font-bold cursor-pointer transition-colors"
              >
                Eval
              </button>
            </form>
          </div>
        </div>

        {/* 7. Stdout Logs */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-zinc-400" /> Stdout Logs
            </div>
          </div>
          <div className="p-2 border border-[#2A3146] bg-[#161922] rounded-xl font-mono text-[10px] text-zinc-400 max-h-32 overflow-y-auto space-y-0.5">
            {consoleLogs.length === 0 ? (
              <span className="italic text-zinc-600 block text-center py-1">No output logged yet.</span>
            ) : (
              consoleLogs.map((log, i) => (
                <p key={i} className="leading-tight text-zinc-300 break-all">{log}</p>
              ))
            )}
          </div>
        </div>

      </div>

    </div>
  );
}