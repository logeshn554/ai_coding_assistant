import React, { useState } from 'react';
import { 
  Terminal, FileText, FileCode, GitBranch, Search, CheckCircle2, 
  XCircle, Clock, ChevronDown, ChevronRight, RotateCcw, HelpCircle 
} from 'lucide-react';
import type { ToolExecutionItem } from '../../types/chat';

interface ToolExecutionCardProps {
  toolItem: ToolExecutionItem;
  onExplain?: (tool: ToolExecutionItem) => void;
  onRetry?: (tool: ToolExecutionItem) => void;
}

export const ToolExecutionCard: React.FC<ToolExecutionCardProps> = ({
  toolItem,
  onExplain,
  onRetry
}) => {
  const [expanded, setExpanded] = useState(false);

  const getToolIcon = () => {
    switch (toolItem.tool) {
      case 'terminal':
        return <Terminal className="w-4 h-4 text-green-400" />;
      case 'file_read':
        return <FileText className="w-4 h-4 text-blue-400" />;
      case 'file_edit':
        return <FileCode className="w-4 h-4 text-violet-400" />;
      case 'git':
        return <GitBranch className="w-4 h-4 text-orange-400" />;
      case 'search':
        return <Search className="w-4 h-4 text-cyan-400" />;
      default:
        return <FileText className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusBadge = () => {
    switch (toolItem.status) {
      case 'running':
        return (
          <span className="flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full font-medium border border-amber-500/20 animate-pulse">
            <Clock className="w-3 h-3" /> Running...
          </span>
        );
      case 'success':
        return (
          <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full font-medium border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" /> Completed
          </span>
        );
      case 'error':
        return (
          <span className="flex items-center gap-1 text-[10px] text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full font-medium border border-rose-500/20">
            <XCircle className="w-3 h-3" /> Error
          </span>
        );
    }
  };

  return (
    <div className="bg-[#12141c] border border-white/10 rounded-xl overflow-hidden my-2 text-xs transition-all duration-120 shadow-md">
      {/* Card Header */}
      <div 
        onClick={() => setExpanded(!expanded)}
        className="p-3 flex items-center justify-between cursor-pointer hover:bg-white/[0.02] transition-colors select-none"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-white/5 border border-white/5 shrink-0">
            {getToolIcon()}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white truncate">{toolItem.name}</span>
              {toolItem.durationMs && (
                <span className="text-[10px] text-gray-500 font-mono">
                  {(toolItem.durationMs / 1000).toFixed(1)}s
                </span>
              )}
            </div>
            <p className="text-[10px] text-gray-400 font-mono truncate">
              {toolItem.params ? JSON.stringify(toolItem.params).replace(/["{}]/g, '') : 'Execution'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {getStatusBadge()}
          <button className="text-gray-400 hover:text-white p-1">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-white/5 p-3 bg-[#0c0e14] space-y-2.5">
          {/* Params */}
          {toolItem.params && (
            <div>
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Parameters</span>
              <pre className="p-2 bg-black/40 border border-white/5 rounded-lg text-[10px] font-mono text-gray-300 overflow-x-auto">
                {JSON.stringify(toolItem.params, null, 2)}
              </pre>
            </div>
          )}

          {/* Output */}
          {toolItem.output && (
            <div>
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1">Output</span>
              <pre className="p-2 bg-black/40 border border-white/5 rounded-lg text-[10px] font-mono text-emerald-300 max-h-40 overflow-y-auto whitespace-pre-wrap">
                {toolItem.output}
              </pre>
            </div>
          )}

          {/* Action Bar */}
          <div className="flex items-center justify-end gap-2 pt-1 border-t border-white/5">
            {onExplain && (
              <button
                onClick={() => onExplain(toolItem)}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 text-[10px] text-gray-300 font-medium transition-colors"
              >
                <HelpCircle className="w-3 h-3 text-blue-400" /> Explain
              </button>
            )}
            {onRetry && (
              <button
                onClick={() => onRetry(toolItem)}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 text-[10px] text-amber-300 font-medium transition-colors"
              >
                <RotateCcw className="w-3 h-3 text-amber-400" /> Retry
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
