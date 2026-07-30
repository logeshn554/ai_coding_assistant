import React, { useEffect, useState, useCallback } from 'react';
import { Layers, Database, Code2, GitBranch, HardDrive, Play, RefreshCw, Terminal, Package } from 'lucide-react';
import type { ProjectContextInfo } from '../../types/chat';
import { useTerminal } from '../../core/terminal/TerminalContext';
import { useAI } from '../../core/ai/AIContext';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';

interface ProjectContextPanelProps {
  contextInfo: ProjectContextInfo;
  onReindex?: () => void;
  activeSessionId?: string;
}

interface Runnable {
  framework: string;
  language: string;
  packageManager: string;
  runCommand: string;
  installCommand: string;
  buildCommand: string;
  testCommand: string;
  dir: string;
}

interface ProjectMetadata {
  projectId?: string;
  name?: string;
  framework?: string;
  language?: string;
  packageManager?: string;
  installCommand?: string;
  runCommand?: string;
  buildCommand?: string;
  testCommand?: string;
  workspace?: string;
  runnables?: Runnable[];
}

export const ProjectContextPanel: React.FC<ProjectContextPanelProps> = ({
  contextInfo,
  onReindex,
  activeSessionId,
}) => {
  const { workspacePath } = useWorkspace();
  const [metadata, setMetadata] = useState<ProjectMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { setBottomTab } = useTerminal();
  const { handleSendMessage } = useAI();

  const fetchMetadata = useCallback(async () => {
    setIsLoading(true);
    try {
      // Always call the AI-powered analyze endpoint — never the stale cache GET
      const res = await fetch('/api/project/analyze', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('session_token') || ''}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMetadata(data);
      }
    } catch (e) {
      console.error('Failed to analyse project:', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch on mount and whenever the workspace changes
  useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata, workspacePath]);

  const handleRunProject = () => {
    const stored = localStorage.getItem('devpilot_detected_run_command');
    const runCmd = stored || metadata?.runCommand || '';

    if (runCmd) {
      setBottomTab('terminal');
      window.dispatchEvent(
        new CustomEvent('devpilot-run-terminal-command', { detail: { command: runCmd } })
      );
    } else {
      // Ask the AI agent to detect and run for us
      setIsAiPanelOpenSafe();
      handleSendMessage('run the project', 'Agent', true);
    }
  };

  // Graceful — only opens AI panel if a callback is wired (avoids import cycle)
  const setIsAiPanelOpenSafe = () => {
    window.dispatchEvent(new CustomEvent('devpilot-open-ai-panel'));
  };

  const handleAnalyze = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/project/analyze', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('session_token') || ''}` },
      });
      if (res.ok) {
        const data = await res.json();
        setMetadata(data);
      }
    } catch (e) {
      console.error('Failed to re-analyze project:', e);
    } finally {
      setIsLoading(false);
    }
  };

  const percentage = Math.min(
    Math.round((contextInfo.tokenUsage / (contextInfo.tokenBudget || 128000)) * 100),
    100
  );

  const runnables = metadata?.runnables ?? [];
  const isMultiService = runnables.length > 1;

  const displayFramework = metadata?.framework || contextInfo.framework || '—';
  const displayLanguage = metadata?.language || contextInfo.language || '—';
  const displayRunCmd = metadata?.runCommand || '';

  return (
    <div className="bg-[#12141c] border border-white/10 rounded-xl p-3 text-xs space-y-3 shadow-md">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div className="min-w-0">
          <h4 className="font-bold text-white text-xs flex items-center gap-1.5 truncate">
            <Layers className="w-4 h-4 text-[#4C8DFF] shrink-0" />
            {isLoading ? (
              <span className="animate-pulse text-gray-500">Detecting...</span>
            ) : (
              metadata?.name || 'Project Context'
            )}
          </h4>
          <p className="text-[10px] text-gray-400 mt-0.5 truncate">
            Session: {activeSessionId || 'default'}
          </p>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={handleRunProject}
            className="flex items-center gap-1 text-[11px] font-bold text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 px-2.5 py-1 rounded-lg transition-colors cursor-pointer shadow-sm"
            title={isMultiService ? `Run all ${runnables.length} services` : 'Run project'}
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            {isMultiService ? `Run All (${runnables.length})` : 'Run Project'}
          </button>

          <button
            onClick={() => { handleAnalyze(); if (onReindex) onReindex(); }}
            disabled={isLoading}
            className="p-1 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors cursor-pointer disabled:opacity-40"
            title="Re-analyse workspace"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <HardDrive className="w-3.5 h-3.5 text-blue-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Indexed Files</div>
            <div className="font-mono text-white font-bold truncate">
              {contextInfo.indexedFiles} / {contextInfo.totalFiles}
            </div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <GitBranch className="w-3.5 h-3.5 text-orange-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Git Branch</div>
            <div className="font-mono text-white font-bold truncate">
              {contextInfo.activeBranch || 'main'}
            </div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <Code2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Framework</div>
            <div className="font-medium text-white truncate" title={displayFramework}>
              {isLoading ? <span className="animate-pulse text-gray-500">…</span> : displayFramework}
            </div>
          </div>
        </div>

        <div className="bg-black/30 border border-white/5 p-2 rounded-lg flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0" />
          <div className="min-w-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase">Language</div>
            <div className="font-medium text-white truncate" title={displayLanguage}>
              {isLoading ? <span className="animate-pulse text-gray-500">…</span> : displayLanguage}
            </div>
          </div>
        </div>
      </div>

      {/* Single-service run command */}
      {!isMultiService && (
        <div className="bg-black/40 border border-white/5 p-2.5 rounded-lg space-y-1.5">
          <div className="flex items-center justify-between text-[10px] text-gray-400 font-semibold">
            <span className="flex items-center gap-1">
              <Terminal className="w-3 h-3 text-emerald-400" /> Execution Command
            </span>
            <span className="text-[9px] uppercase font-mono text-gray-500">
              {metadata?.packageManager || '—'}
            </span>
          </div>
          <div className="bg-black/60 border border-white/10 px-2 py-1.5 rounded font-mono text-[11px] text-emerald-300 font-bold truncate">
            {isLoading
              ? <span className="animate-pulse text-gray-500">Detecting…</span>
              : (displayRunCmd || <span className="text-gray-600 italic">none detected</span>)
            }
          </div>
        </div>
      )}

      {/* Multi-service runnables list */}
      {isMultiService && (
        <div className="bg-black/40 border border-white/5 p-2.5 rounded-lg space-y-2">
          <div className="flex items-center gap-1 text-[10px] text-gray-400 font-semibold">
            <Package className="w-3 h-3 text-[#4C8DFF]" />
            Services ({runnables.length}) — each runs in a split terminal
          </div>
          {runnables.map((r, i) => (
            <div key={i} className="bg-black/50 border border-white/5 rounded p-1.5 space-y-0.5">
              <div className="flex items-center justify-between">
                <span className="text-[#4C8DFF] font-semibold text-[10px]">{r.framework}</span>
                <span className="text-[9px] text-gray-500 font-mono">{r.dir}</span>
              </div>
              <div className="font-mono text-[10px] text-emerald-300 truncate" title={r.runCommand}>
                {r.runCommand}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Context Window Utilization */}
      <div className="pt-2 border-t border-white/5 space-y-1.5">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-400 font-semibold">Model Context Utilization</span>
          <span className="font-mono text-[#4C8DFF]">
            {contextInfo.tokenUsage.toLocaleString()} / {(contextInfo.tokenBudget || 128000).toLocaleString()} tokens ({percentage}%)
          </span>
        </div>
        <div className="w-full bg-black/40 h-2 rounded-full overflow-hidden border border-white/5">
          <div
            className={`h-full transition-all duration-300 ${
              percentage > 85 ? 'bg-red-500' : percentage > 60 ? 'bg-amber-400' : 'bg-gradient-to-r from-[#3B7AE8] to-[#4C8DFF]'
            }`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
};
