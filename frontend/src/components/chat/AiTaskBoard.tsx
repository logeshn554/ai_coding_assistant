import React from 'react';
import { Clock, Cpu } from 'lucide-react';
import type { AiTaskItem } from '../../types/chat';

interface AiTaskBoardProps {
  tasks: AiTaskItem[];
}

const PHASES: Array<{ id: AiTaskItem['phase']; title: string; color: string }> = [
  { id: 'planning', title: 'Planning', color: 'border-blue-500/40 text-blue-400' },
  { id: 'coding', title: 'Coding', color: 'border-violet-500/40 text-violet-400' },
  { id: 'testing', title: 'Testing', color: 'border-amber-500/40 text-amber-400' },
  { id: 'review', title: 'Review', color: 'border-purple-500/40 text-purple-400' },
  { id: 'deployment', title: 'Deployment', color: 'border-emerald-500/40 text-emerald-400' },
];

export const AiTaskBoard: React.FC<AiTaskBoardProps> = ({ tasks }) => {
  return (
    <div className="h-full flex flex-col bg-[#0e1017] p-3 text-xs overflow-hidden">
      <div className="flex items-center justify-between pb-3 border-b border-white/5 shrink-0">
        <div>
          <h3 className="font-bold text-white text-sm flex items-center gap-2">
            <span>📋 AI Task Board</span>
            <span className="text-[10px] font-mono text-gray-400 bg-white/5 px-2 py-0.5 rounded-full border border-white/5">
              {tasks.filter(t => t.status === 'completed').length} / {tasks.length} Completed
            </span>
          </h3>
          <p className="text-[11px] text-gray-400 mt-0.5">Automated phase tracking and multi-agent task workflow</p>
        </div>
      </div>

      {/* Kanban Board Grid */}
      <div className="flex-1 grid grid-cols-5 gap-3 pt-3 overflow-x-auto min-h-0">
        {PHASES.map((phase) => {
          const phaseTasks = tasks.filter((t) => t.phase === phase.id);

          return (
            <div 
              key={phase.id} 
              className="bg-[#12141d] border border-white/5 rounded-xl p-2.5 flex flex-col min-w-[170px] overflow-hidden"
            >
              {/* Phase Header */}
              <div className={`flex items-center justify-between pb-2 mb-2 border-b font-semibold text-[11px] ${phase.color}`}>
                <span>{phase.title}</span>
                <span className="text-[10px] bg-white/5 text-gray-400 px-1.5 py-0.2 rounded font-mono">
                  {phaseTasks.length}
                </span>
              </div>

              {/* Task Items */}
              <div className="flex-1 overflow-y-auto space-y-2 pr-0.5">
                {phaseTasks.length === 0 ? (
                  <div className="text-[10px] text-gray-600 text-center py-6 border border-dashed border-white/5 rounded-lg">
                    No tasks
                  </div>
                ) : (
                  phaseTasks.map((task) => (
                    <div 
                      key={task.id}
                      className="bg-[#181b26] border border-white/5 rounded-lg p-2.5 shadow-sm space-y-2 hover:border-violet-500/30 transition-colors"
                    >
                      <div className="font-medium text-white leading-tight text-[11px]">
                        {task.title}
                      </div>

                      {/* Progress Bar */}
                      <div className="w-full bg-black/40 h-1.5 rounded-full overflow-hidden">
                        <div 
                          className={`h-full transition-all duration-300 ${
                            task.status === 'completed'
                              ? 'bg-emerald-400'
                              : task.status === 'in_progress'
                              ? 'bg-violet-500 animate-pulse'
                              : task.status === 'failed'
                              ? 'bg-rose-500'
                              : 'bg-gray-600'
                          }`}
                          style={{ width: `${task.progress}%` }}
                        />
                      </div>

                      {/* Footer Info */}
                      <div className="flex items-center justify-between text-[9px] text-gray-400 pt-1 border-t border-white/5">
                        <span className="flex items-center gap-1">
                          <Cpu className="w-3 h-3 text-violet-400" />
                          {task.owner || 'AI Agent'}
                        </span>
                        {task.estimatedTime && (
                          <span className="flex items-center gap-1 font-mono text-gray-500">
                            <Clock className="w-2.5 h-2.5" />
                            {task.estimatedTime}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
