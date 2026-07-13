import React from 'react';
import { AlertCircle, Code, Terminal as TerminalIcon, Globe, Activity, ListTodo } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useTerminal } from '../../core/terminal/TerminalContext';
import { useGit } from '../../core/git/GitContext';
import { useAI } from '../../core/ai/AIContext';
import TerminalArea from '../TerminalArea';

export const BottomPanel: React.FC = () => {
  const { workspacePath } = useWorkspace();
  const {
    bottomTab,
    setBottomTab,
    terminalHeight,
    setTerminalHeight,
    consoleLogs,
    activeProcesses,
    activeTerminalCommand,
    activeTerminalStatus,
    activeTerminalExitCode,
    activeTerminalElapsed
  } = useTerminal();
  const { gitChangesList } = useGit();
  const { handleKillProcess } = useAI();

  const tabs = [
    { id: 'problems', label: 'Problems', icon: AlertCircle },
    { id: 'output', label: 'Output', icon: Code },
    { id: 'terminal', label: 'Terminal', icon: TerminalIcon },
    { id: 'ports', label: 'Ports', icon: Globe },
    { id: 'debugConsole', label: 'Debug Console', icon: Activity },
    { id: 'tasks', label: 'Tasks', icon: ListTodo }
  ];

  return (
    <div
      style={{ height: `${terminalHeight}px` }}
      className="border-t border-[#2d2d2d] bg-[#181818] flex flex-col shrink-0 min-h-[50px] relative overflow-hidden"
    >
      {/* Panel Tabs Header */}
      <div className="h-[35px] border-b border-[#2d2d2d] flex items-center justify-between px-3 shrink-0 select-none bg-[#131313]">
        <div className="flex items-center gap-1.5 h-full text-xs">
          {tabs.map(t => {
            const isActive = bottomTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setBottomTab(t.id as any)}
                className={`px-3 py-1 cursor-pointer font-medium flex items-center gap-1.5 rounded transition-all font-sans text-[11px] ${
                  isActive
                    ? 'bg-white/10 text-white font-semibold'
                    : 'text-gray-400 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <span>{t.label}</span>
                {t.id === 'problems' && gitChangesList.length > 0 && (
                  <span className="bg-[#007acc] text-white font-bold rounded-full text-[9px] font-mono w-4 h-4 flex items-center justify-center shrink-0">
                    {gitChangesList.length}
                  </span>
                )}
                {t.id === 'ports' && activeProcesses.length > 0 && (
                  <span className="bg-[#8b5cf6]/20 text-violet-400 font-bold px-1.5 py-0.5 rounded-full text-[9px] font-mono shrink-0">
                    {activeProcesses.length}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Panel Actions */}
        <div className="flex items-center gap-2 text-gray-550 px-3 shrink-0">
          <button
            onClick={() => setTerminalHeight(100)}
            className="hover:text-white transition-colors cursor-pointer text-[10px]"
            title="Minimize Panel"
          >
            —
          </button>
          <button
            onClick={() => setTerminalHeight(350)}
            className="hover:text-white transition-colors cursor-pointer text-[10px]"
            title="Maximize Panel"
          >
            🗖
          </button>
        </div>
      </div>

      {/* Bottom Tab Contents */}
      <div className="flex-1 overflow-hidden flex bg-[#1e1e1e]">
        {bottomTab === 'terminal' && (
          <TerminalArea
            workspacePath={workspacePath}
            activeTerminalCommand={activeTerminalCommand}
            activeTerminalStatus={activeTerminalStatus}
            activeTerminalExitCode={activeTerminalExitCode}
            activeTerminalElapsed={activeTerminalElapsed}
          />
        )}
        {bottomTab === 'problems' && (
          <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-1 bg-[#1e1e1e] select-text scrollbar-thin">
            {gitChangesList.length === 0 ? (
              <div className="text-gray-500 italic p-1 font-sans">No problems have been detected in the workspace.</div>
            ) : (
              gitChangesList.map((file, i) => (
                <div key={i} className="flex items-start gap-2 text-yellow-500 py-0.5 hover:bg-white/5 px-2 rounded-none cursor-pointer">
                  <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  <div>
                    <div className="font-semibold font-mono">{file.path.split('/').pop()} <span className="text-[10px] text-gray-500 font-normal font-mono">({file.path})</span></div>
                    <div className="text-gray-400 text-[10px] font-sans">Unsaved AI proposed edits detected. Review recommended before compile.</div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
        {bottomTab === 'output' && (
          <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] text-[#cccccc] bg-[#1e1e1e] select-text scrollbar-thin">
            {consoleLogs.length === 0 ? (
              <div className="text-gray-550 italic p-1 font-sans">No build output or debug console logs.</div>
            ) : (
              consoleLogs.map((log, i) => (
                <div key={i} className="py-0.5 leading-normal border-l border-white/5 pl-2 select-text whitespace-pre-wrap truncate font-mono">
                  {log}
                </div>
              ))
            )}
          </div>
        )}
        {bottomTab === 'ports' && (
          <div className="flex-1 overflow-y-auto p-3 font-sans text-xs space-y-2 bg-[#1e1e1e] text-[#cccccc] select-text scrollbar-thin">
            {activeProcesses.length === 0 ? (
              <div className="text-gray-555 italic p-1">No active network ports or processes launched by DevPilot.</div>
            ) : (
              <div className="divide-y divide-[#2d2d2d] pr-2">
                {activeProcesses.map((proc, i) => (
                  <div key={i} className="flex items-center justify-between py-2 text-[11px]">
                    <div>
                      <div className="font-semibold text-white font-mono">{proc.name}</div>
                      <div className="text-[10px] text-gray-550 font-mono">PID: {proc.pid} | Command: {proc.command || 'N/A'}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      {proc.port && (
                        <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold rounded-none font-mono text-[9px]">
                          :{proc.port}
                        </span>
                      )}
                      <button
                        onClick={() => handleKillProcess(proc.id)}
                        className="px-2 py-0.5 bg-red-650/15 text-red-400 hover:bg-red-655/35 text-[9px] rounded-none border border-red-500/20 font-bold cursor-pointer font-sans"
                      >
                        Kill Process
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {bottomTab === 'debugConsole' && (
          <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] text-[#cccccc] bg-[#1e1e1e] select-text scrollbar-thin">
            <div className="text-gray-550 italic p-1 font-sans">Debug console is idle. Run agent or diagnostics to stream outputs.</div>
          </div>
        )}
        {bottomTab === 'tasks' && (
          <div className="flex-1 overflow-y-auto p-3 font-sans text-xs bg-[#1e1e1e] text-[#cccccc] select-text scrollbar-thin">
            <div className="text-gray-555 italic p-1">No active compiler background tasks executing.</div>
          </div>
        )}
      </div>
    </div>
  );
};
