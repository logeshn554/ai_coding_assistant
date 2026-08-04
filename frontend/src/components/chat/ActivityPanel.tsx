import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Loader2, Wrench } from 'lucide-react';
import type { ChatMessage } from '../../types/chat';
import { ReasoningTimeline, toolMessagesToTimelineRows } from './ReasoningTimeline';

interface ActivityPanelProps {
  toolMessages: ChatMessage[];
  isGenerating?: boolean;
}

export const ActivityPanel: React.FC<ActivityPanelProps> = ({ toolMessages, isGenerating }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (toolMessages.length === 0 && !isGenerating) return null;

  const rows = toolMessagesToTimelineRows(toolMessages);
  const totalSteps = rows.length;
  const runningStep = rows.find(r => r.status === 'running');
  const failedStep = rows.find(r => r.status === 'error');

  // Derive top-level status
  let statusText = 'Completed';
  let statusColor = 'text-green-400';
  let StatusIcon = CheckCircle2;

  if (isGenerating || runningStep) {
    statusText = runningStep ? runningStep.action : 'Running...';
    statusColor = 'text-blue-400 animate-pulse';
    StatusIcon = Loader2;
  } else if (failedStep) {
    statusText = 'Failed';
    statusColor = 'text-red-400';
    StatusIcon = XCircle;
  }

  return (
    <div className="border border-zinc-800/80 bg-zinc-950/20 rounded-lg overflow-hidden transition-all duration-150 my-2">
      {/* Header Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 text-zinc-400 hover:text-zinc-300 bg-zinc-900/30 hover:bg-zinc-900/50 cursor-pointer select-none text-[12px] font-medium transition-all"
      >
        <div className="flex items-center gap-2 truncate">
          {isOpen ? (
            <ChevronDown className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
          )}
          <Wrench className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
          <span className="font-mono text-zinc-500 select-none">Activity ({totalSteps} step{totalSteps !== 1 ? 's' : ''})</span>
          <span className="text-zinc-600 font-sans">•</span>
          <div className={`flex items-center gap-1.5 truncate ${statusColor}`}>
            {StatusIcon === Loader2 ? (
              <Loader2 className="w-3 h-3 animate-spin shrink-0" />
            ) : (
              <StatusIcon className="w-3.5 h-3.5 shrink-0" />
            )}
            <span className="truncate">{statusText}</span>
          </div>
        </div>
      </button>

      {/* Collapsible Content */}
      {isOpen && (
        <div className="px-3 py-2 bg-zinc-950/40 border-t border-zinc-900/60 transition-all">
          <ReasoningTimeline rows={rows} isGenerating={Boolean(isGenerating)} />
        </div>
      )}
    </div>
  );
};
