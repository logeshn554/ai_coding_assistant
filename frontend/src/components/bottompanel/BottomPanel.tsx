import React from 'react';
import { AlertCircle, Code, Terminal as TerminalIcon, Globe, Activity, ListTodo, ChevronUp, ChevronDown, X } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useTerminal } from '../../core/terminal/TerminalContext';
import { useGit } from '../../core/git/GitContext';
import { useAI } from '../../core/ai/AIContext';
import TerminalArea from '../TerminalArea';

export interface ProblemItem {
  file: string;
  line: number;
  column: number;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

export const BottomPanel: React.FC = () => {
  const { workspacePath } = useWorkspace();
  const {
    bottomTab, setBottomTab,
    terminalHeight, setTerminalHeight,
    consoleLogs, activeProcesses,
    activeTerminalCommand, activeTerminalStatus,
    activeTerminalExitCode, activeTerminalElapsed
  } = useTerminal();
  const { gitChangesList } = useGit();
  const { handleKillProcess } = useAI();

  const [diagnostics, setDiagnostics] = React.useState<{ errors: number; warnings: number }>({ errors: 0, warnings: 0 });

  React.useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ errors: number; warnings: number }>).detail;
      if (detail) {
        setDiagnostics(detail);
      }
    };
    window.addEventListener('editor-diagnostics', handler);
    return () => window.removeEventListener('editor-diagnostics', handler);
  }, []);

  const tabs = [
    { id: 'terminal',     label: 'Terminal',      icon: TerminalIcon },
    { id: 'problems',     label: 'Problems',      icon: AlertCircle },
    { id: 'output',       label: 'Output',        icon: Code },
    { id: 'ports',        label: 'Ports',         icon: Globe },
    { id: 'debugConsole', label: 'Debug Console', icon: Activity },
    { id: 'tasks',        label: 'Tasks',         icon: ListTodo },
  ];

  const problemCount = diagnostics.errors + diagnostics.warnings || gitChangesList.length;
  const portCount    = activeProcesses.length;

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--dp-bg-primary)' }}>

      {/* ── Panel Tab Header ── */}
      <div
        className="h-[34px] flex items-center justify-between px-3 shrink-0 select-none"
        style={{ background: 'var(--dp-bg-tertiary)', borderBottom: '1px solid var(--dp-border)' }}
      >
        {/* Tabs */}
        <div className="flex items-center gap-0.5 h-full">
          {tabs.map(t => {
            const Icon = t.icon;
            const isActive = bottomTab === t.id;
            const badge = t.id === 'problems' ? problemCount : t.id === 'ports' ? portCount : 0;

            return (
              <button
                key={t.id}
                onClick={() => setBottomTab(t.id as any)}
                className={`
                  relative h-full px-3 flex items-center gap-1.5 text-[11px] font-medium transition-all cursor-pointer
                  ${isActive
                    ? 'text-[var(--dp-text-bright)]'
                    : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-secondary)]'
                  }
                `}
              >
                {/* Active underline */}
                {isActive && (
                  <span className="absolute bottom-0 left-1 right-1 h-[2px] bg-[var(--dp-accent)] rounded-t-full" />
                )}
                <Icon className={`w-3 h-3 ${isActive ? 'text-[var(--dp-accent)]' : ''}`} />
                <span>{t.label}</span>
                {badge > 0 && (
                  <span className={`dp-badge ${t.id === 'problems' ? 'dp-badge-error' : 'dp-badge-accent'}`}>
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Panel Actions */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTerminalHeight(Math.max(80, terminalHeight - 60))}
            className="w-6 h-6 flex items-center justify-center rounded text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5 transition-colors cursor-pointer"
            title="Decrease Panel Height"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setTerminalHeight(terminalHeight + 60)}
            className="w-6 h-6 flex items-center justify-center rounded text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5 transition-colors cursor-pointer"
            title="Increase Panel Height"
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setTerminalHeight(100)}
            className="w-6 h-6 flex items-center justify-center rounded text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5 transition-colors cursor-pointer"
            title="Minimize Panel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── Panel Content ── */}
      <div className="flex-1 overflow-hidden flex" style={{ background: '#111218' }}>

        {/* Terminal */}
        {bottomTab === 'terminal' && (
          <TerminalArea
            workspacePath={workspacePath}
            activeTerminalCommand={activeTerminalCommand}
            activeTerminalStatus={activeTerminalStatus}
            activeTerminalExitCode={activeTerminalExitCode}
            activeTerminalElapsed={activeTerminalElapsed}
          />
        )}

        {/* Problems */}
        {bottomTab === 'problems' && (
          <div className="flex-1 overflow-y-auto p-3 space-y-2 select-text">
            {diagnostics.errors > 0 || diagnostics.warnings > 0 ? (
              <div className="space-y-2">
                <div className="flex items-center gap-3 text-xs border-b border-white/5 pb-2">
                  {diagnostics.errors > 0 && (
                    <span className="flex items-center gap-1 text-[var(--dp-error)] font-semibold">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {diagnostics.errors} {diagnostics.errors === 1 ? 'Error' : 'Errors'}
                    </span>
                  )}
                  {diagnostics.warnings > 0 && (
                    <span className="flex items-center gap-1 text-[var(--dp-warning)] font-semibold">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {diagnostics.warnings} {diagnostics.warnings === 1 ? 'Warning' : 'Warnings'}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[var(--dp-text-muted)] italic">
                  LSP and Monaco language services are active. Select error lines directly in the active editor pane to jump to definition or auto-fix.
                </p>
              </div>
            ) : gitChangesList.length > 0 ? (
              gitChangesList.map((file, i) => (
                <div key={i} className="flex items-start gap-2 text-[11px] py-1 px-2 rounded-md hover:bg-white/4 cursor-pointer transition-colors">
                  <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-[var(--dp-warning)]" />
                  <div>
                    <span className="font-semibold text-[var(--dp-text-primary)] font-mono">{file.path.split('/').pop()}</span>
                    <span className="text-[var(--dp-text-muted)] ml-2">({file.path})</span>
                    <p className="text-[var(--dp-text-muted)] text-[10px] mt-0.5">Unsaved AI proposed edits. Review recommended.</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-24 gap-2">
                <AlertCircle className="w-8 h-8 text-[var(--dp-text-muted)]/30" />
                <p className="text-[11px] text-[var(--dp-text-muted)] italic">No problems detected in workspace.</p>
              </div>
            )}
          </div>
        )}

        {/* Output */}
        {bottomTab === 'output' && (
          <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] text-[#a0aabb] select-text space-y-0.5">
            {consoleLogs.length === 0 ? (
              <div className="flex items-center gap-2 text-[var(--dp-text-muted)] italic p-1">
                <Code className="w-4 h-4 opacity-30" />
                <span>No build output or console logs.</span>
              </div>
            ) : (
              consoleLogs.map((log, i) => (
                <div key={i} className="py-0.5 leading-normal pl-2 border-l border-white/5 whitespace-pre-wrap break-all">
                  {log}
                </div>
              ))
            )}
          </div>
        )}

        {/* Ports */}
        {bottomTab === 'ports' && (
          <div className="flex-1 overflow-y-auto p-3 text-[11px] select-text">
            {activeProcesses.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-24 gap-2">
                <Globe className="w-8 h-8 text-[var(--dp-text-muted)]/30" />
                <p className="text-[11px] text-[var(--dp-text-muted)] italic">No active ports or processes.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {activeProcesses.map((proc, i) => (
                  <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/3 border border-[var(--dp-border)] hover:border-[var(--dp-border-mid)] transition-colors">
                    <div>
                      <div className="font-semibold text-[var(--dp-text-bright)] font-mono text-[11px]">{proc.name}</div>
                      <div className="text-[10px] text-[var(--dp-text-muted)] font-mono">PID: {proc.pid} · {proc.command || 'N/A'}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      {proc.port && (
                        <span className="px-2 py-0.5 bg-[var(--dp-success)]/10 text-[var(--dp-success)] border border-[var(--dp-success)]/20 font-bold rounded-full font-mono text-[9px]">
                          :{proc.port}
                        </span>
                      )}
                      <button
                        onClick={() => handleKillProcess(proc.id)}
                        className="px-2.5 py-1 bg-[var(--dp-error)]/10 text-[var(--dp-error)] hover:bg-[var(--dp-error)]/20 text-[9px] rounded-lg border border-[var(--dp-error)]/20 font-semibold cursor-pointer transition-colors"
                      >
                        Kill
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Debug Console */}
        {bottomTab === 'debugConsole' && (
          <div className="flex-1 p-3 font-mono text-[11px] text-[var(--dp-text-muted)] flex items-center gap-2 italic">
            <Activity className="w-4 h-4 opacity-30" />
            Debug console is idle. Run agent or diagnostics to stream outputs.
          </div>
        )}

        {/* Tasks */}
        {bottomTab === 'tasks' && (
          <div className="flex-1 p-3 text-[11px] text-[var(--dp-text-muted)] flex items-center gap-2 italic">
            <ListTodo className="w-4 h-4 opacity-30" />
            No active background tasks.
          </div>
        )}
      </div>
    </div>
  );
};
