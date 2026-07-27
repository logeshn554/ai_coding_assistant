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
    <div className="absolute top-3 right-6 z-40 flex items-center gap-1 px-3 py-1.5 bg-[#12131d]/90 backdrop-blur-md border border-violet-500/40 rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.6)] text-xs text-zinc-200 animate-in fade-in slide-in-from-top-2 duration-200 select-none">
      <div className="flex items-center gap-1.5 pr-2 border-r border-zinc-800">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
        </span>
        <span className="font-mono text-[10.5px] text-zinc-300 font-medium truncate max-w-[140px]">
          {activeFrame || 'Debugging'}
        </span>
      </div>

      <button
        onClick={() => handleAction('continue')}
        className="p-1.5 hover:bg-violet-600/30 text-emerald-400 hover:text-emerald-300 rounded-lg transition-colors cursor-pointer"
        title="Continue (F5)"
      >
        <Play className="w-3.5 h-3.5 fill-current" />
      </button>

      <button
        onClick={() => handleAction('pause')}
        className="p-1.5 hover:bg-violet-600/30 text-amber-400 hover:text-amber-300 rounded-lg transition-colors cursor-pointer"
        title="Pause (F6)"
      >
        <Pause className="w-3.5 h-3.5 fill-current" />
      </button>

      <button
        onClick={() => handleAction('step-over')}
        className="p-1.5 hover:bg-violet-600/30 text-blue-400 hover:text-blue-300 rounded-lg transition-colors cursor-pointer"
        title="Step Over (F10)"
      >
        <CornerDownRight className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('step-into')}
        className="p-1.5 hover:bg-violet-600/30 text-indigo-400 hover:text-indigo-300 rounded-lg transition-colors cursor-pointer"
        title="Step Into (F11)"
      >
        <CornerRightDown className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('step-out')}
        className="p-1.5 hover:bg-violet-600/30 text-purple-400 hover:text-purple-300 rounded-lg transition-colors cursor-pointer"
        title="Step Out (Shift+F11)"
      >
        <CornerUpLeft className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('start')}
        className="p-1.5 hover:bg-violet-600/30 text-zinc-300 hover:text-white rounded-lg transition-colors cursor-pointer"
        title="Restart"
      >
        <RotateCcw className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => handleAction('stop')}
        className="p-1.5 hover:bg-red-600/30 text-red-400 hover:text-red-300 rounded-lg transition-colors cursor-pointer"
        title="Stop Debugger (Shift+F5)"
      >
        <Square className="w-3.5 h-3.5 fill-current" />
      </button>
    </div>
  );
};
