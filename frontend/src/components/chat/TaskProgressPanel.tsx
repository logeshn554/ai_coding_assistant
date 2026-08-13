import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ClipboardList, CheckCircle2, Circle, Play, AlertCircle, HelpCircle } from 'lucide-react';
import type { TaskMemoryData, TaskStep } from '../../types/chat';

interface TaskProgressPanelProps {
  taskMemory: TaskMemoryData | null;
  onContinue?: () => void;
  isGenerating?: boolean;
}

export const TaskProgressPanel: React.FC<TaskProgressPanelProps> = ({
  taskMemory,
  onContinue,
  isGenerating = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!taskMemory || !taskMemory.steps || taskMemory.steps.length === 0) {
    return null;
  }

  const { steps, goal, intent, pending_steps, completed_steps } = taskMemory;
  const progressPercent = Math.round((completed_steps / steps.length) * 100);

  const getStepIcon = (status: TaskStep['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'in_progress':
        return <span className="w-4 h-4 rounded-full border-2 border-t-transparent border-sky-400 animate-spin shrink-0" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />;
      case 'skipped':
        return <HelpCircle className="w-4 h-4 text-zinc-500 shrink-0" />;
      default:
        return <Circle className="w-4 h-4 text-zinc-600 shrink-0" />;
    }
  };

  const getStepStyle = (status: TaskStep['status']) => {
    switch (status) {
      case 'completed':
        return { color: '#A0A5AD', textDecoration: 'line-through' };
      case 'in_progress':
        return { color: '#60A5FA', fontWeight: 'bold' };
      case 'failed':
        return { color: '#F87171', fontWeight: 'bold' };
      case 'skipped':
        return { color: '#71717A' };
      default:
        return { color: '#E4E4E7' };
    }
  };

  return (
    <div
      className="w-full rounded-xl overflow-hidden border border-zinc-700/80 bg-zinc-900/90 shadow-lg transition-all duration-300 mb-4"
      style={{ backdropFilter: 'blur(8px)' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 bg-zinc-800/50 border-b border-zinc-800 cursor-pointer select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-2">
          <ClipboardList className="w-4.5 h-4.5 text-sky-400 animate-pulse" />
          <span className="text-xs font-bold tracking-wider text-zinc-300 uppercase">
            Task Progress — {intent}
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
            {completed_steps}/{steps.length} Steps
          </span>
        </div>
        <div className="flex items-center gap-3">
          {pending_steps > 0 && onContinue && !isGenerating && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onContinue();
              }}
              className="flex items-center gap-1 px-3 py-1 bg-sky-600 hover:bg-sky-500 text-white rounded text-[11px] font-semibold transition-all shadow-md active:scale-95"
            >
              <Play className="w-3 h-3 fill-current" />
              Continue
            </button>
          )}
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-zinc-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-400" />
          )}
        </div>
      </div>

      {/* Expanded body */}
      {isExpanded && (
        <div className="p-4 space-y-4">
          {/* Progress Bar */}
          <div>
            <div className="flex justify-between text-[11px] text-zinc-400 mb-1">
              <span>Overall Completion</span>
              <span className="font-semibold">{progressPercent}%</span>
            </div>
            <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-sky-500 transition-all duration-500 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Goal */}
          <div className="p-2.5 rounded bg-zinc-800/30 border border-zinc-800/80">
            <span className="text-[10px] font-bold text-zinc-500 uppercase block mb-0.5">Objective</span>
            <p className="text-xs text-zinc-300 line-clamp-2">{goal}</p>
          </div>

          {/* Steps List */}
          <div className="space-y-2">
            <span className="text-[10px] font-bold text-zinc-500 uppercase block mb-1">Steps Plan</span>
            <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1">
              {steps.map((step) => (
                <div
                  key={step.id}
                  className="flex items-start gap-3 p-1.5 rounded transition-colors hover:bg-zinc-800/30"
                >
                  <div className="mt-0.5">{getStepIcon(step.status)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs leading-5" style={getStepStyle(step.status)}>
                      {step.task}
                    </p>
                    {step.error && (
                      <p className="text-[10px] text-rose-400/90 bg-rose-500/5 border border-rose-500/10 px-2 py-0.5 rounded mt-1 font-mono">
                        Error: {step.error}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
