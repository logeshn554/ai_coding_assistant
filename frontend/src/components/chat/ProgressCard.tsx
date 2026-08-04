import React from 'react';
import { Loader2, CheckCircle2, Circle } from 'lucide-react';

interface ProgressCardProps {
  statusMessage: string | null;
  isGenerating: boolean;
}

interface StepState {
  label: string;
  status: 'pending' | 'active' | 'completed';
}

export const ProgressCard: React.FC<ProgressCardProps> = ({ statusMessage, isGenerating }) => {
  if (!isGenerating) return null;

  const msg = (statusMessage || '').toLowerCase();

  // Determine current active stage
  let activeIndex = 0; // default to planning
  if (msg.includes('read') || msg.includes('list') || msg.includes('inspect') || msg.includes('search')) {
    activeIndex = 1; // Reading Workspace
  } else if (msg.includes('generate') || msg.includes('completion') || msg.includes('llm') || msg.includes('reason')) {
    activeIndex = 2; // Generating Code
  } else if (msg.includes('write') || msg.includes('edit') || msg.includes('patch') || msg.includes('apply')) {
    activeIndex = 3; // Writing Files
  } else if (msg.includes('test') || msg.includes('validate') || msg.includes('run') || msg.includes('npm') || msg.includes('pytest')) {
    activeIndex = 4; // Validating
  }

  const steps: StepState[] = [
    { label: 'Planning', status: activeIndex === 0 ? 'active' : activeIndex > 0 ? 'completed' : 'pending' },
    { label: 'Reading Workspace', status: activeIndex === 1 ? 'active' : activeIndex > 1 ? 'completed' : 'pending' },
    { label: 'Generating Code', status: activeIndex === 2 ? 'active' : activeIndex > 2 ? 'completed' : 'pending' },
    { label: 'Writing Files', status: activeIndex === 3 ? 'active' : activeIndex > 3 ? 'completed' : 'pending' },
    { label: 'Validating', status: activeIndex === 4 ? 'active' : 'pending' }
  ];

  return (
    <div className="border border-zinc-800 bg-zinc-950/60 rounded-xl p-3.5 space-y-3 my-3 shadow-md animate-[fadeIn_150ms_ease-out]">
      <div className="flex items-center gap-2">
        <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
        <span className="text-[13px] font-semibold text-zinc-200">DevPilot Execution in Progress</span>
      </div>

      <div className="space-y-2 pl-1">
        {steps.map((step, idx) => (
          <div key={idx} className="flex items-center gap-2.5">
            {step.status === 'completed' && (
              <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
            )}
            {step.status === 'active' && (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
            )}
            {step.status === 'pending' && (
              <Circle className="w-4 h-4 text-zinc-700 shrink-0" />
            )}
            <span
              className={`text-[12px] ${
                step.status === 'active'
                  ? 'text-blue-300 font-semibold'
                  : step.status === 'completed'
                  ? 'text-zinc-500'
                  : 'text-zinc-600'
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {statusMessage && (
        <div className="pt-2 border-t border-zinc-900 font-mono text-[10.5px] text-zinc-500 truncate" title={statusMessage}>
          Status: {statusMessage}
        </div>
      )}
    </div>
  );
};
