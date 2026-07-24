import React, { useEffect, useState } from 'react';
import { Layers, Database, Code2, GitBranch, HardDrive, Play, RefreshCw, Terminal } from 'lucide-react';
import type { ProjectContextInfo } from '../../types/chat';
import { useTerminal } from '../../core/terminal/TerminalContext';

interface ProjectContextPanelProps {
  contextInfo: ProjectContextInfo;
  onReindex?: () => void;
  activeSessionId?: string;
}

interface ProjectMetadata {
  projectId?: string;
  name?: string;
  framework?: string;
  language?: string;
  packageManager?: string;
  installCommand?: string;
  runCommand?: string;
  buildCommand?: string;
  testCommand?: string;
  workspace?: string;
}

export const ProjectContextPanel: React.FC<ProjectContextPanelProps> = ({
  contextInfo,
  onReindex,
  activeSessionId
}) => {
  const [metadata, setMetadata] = useState<ProjectMetadata | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const { setBottomTab } = useTerminal();

  const fetchMetadata = async () => {
    try {
      const res = await fetch('/api/project/metadata');
      if (res.ok) {
        const data = await res.json();
        setMetadata(data);
      }
    } catch (e) {
      console.error('Failed to fetch project metadata:', e);
    }
  };

  useEffect(() => {
    fetchMetadata();
  }, []);

  const handleRunProject = async () => {
    setIsRunning(true);
    setBottomTab('terminal');
    try {
      const res = await fetch('/api/project/run', { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        alert(data.detail || 'Failed to start project execution.');
      }
    } catch (e) {
      console.error('Failed to trigger project run:', e);
    } finally {
      setIsRunning(false);
    }
  };

  const handleAnalyze = async () => {
    try {
      const res = await fetch('/api/project/analyze', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setMetadata(data);
      }
    } catch (e) {
      console.error('Failed to re-analyze project:', e);
    }
  };

  const percentage = Math.min(Math.round((contextInfo.tokenUsage / (contextInfo.tokenBudget || 128000)) * 100), 100);

  return (
    <div className="bg-[#12141c] border border-white/10 rounded-xl p-3 text-xs space-y-3 shadow-md">
      {/* Header with Run Button */}
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div>
          <h4 className="font-bold text-white text-xs flex items-center gap-1.5">
            <Layers className="w-4 h-4 text-violet-400" /> {metadata?.name || 'Project Context'}
          </h4>
          <p className="text-[10px] text-gray-400 mt-0.5">Session: {activeSessionId || 'default'}</p>
        </div>
        
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleRunProject}
            disabled={isRunning}
            className="flex items-center gap-1 text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 px-2.5 py-1 rounded-lg transition-colors cursor-pointer shadow-sm disabled:opacity-50"
            title="Execute project run command in terminal"
          >
            <Play className="w-3.5 h-3.5 fill-current" /> Run Project
          </button>
          
          <button
            onClick={() => { handleAnalyze(); if (onReindex) onReindex(); }}
            className="p-1 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors cursor-pointer"
            title="Re-analyze stack and commands"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Grid Specs */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <HardDrive className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Indexed Files</div>
            <div className="font-mono text-white font-bold truncate">{contextInfo.indexedFiles} / {contextInfo.totalFiles}</div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-orange-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Git Branch</div>
            <div className="font-mono text-white font-bold truncate">{contextInfo.activeBranch || 'main'}</div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <Code2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Framework</div>
            <div className="font-medium text-white truncate">{metadata?.framework || contextInfo.framework || 'Detecting...'}</div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-purple-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Language</div>
            <div className="font-medium text-white truncate">{metadata?.language || contextInfo.language || 'Detecting...'}</div>
          </div>
        </div>
      </div>

      {/* Execution Commands Card */}
      <div className="bg-black/40 border border-white/5 p-2.5 rounded-lg space-y-1.5">
        <div className="flex items-center justify-between text-[10px] text-gray-400 font-semibold">
          <span className="flex items-center gap-1">
            <Terminal className="w-3 h-3 text-emerald-400" /> Execution Command
          </span>
          <span className="text-[9px] uppercase font-mono text-gray-500">{metadata?.packageManager || 'npm'}</span>
        </div>
        <div className="bg-black/60 border border-white/10 px-2 py-1.5 rounded font-mono text-[11px] text-emerald-300 font-bold truncate">
          {metadata?.runCommand || 'npm run dev'}
        </div>
      </div>

      {/* Context Window Utilization */}
      <div className="pt-2 border-t border-white/5 space-y-1.5">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-400 font-semibold">Model Context Utilization</span>
          <span className="font-mono text-violet-300">
            {contextInfo.tokenUsage.toLocaleString()} / {(contextInfo.tokenBudget || 128000).toLocaleString()} tokens ({percentage}%)
          </span>
        </div>
        <div className="w-full bg-black/40 h-2 rounded-full overflow-hidden border border-white/5">
          <div 
            className={`h-full transition-all duration-300 ${
              percentage > 85 ? 'bg-red-500' : percentage > 60 ? 'bg-amber-400' : 'bg-gradient-to-r from-violet-600 to-indigo-500'
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
};
