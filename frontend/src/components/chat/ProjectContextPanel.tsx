import React from 'react';
import { Layers, Database, Code2, GitBranch, HardDrive, RefreshCw } from 'lucide-react';
import type { ProjectContextInfo } from '../../types/chat';

interface ProjectContextPanelProps {
  contextInfo: ProjectContextInfo;
  onReindex?: () => void;
}

export const ProjectContextPanel: React.FC<ProjectContextPanelProps> = ({
  contextInfo,
  onReindex
}) => {
  const percentage = Math.min(Math.round((contextInfo.tokenUsage / (contextInfo.tokenBudget || 128000)) * 100), 100);

  return (
    <div className="bg-[#12141c] border border-white/10 rounded-xl p-3 text-xs space-y-3 shadow-md">
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <h4 className="font-bold text-white text-xs flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-violet-400" /> Project Context Index
        </h4>
        {onReindex && (
          <button
            onClick={onReindex}
            className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 px-2 py-0.5 rounded transition-colors"
          >
            <RefreshCw className="w-3 h-3 text-violet-400" /> Re-index
          </button>
        )}
      </div>

      {/* Grid Specs */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <HardDrive className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <div>
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Indexed Files</div>
            <div className="font-mono text-white font-bold">{contextInfo.indexedFiles} / {contextInfo.totalFiles}</div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-orange-400 shrink-0" />
          <div>
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Git Branch</div>
            <div className="font-mono text-white font-bold">{contextInfo.activeBranch || 'main'}</div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <Code2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Framework</div>
            <div className="font-medium text-white">{contextInfo.framework || 'React / Vite'}</div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-purple-400 shrink-0" />
          <div>
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Language</div>
            <div className="font-medium text-white">{contextInfo.language || 'TypeScript / Python'}</div>
          </div>
        </div>
      </div>

      {/* Token Usage Bar */}
      <div className="pt-2 border-t border-white/5 space-y-1.5">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-400 font-semibold">Active Context Window</span>
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
