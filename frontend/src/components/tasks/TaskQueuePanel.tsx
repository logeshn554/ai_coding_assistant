import React, { useState, useEffect } from 'react';
import {
  ListChecks,
  Clock,
  Plus
} from 'lucide-react';
import { useAI } from '../../core/ai/AIContext';

interface QueueTask {
  id: string;
  title: string;
  mode: string;
  priority: string;
  status: 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: number;
  elapsed_seconds: number;
  logs: string[];
}

export const TaskQueuePanel: React.FC = () => {
  const [tasks, setTasks] = useState<QueueTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<QueueTask | null>(null);

  const { handleSendMessage } = useAI();

  const fetchTasks = async () => {
    // Simulated queue fetch (backed by active tasks and local state)
    try {
      const res = await fetch('/api/chat/history');
      if (res.ok) {
        const data = await res.json();
        // Convert sessions to task queue view
        const queue: QueueTask[] = (data.sessions || []).slice(0, 8).map((s: any, idx: number) => ({
          id: s.id || `task_${idx}`,
          title: s.title || `Agent Task #${idx + 1}`,
          mode: 'Agent',
          priority: idx === 0 ? 'high' : 'medium',
          status: idx === 0 ? 'completed' : 'queued',
          progress: idx === 0 ? 100 : 0,
          created_at: Date.now() / 1000 - idx * 300,
          elapsed_seconds: 14 + idx * 2,
          logs: [`Started task '${s.title || 'Task'}'`, 'Completed all steps']
        }));
        setTasks(queue);
      }
    } catch (e) {
      console.error('Failed to fetch tasks queue:', e);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  const handleAddNewTask = () => {
    const title = prompt('Enter task prompt for Agent queue:');
    if (title) {
      handleSendMessage(title, 'Goal', false);
      fetchTasks();
    }
  };

  const statusBadge = (s: QueueTask['status']) => {
    switch (s) {
      case 'running':
        return <span className="text-violet-400 bg-violet-500/10 border border-violet-500/30 px-1.5 py-0.5 rounded text-[9px] font-bold animate-pulse">Running</span>;
      case 'completed':
        return <span className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 rounded text-[9px] font-bold">Completed</span>;
      case 'paused':
        return <span className="text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded text-[9px] font-bold">Paused</span>;
      default:
        return <span className="text-gray-400 bg-white/5 border border-white/10 px-1.5 py-0.5 rounded text-[9px] font-bold">Queued</span>;
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0d0e15] text-xs font-sans overflow-hidden border border-white/10 rounded-xl p-3 space-y-3">
      {/* ── Header ── */}
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div className="flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-emerald-400" />
          <div>
            <h4 className="font-bold text-white text-xs">Autonomous Agent Task Queue</h4>
            <p className="text-[10px] text-gray-400">
              {tasks.length} task(s) in pipeline
            </p>
          </div>
        </div>

        <button
          onClick={handleAddNewTask}
          className="flex items-center gap-1 text-[11px] font-bold text-white bg-violet-600 hover:bg-violet-500 px-2.5 py-1 rounded-lg transition-colors cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" /> Queue Task
        </button>
      </div>

      {/* ── Task List ── */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {tasks.length === 0 ? (
          <div className="text-center py-12 text-xs text-gray-500 italic">
            No agent tasks queued. Click 'Queue Task' to add autonomous goals.
          </div>
        ) : (
          tasks.map((task) => (
            <div
              key={task.id}
              onClick={() => setSelectedTask(task)}
              className={`p-3 rounded-xl border transition-all cursor-pointer space-y-2 ${
                selectedTask?.id === task.id
                  ? 'bg-violet-500/15 border-violet-500/40 text-white'
                  : 'bg-black/30 border-white/5 hover:border-white/15 text-gray-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-bold text-white text-xs truncate">{task.title}</span>
                  {statusBadge(task.status)}
                </div>
                <div className="flex items-center gap-1 text-[10px] text-gray-400 font-mono">
                  <Clock className="w-3 h-3 text-gray-500" /> {task.elapsed_seconds}s
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-black/40 h-1.5 rounded-full overflow-hidden border border-white/5">
                <div
                  className="h-full bg-gradient-to-r from-violet-500 to-emerald-400 transition-all duration-300"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
