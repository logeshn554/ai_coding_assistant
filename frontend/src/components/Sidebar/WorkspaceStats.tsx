import React from 'react';
import { ChevronsDownUp } from 'lucide-react';
import type { WorkspaceStatsData } from './types';

interface WorkspaceStatsProps {
  stats: WorkspaceStatsData | null;
  isExpanded: boolean;
  setIsExpanded: (expanded: boolean) => void;
}

export const WorkspaceStats: React.FC<WorkspaceStatsProps> = ({
  stats,
  isExpanded,
  setIsExpanded,
}) => {
  if (!stats) return null;

  return (
    <div className="border-t border-[#2a3142] bg-[#12151e] shrink-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-1.5 flex items-center justify-between text-[10px] font-semibold text-gray-400 hover:text-white uppercase tracking-wider hover:bg-white/5 transition-colors cursor-pointer"
      >
        <span>Workspace Stats</span>
        <ChevronsDownUp className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
      </button>

      {isExpanded && (
        <div className="px-3 pb-2 pt-1 text-[11px] space-y-1 text-gray-300 font-sans border-t border-[#2a3142]/40">
          <div className="flex justify-between">
            <span className="text-gray-500">Total Files:</span>
            <span className="font-mono text-gray-200">{stats.total_files.toLocaleString()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Total Lines:</span>
            <span className="font-mono text-gray-200">{stats.total_lines.toLocaleString()}</span>
          </div>
          {stats.git_commits > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-500">Git Commits:</span>
              <span className="font-mono text-gray-200">{stats.git_commits}</span>
            </div>
          )}
          {stats.languages && Object.keys(stats.languages).length > 0 && (
            <div className="pt-1">
              <span className="text-gray-500 text-[10px] block mb-1">Languages:</span>
              <div className="flex flex-wrap gap-1">
                {Object.entries(stats.languages).map(([lang, count]) => (
                  <span
                    key={lang}
                    className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[9px] font-mono text-gray-300"
                  >
                    {lang}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
