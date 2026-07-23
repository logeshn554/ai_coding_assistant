import React from 'react';
import { Settings, Check, AlertCircle, AlertTriangle, RotateCcw } from 'lucide-react';
import type { AgentState } from '../../types/chat';

interface AgentStatusBarProps {
  agents?: AgentState[];
  contextPercentage?: number;
  contextTokens?: string;
  activeProfileName?: string;
  totalCostUsd?: number;
  onOpenSettings?: () => void;
  onRetryAgent?: (agentType: string, taskId?: number | string) => void;
}

export const AgentStatusBar: React.FC<AgentStatusBarProps> = ({
  agents = [],
  contextPercentage = 0,
  contextTokens = '0',
  activeProfileName = 'Default',
  totalCostUsd = 0.0,
  onOpenSettings,
  onRetryAgent,
}) => {
  return (
    <div className="flex flex-col gap-2 pb-2 px-1 border-t border-zinc-800 pt-2 font-sans select-none bg-zinc-950">
      {/* Header Label & Agent Pills Row */}
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold tracking-wider text-zinc-500 uppercase shrink-0">
          Agent Status
        </span>
        {agents.length > 0 ? (
          <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 max-w-full">
            {agents.map((ag, idx) => {
              const isRunning = ag.status === 'running';
              const isDone = ag.status === 'done';
              const isError = ag.status === 'error';
              const isStuck = ag.status === 'stuck';
              const costDisplay = typeof ag.cost_usd === 'number' && ag.cost_usd > 0
                ? ` · $${ag.cost_usd.toFixed(3)}`
                : '';

              return (
                <div
                  key={`${ag.agent_type}-${idx}`}
                  className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono transition-all duration-150 shrink-0 border ${
                    isRunning
                      ? 'bg-blue-950/80 border-blue-500/50 text-blue-300 shadow-sm shadow-blue-500/10'
                      : isDone
                      ? 'bg-green-950/80 border-green-500/40 text-green-300'
                      : isStuck
                      ? 'bg-amber-950/80 border-amber-500/60 text-amber-300 shadow-sm shadow-amber-500/10'
                      : isError
                      ? 'bg-red-950/80 border-red-500/40 text-red-300'
                      : 'bg-zinc-900 border-zinc-800 text-zinc-400'
                  }`}
                >
                  {isRunning && (
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse shrink-0" />
                  )}
                  {isDone && <Check className="w-3 h-3 text-green-400 shrink-0" />}
                  {isStuck && <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />}
                  {isError && <AlertCircle className="w-3 h-3 text-red-400 shrink-0" />}
                  <span className="truncate max-w-[150px]">
                    {ag.agent_type}{costDisplay}
                  </span>
                  {isStuck && onRetryAgent && (
                    <button
                      type="button"
                      onClick={() => onRetryAgent(ag.agent_type, ag.taskId)}
                      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-amber-900/80 hover:bg-amber-800 text-amber-200 text-[10px] rounded cursor-pointer transition-colors"
                      title="Retry Agent"
                    >
                      <RotateCcw className="w-2.5 h-2.5" />
                      <span>Retry</span>
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <span className="text-[11px] text-zinc-600 italic">No active agents</span>
        )}
      </div>

      {/* Profile & Context Tokens Bar */}
      <div className="flex items-center justify-between font-mono text-[11px] text-zinc-400 pt-1 border-t border-zinc-900">
        <div className="flex items-center gap-2">
          {onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="p-1 hover:text-zinc-200 transition-colors cursor-pointer rounded hover:bg-zinc-800"
              title="Settings & Model Config"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>
          )}
          <span className="text-zinc-400 truncate max-w-[130px]" title={`Profile: ${activeProfileName}`}>
            Profile: {activeProfileName}
          </span>
          {totalCostUsd > 0 && (
            <span className="text-emerald-400 font-semibold text-[10.5px]">
              ${totalCostUsd.toFixed(3)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span>Tokens: {contextTokens}</span>
          <div className="flex items-center gap-1.5">
            <div className="w-12 h-1 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
              <div
                className={`h-full transition-all duration-300 ${
                  contextPercentage > 80
                    ? 'bg-red-500'
                    : contextPercentage > 50
                    ? 'bg-yellow-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${Math.min(contextPercentage, 100)}%` }}
              />
            </div>
            <span>{contextPercentage}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};
