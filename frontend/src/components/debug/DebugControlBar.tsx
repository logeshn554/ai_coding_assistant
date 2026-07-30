import React, { useState, useEffect } from 'react';
import { Play, Pause, CornerDownRight, CornerRightDown, CornerUpLeft, RotateCcw, Square } from 'lucide-react';

export const DebugControlBar: React.FC = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [activeFrame, setActiveFrame] = useState('');

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/debug/status');
      const data = await res.json();
      setIsRunning(Boolean(data.running));
      setActiveFrame(data.active_frame || '');
    } catch {}
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  if (!isRunning) return null;

  const handleAction = async (endpoint: string) => {
    try {
      await fetch(`/api/debug/${endpoint}`, { method: 'POST' });
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div
      className="absolute top-2 right-6 z-40 flex items-center gap-1 px-2.5 py-1 backdrop-blur-sm border rounded-[4px] shadow-md text-xs select-none"
      style={{
        background: '#2B2D30',
        borderColor: '#393B40',
        color: '#DFE1E5',
      }}
    >
      <div className="flex items-center gap-1.5 pr-2 border-r border-[var(--dp-border)]">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="font-mono text-[10.5px] text-[var(--dp-text-primary)] font-medium truncate max-w-[140px]">
          {activeFrame || 'Debugging'}
        </span>
      </div>

      <button
        onClick={() => handleAction('continue')}
        className="p-1 hover:bg-white/5 text-emerald-400 hover:text-emerald-300 rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Continue (F5)"
      >
        <Play className="w-3.5 h-3.5 fill-current" />
      </button>

      <button
        onClick={() => handleAction('pause')}
        className="p-1 hover:bg-white/5 text-amber-400 hover:text-amber-300 rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Pause (F6)"
      >
        <Pause className="w-3.5 h-3.5 fill-current" />
      </button>

      <button
        onClick={() => handleAction('step-over')}
        className="p-1 hover:bg-white/5 text-[#4C8DFF] hover:text-[#6AA3FF] rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Step Over (F10)"
      >
        <CornerDownRight className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('step-into')}
        className="p-1 hover:bg-white/5 text-[#4C8DFF] hover:text-[#6AA3FF] rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Step Into (F11)"
      >
        <CornerRightDown className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('step-out')}
        className="p-1 hover:bg-white/5 text-[#4C8DFF] hover:text-[#6AA3FF] rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Step Out (Shift+F11)"
      >
        <CornerUpLeft className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('start')}
        className="p-1 hover:bg-white/5 text-[var(--dp-text-primary)] hover:text-white rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Restart"
      >
        <RotateCcw className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('stop')}
        className="p-1 hover:bg-red-500/10 text-[#FF6B6B] hover:text-red-300 rounded-[3px] transition-colors cursor-pointer border-0 bg-transparent"
        title="Stop Debugger (Shift+F5)"
      >
        <Square className="w-3.5 h-3.5 fill-current" />
      </button>
    </div>
  );
};

