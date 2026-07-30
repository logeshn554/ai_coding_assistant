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
    <div className="h-full flex flex-col font-sans select-none border-r border-[var(--dp-border)]" style={{ background: '#1E1F22', color: '#DFE1E5' }}>
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--dp-border)] flex items-center justify-between shrink-0" style={{ background: '#2B2D30' }}>
        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--dp-text-primary)] flex items-center gap-1.5 font-sans">
          <Bug className="w-4 h-4 text-[#4C8DFF]" />
          Run & Debug
        </span>
        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-[2px] border" style={isRunning ? { background: 'rgba(98,210,111,0.15)', borderColor: '#62D26F', color: '#62D26F' } : { background: '#2B2D30', borderColor: '#393B40', color: '#6F737A' }}>
          {isRunning ? 'RUNNING' : 'STOPPED'}
        </span>
      </div>

      {/* Control Action Toolbar */}
      <div className="p-2 border-b border-[var(--dp-border)] flex gap-1.5 shrink-0" style={{ background: '#2B2D30' }}>
        {!isRunning ? (
          <button
            onClick={handleStart}
            className="flex-1 py-1.5 bg-[#62D26F] hover:bg-[#82F28F] text-white rounded-[4px] text-[11px] font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-colors"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Run Project
          </button>
        ) : (
          <>
            <button
              onClick={handleStop}
              className="flex-1 py-1.5 bg-[#FF6B6B] hover:bg-red-500 text-white rounded-[4px] text-[11px] font-semibold flex items-center justify-center gap-1.5 cursor-pointer transition-colors"
            >
              <Square className="w-3.5 h-3.5 fill-current" /> Stop
            </button>
            <button
              onClick={handleRestart}
              className="py-1.5 px-3 border rounded-[4px] text-[11px] font-semibold flex items-center justify-center cursor-pointer transition-colors"
              style={{ background: '#2B2D30', color: '#DFE1E5', borderColor: '#393B40' }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#3B3D42'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = '#2B2D30'; }}
              title="Restart Session"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </>
        )}
        <button
          onClick={fetchBugReport}
          className="px-3 py-1.5 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-[4px] text-[11px] font-semibold flex items-center justify-center gap-1 cursor-pointer transition-colors"
          title="Scan workspace for bugs"
        >
          <Bug className="w-3.5 h-3.5" /> Scan
        </button>
      </div>

      {/* Main Panels Feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4 font-sans scrollbar-none">
        
        {/* 1. Variables & Scope */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-[#4C8DFF]" /> Variables & Scope
          </div>
          <div className="p-2.5 border border-[var(--dp-border)] rounded-[4px] font-mono text-[10.5px] text-[var(--dp-text-primary)] space-y-1" style={{ background: '#2B2D30' }}>
            <div className="flex justify-between items-center"><span className="text-[#4C8DFF] font-semibold">active_frame:</span> <span className="text-[var(--dp-text-primary)]">{activeFrame}</span></div>
            <div className="flex justify-between items-center"><span className="text-[#4C8DFF] font-semibold">is_running:</span> <span className={isRunning ? 'text-[#62D26F] font-bold' : 'text-[var(--dp-text-muted)]'}>{isRunning ? 'true' : 'false'}</span></div>
            <div className="flex justify-between items-center"><span className="text-[#4C8DFF] font-semibold">breakpoints:</span> <span className="text-[var(--dp-text-primary)]">{breakpoints.length} active</span></div>
          </div>
        </div>

        {/* 2. Watch Expressions */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
              <Eye className="w-3.5 h-3.5 text-[#4C8DFF]" /> Watch
            </div>
          </div>
          <form onSubmit={handleAddWatch} className="flex gap-1">
            <input
              type="text"
              value={newWatchInput}
              onChange={e => setNewWatchInput(e.target.value)}
              placeholder="Add watch expression (e.g. state.root)"
              className="flex-1 px-2 py-1 border border-[var(--dp-border)] rounded-[4px] text-[11px] font-mono text-[var(--dp-text-primary)] focus:outline-none focus:border-[#4C8DFF]"
              style={{ background: '#1E1F22' }}
            />
            <button type="submit" className="px-2.5 py-1 border border-[var(--dp-border)] rounded-[4px] text-xs font-bold cursor-pointer" style={{ background: '#2B2D30', color: '#DFE1E5' }}>+</button>
          </form>
          <div className="space-y-1">
            {watchExprs.map(w => (
              <div key={w.id} className="flex items-center justify-between p-2 border border-[var(--dp-border)] rounded-[4px] text-[10.5px] font-mono" style={{ background: '#2B2D30' }}>
                <span className="text-[#4C8DFF] truncate max-w-[140px]">{w.expr}</span>
                <span className="text-[var(--dp-text-secondary)] truncate max-w-[100px]">{w.val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 3. Call Stack */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-[#FFB74D]" /> Call Stack
          </div>
          <div className="space-y-1">
            {callstack.length === 0 ? (
              <div className="p-2 border border-[var(--dp-border)] rounded-[4px] text-[10.5px] text-[var(--dp-text-muted)] italic" style={{ background: '#2B2D30' }}>No stack frame active.</div>
            ) : (
              callstack.map(frame => (
                <div key={frame.id} className="flex items-center justify-between p-2 border border-[var(--dp-border)] rounded-[4px] text-[10.5px] font-mono" style={{ background: '#2B2D30' }}>
                  <span className="font-bold text-[var(--dp-text-primary)]">{frame.name}()</span>
                  <span className="text-[var(--dp-text-secondary)] text-[9.5px] truncate max-w-[150px]">{frame.file.split('/').pop()}:L{frame.line}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 4. Breakpoints Management */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
              <List className="w-3.5 h-3.5 text-[#4C8DFF]" /> Breakpoints
            </div>
            <button
              onClick={() => setShowAddBp(!showAddBp)}
              className="text-[#4C8DFF] hover:text-[#6AA3FF] text-xs font-bold p-0.5"
              title="Add Breakpoint"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          {showAddBp && (
            <form onSubmit={handleAddBreakpoint} className="p-2 border border-[var(--dp-border)] rounded-[4px] space-y-1.5" style={{ background: '#2B2D30' }}>
              <input
                type="text"
                placeholder="File path (e.g. main.py)"
                value={newBpFile}
                onChange={e => setNewBpFile(e.target.value)}
                className="w-full px-2 py-1 border border-[var(--dp-border)] rounded-[3px] text-[11px] font-mono text-[var(--dp-text-primary)] focus:outline-none focus:border-[#4C8DFF]"
                style={{ background: '#1E1F22' }}
              />
              <div className="flex gap-1.5">
                <input
                  type="number"
                  placeholder="Line #"
                  value={newBpLine}
                  onChange={e => setNewBpLine(e.target.value)}
                  className="w-20 px-2 py-1 border border-[var(--dp-border)] rounded-[3px] text-[11px] font-mono text-[var(--dp-text-primary)] focus:outline-none focus:border-[#4C8DFF]"
                  style={{ background: '#1E1F22' }}
                />
                <button type="submit" className="flex-1 py-1 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-[3px] text-[11px] font-semibold cursor-pointer border-0">
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
                className="flex items-center justify-between p-2 hover:bg-white/5 border border-[var(--dp-border)] rounded-[4px] text-[10.5px] font-mono cursor-pointer transition-colors"
                style={{ background: '#2B2D30' }}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${bp.enabled !== false ? 'bg-[#FF6B6B] shadow-[0_0_8px_rgba(255,107,107,0.8)]' : 'bg-[var(--dp-text-muted)]'}`} />
                  <span className={`truncate ${bp.enabled !== false ? 'text-[var(--dp-text-primary)]' : 'text-[var(--dp-text-muted)] line-through'}`}>{bp.file}:{bp.line}</span>
                </div>
                <span className="text-[9.5px] text-[var(--dp-text-secondary)] font-sans">{bp.enabled !== false ? 'Active' : 'Disabled'}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 5. Debug REPL Console */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-[#62D26F]" /> Debug Console
          </div>
          <div className="p-2 border border-[var(--dp-border)] rounded-[4px] font-mono text-[10px] text-[var(--dp-text-secondary)] h-28 overflow-y-auto space-y-1 pr-1 scrollbar-none" style={{ background: '#2B2D30' }}>
            {replHistory.length === 0 ? (
              <div className="text-[var(--dp-text-muted)] italic">Enter python or expression query below to evaluate in debug context.</div>
            ) : (
              replHistory.map((item, idx) => (
                <div key={idx} className="space-y-0.5">
                  <div className="text-[#4C8DFF] font-semibold">&gt; {item.query}</div>
                  {item.result && <div className="text-[var(--dp-text-primary)] pl-2">{item.result}</div>}
                  {item.error && <div className="text-[#FF6B6B] pl-2">{item.error}</div>}
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
              className="flex-1 px-2.5 py-1 border border-[var(--dp-border)] rounded-[4px] text-[11px] font-mono text-[var(--dp-text-primary)] focus:outline-none focus:border-[#4C8DFF]"
              style={{ background: '#1E1F22' }}
            />
            <button type="submit" className="px-2.5 py-1 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-[4px] text-xs font-semibold cursor-pointer border-0">
              Eval
            </button>
          </form>
        </div>

        {/* 6. Console Output Stream */}
        <div className="space-y-1.5">
          <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-[#4C8DFF]" /> Stdout Logs
          </div>
          <div className="p-2 border border-[var(--dp-border)] rounded-[4px] font-mono text-[9.5px] text-[var(--dp-text-secondary)] h-24 overflow-y-auto space-y-1 pr-1 select-text scrollbar-none" style={{ background: '#2B2D30' }}>
            {consoleLogs.length === 0 ? (
              <div className="text-[var(--dp-text-muted)] italic">No output logged yet.</div>
            ) : (
              consoleLogs.map((log, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all text-[var(--dp-text-primary)]">{log}</div>
              ))
            )}
          </div>
        </div>

        {/* 7. Bug Scanner Report */}
        {bugReport.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-[10.5px] font-bold text-[var(--dp-text-secondary)] uppercase tracking-wider flex items-center gap-1.5">
              <Bug className="w-3.5 h-3.5 text-[#4C8DFF]" /> Bug Scan Report
            </div>
            <div className="p-2 border border-[var(--dp-border)] rounded-[4px] font-mono text-[9.5px] text-[var(--dp-text-primary)] h-24 overflow-y-auto space-y-1 pr-1 select-text scrollbar-none" style={{ background: '#2B2D30' }}>
              {bugReport.map((item, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all text-[var(--dp-text-primary)]">{item}</div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}