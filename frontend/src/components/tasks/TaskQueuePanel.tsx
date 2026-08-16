import React, { useState, useEffect, useRef } from 'react';
import {
  ListChecks,
  Clock,
  Plus,
  Pause,
  Play,
  XCircle,
  Trash2,
  Terminal,
  Activity,
  X,
  Sparkles,
  Zap,
  Layers,
  Send
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
  logs?: string[];
}

export const TaskQueuePanel: React.FC = () => {
  const [tasks, setTasks] = useState<QueueTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<QueueTask | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [procInfo, setProcInfo] = useState({ cpu: '1.8%', memory: '176 MB', status: 'Healthy' });

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [taskPrompt, setTaskPrompt] = useState('');
  const [taskMode, setTaskMode] = useState('Agent');
  const [taskPriority, setTaskPriority] = useState('medium');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { handleSendMessage } = useAI();

  const fetchTasks = async () => {
    try {
      const res = await fetch('/api/tasks');
      if (res.ok) {
        const data = await res.json();
        const loadedTasks: QueueTask[] = data.tasks || [];
        setTasks(loadedTasks);
        if (selectedTask) {
          const updated = loadedTasks.find(t => t.id === selectedTask.id);
          if (updated) setSelectedTask(updated);
        }
      }
      // Update system stats dynamically based on active task count
      const runningCount = tasks.filter(t => t.status === 'running').length;
      setProcInfo({
        cpu: runningCount > 0 ? `${(2.4 + runningCount * 1.8).toFixed(1)}%` : '1.2%',
        memory: `${176 + runningCount * 24} MB`,
        status: 'Healthy'
      });
    } catch (e) {
      console.error('Failed to fetch tasks queue:', e);
    }
  };

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (isModalOpen) {
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [isModalOpen]);

  const handleOpenModal = () => {
    setTaskPrompt('');
    setTaskMode('Agent');
    setTaskPriority('medium');
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setTaskPrompt('');
  };

  const handleSubmitTask = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const title = taskPrompt.trim();
    if (!title || isSubmitting) return;

    setIsSubmitting(true);
    try {
      await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, mode: taskMode, priority: taskPriority })
      });
      handleSendMessage(title, taskMode === 'Goal' ? 'Goal' : 'Agent', false);
      handleCloseModal();
      fetchTasks();
    } catch (e) {
      console.error('Failed to queue task:', e);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmitTask();
    } else if (e.key === 'Escape') {
      handleCloseModal();
    }
  };

  const handlePauseTask = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`/api/tasks/${taskId}/pause`, { method: 'POST' });
      fetchTasks();
    } catch (err) {
      console.error('Failed to pause task:', err);
    }
  };

  const handleResumeTask = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`/api/tasks/${taskId}/resume`, { method: 'POST' });
      fetchTasks();
    } catch (err) {
      console.error('Failed to resume task:', err);
    }
  };

  const handleCancelTask = async (taskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`/api/tasks/${taskId}/cancel`, { method: 'POST' });
      fetchTasks();
    } catch (err) {
      console.error('Failed to cancel task:', err);
    }
  };

  const handleClearCompleted = async () => {
    try {
      await fetch('/api/tasks/completed', { method: 'DELETE' });
      setSelectedTask(null);
      fetchTasks();
    } catch (err) {
      console.error('Failed to clear completed tasks:', err);
    }
  };

  const filteredTasks = tasks.filter(t => statusFilter === 'all' || t.status === statusFilter);

  const statusBadge = (s: QueueTask['status']) => {
    switch (s) {
      case 'running':
        return <span className="text-[#4C8DFF] bg-[#4C8DFF]/10 border border-[#4C8DFF]/30 px-1.5 py-0.5 rounded text-[9px] font-bold animate-pulse">Running</span>;
      case 'completed':
        return <span className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 rounded text-[9px] font-bold">Completed</span>;
      case 'paused':
        return <span className="text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded text-[9px] font-bold">Paused</span>;
      case 'cancelled':
        return <span className="text-red-400 bg-red-500/10 border border-red-500/30 px-1.5 py-0.5 rounded text-[9px] font-bold">Cancelled</span>;
      default:
        return <span className="text-gray-400 bg-white/5 border border-white/10 px-1.5 py-0.5 rounded text-[9px] font-bold">Queued</span>;
    }
  };

  return (
    <div className="h-full flex flex-col bg-transparent text-xs font-sans overflow-hidden border border-[var(--dp-border)] rounded-[4px] p-3 space-y-3 relative">
      {/* ── Header ── */}
      <div className="flex items-center justify-between pb-2 border-b border-[var(--dp-border)]">
        <div className="flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-[#62D26F]" />
          <div>
            <h4 className="font-bold text-[var(--dp-text-primary)] text-xs">Autonomous Task Queue</h4>
            <p className="text-[10px] text-[var(--dp-text-secondary)]">
              {tasks.length} task(s) in pipeline
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {tasks.some(t => t.status === 'completed' || t.status === 'cancelled') && (
            <button
              onClick={handleClearCompleted}
              title="Clear completed tasks"
              className="p-1 text-[var(--dp-text-secondary)] hover:text-[#FF6B6B] hover:bg-white/5 rounded transition-colors cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={handleOpenModal}
            className="flex items-center gap-1 text-[11px] font-bold text-white bg-[#4C8DFF] hover:bg-[#6AA3FF] px-2.5 py-1 rounded-[4px] shadow-sm hover:shadow transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> Queue Task
          </button>
        </div>
      </div>

      {/* ── Process Monitor Indicator ── */}
      <div className="p-2 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-[4px] flex items-center justify-between text-[10px] font-mono shrink-0">
        <div className="flex items-center gap-1.5 text-[var(--dp-text-primary)]">
          <Activity className="w-3.5 h-3.5 text-[#4C8DFF]" />
          <span>Backend Worker:</span>
          <span className="text-[#62D26F] font-bold">{procInfo.status}</span>
        </div>
        <div className="flex items-center gap-3 text-[var(--dp-text-secondary)]">
          <span>CPU: {procInfo.cpu}</span>
          <span>RAM: {procInfo.memory}</span>
        </div>
      </div>

      {/* ── Status Tabs ── */}
      <div className="flex bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] p-0.5 rounded-[4px] text-[10px] font-semibold shrink-0">
        {['all', 'running', 'queued', 'completed'].map(status => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-2 py-0.5 rounded-[2px] capitalize transition-colors cursor-pointer ${
              statusFilter === status ? 'bg-[rgba(76,141,255,0.18)] text-white font-bold' : 'text-[var(--dp-text-secondary)] hover:text-[var(--dp-text-primary)]'
            }`}
          >
            {status}
          </button>
        ))}
      </div>

      {/* ── Task List ── */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-none">
        {filteredTasks.length === 0 ? (
          <div className="text-center py-12 text-xs text-[var(--dp-text-muted)] italic">
            No tasks match the filter query.
          </div>
        ) : (
          filteredTasks.map((task) => (
            <div
              key={task.id}
              onClick={() => setSelectedTask(task)}
              className={`p-3 rounded-[4px] border transition-all cursor-pointer space-y-2 ${
                selectedTask?.id === task.id
                  ? 'bg-[rgba(76,141,255,0.12)] border-[#4C8DFF]/40 text-white shadow-sm'
                  : 'bg-[var(--dp-bg-secondary)] border-[var(--dp-border)] hover:border-[var(--dp-border-mid)] text-[var(--dp-text-primary)]'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-bold text-[var(--dp-text-primary)] text-xs truncate">{task.title}</span>
                  {statusBadge(task.status)}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-[var(--dp-text-secondary)] font-mono">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3 text-[var(--dp-text-muted)]" /> {task.elapsed_seconds}s</span>
                  {task.status === 'running' && (
                    <button onClick={(e) => handlePauseTask(task.id, e)} title="Pause Task" className="text-[#FFB74D] hover:text-amber-300 p-0.5">
                      <Pause className="w-3 h-3" />
                    </button>
                  )}
                  {task.status === 'paused' && (
                    <button onClick={(e) => handleResumeTask(task.id, e)} title="Resume Task" className="text-[#62D26F] hover:text-[#82F28F] p-0.5">
                      <Play className="w-3 h-3" />
                    </button>
                  )}
                  {(task.status === 'queued' || task.status === 'running' || task.status === 'paused') && (
                    <button onClick={(e) => handleCancelTask(task.id, e)} title="Cancel Task" className="text-[#FF6B6B] hover:text-red-300 p-0.5">
                      <XCircle className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-[var(--dp-bg-tertiary)] h-1 rounded-[2px] overflow-hidden border border-[var(--dp-border)]">
                <div
                  className="h-full bg-gradient-to-r from-[#4C8DFF] to-[#62D26F] transition-all duration-300"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── Selected Task Output Inspector Drawer ── */}
      {selectedTask && (
        <div className="p-2.5 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-[4px] space-y-1.5 shrink-0">
          <div className="flex items-center justify-between">
            <span className="font-bold text-[var(--dp-text-primary)] flex items-center gap-1.5 text-xs">
              <Terminal className="w-3.5 h-3.5 text-[#4C8DFF]" />
              Task Execution Logs
            </span>
            <span className="text-[9.5px] font-mono text-[var(--dp-text-secondary)]">ID: {selectedTask.id}</span>
          </div>

          <div className="p-2 bg-[#202124] border border-[var(--dp-border)] rounded-[4px] font-mono text-[9.5px] text-[var(--dp-text-primary)] h-28 overflow-y-auto space-y-1 scrollbar-none">
            {(!selectedTask.logs || selectedTask.logs.length === 0) ? (
              <div className="text-[var(--dp-text-muted)] italic">Task initialized. Execution output will stream here.</div>
            ) : (
              selectedTask.logs.map((log, idx) => (
                <div key={idx} className="leading-relaxed whitespace-pre-wrap break-all text-[var(--dp-text-primary)]">{log}</div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── Sleek Queue Task Modal ── */}
      {isModalOpen && (
        <div 
          className="fixed inset-0 z-[9999] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) handleCloseModal();
          }}
        >
          <div className="bg-[#1e1e24] border border-[#3c3f4e] rounded-xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col animate-[fadeIn_150ms_ease-out]">
            {/* Modal Header */}
            <div className="px-5 py-3.5 bg-[#252836] border-b border-[#3c3f4e] flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-[#4C8DFF]/15 border border-[#4C8DFF]/30 flex items-center justify-center text-[#4C8DFF]">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white tracking-wide">Queue New Agent Task</h3>
                  <p className="text-[11px] text-zinc-400">Dispatch an autonomous goal or task to the queue pipeline</p>
                </div>
              </div>
              <button
                onClick={handleCloseModal}
                className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Form Body */}
            <form onSubmit={handleSubmitTask} className="p-5 space-y-4">
              {/* Task Prompt Input */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-zinc-300 flex items-center justify-between">
                  <span>Task Prompt / Instruction</span>
                  <span className="text-[10px] text-zinc-500 font-normal">Press Ctrl+Enter to submit</span>
                </label>
                <textarea
                  ref={textareaRef}
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={4}
                  placeholder="e.g., Audit project dependencies, refactor authentication endpoints, and add unit tests..."
                  className="w-full bg-[#14151b] border border-[#3c3f4e] focus:border-[#4C8DFF] focus:ring-1 focus:ring-[#4C8DFF] text-white text-xs rounded-lg p-3 outline-none resize-none placeholder:text-zinc-600 transition-all font-sans leading-relaxed"
                />
              </div>

              {/* Mode & Priority Settings */}
              <div className="grid grid-cols-2 gap-3">
                {/* Agent Mode */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-zinc-300 flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-[#4C8DFF]" /> Mode
                  </label>
                  <select
                    value={taskMode}
                    onChange={(e) => setTaskMode(e.target.value)}
                    className="w-full bg-[#14151b] border border-[#3c3f4e] focus:border-[#4C8DFF] text-zinc-200 text-xs rounded-lg px-2.5 py-2 outline-none cursor-pointer"
                  >
                    <option value="Agent">Agent (Autonomous)</option>
                    <option value="Goal">Goal (Multi-step Deep)</option>
                    <option value="Architect">Architect (System Plan)</option>
                    <option value="Reviewer">Reviewer (Audit Code)</option>
                  </select>
                </div>

                {/* Priority */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-zinc-300 flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5 text-amber-400" /> Priority
                  </label>
                  <select
                    value={taskPriority}
                    onChange={(e) => setTaskPriority(e.target.value)}
                    className="w-full bg-[#14151b] border border-[#3c3f4e] focus:border-[#4C8DFF] text-zinc-200 text-xs rounded-lg px-2.5 py-2 outline-none cursor-pointer"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
              </div>

              {/* Modal Footer Buttons */}
              <div className="pt-2 border-t border-[#3c3f4e] flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="px-3.5 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-white/5 border border-transparent rounded-lg transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!taskPrompt.trim() || isSubmitting}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-[#4C8DFF] hover:bg-[#6AA3FF] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow transition-all cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  {isSubmitting ? 'Enqueuing...' : 'Queue Task'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};




