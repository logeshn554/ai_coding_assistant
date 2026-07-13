import { Database, Network, Clock, BarChart2, GitBranch } from 'lucide-react';
import { useWorkspace } from '../core/workspace/WorkspaceContext';
import { useGit } from '../core/git/GitContext';

export default function WorkspaceSidebar() {
  const { workspacePath } = useWorkspace();
  const { statusBarBranch } = useGit();

  const getWorkspaceName = () => {
    if (!workspacePath) return 'No Folder';
    return workspacePath.replace(/\\/g, '/').split('/').pop() || 'Workspace';
  };

  const languages = [
    { name: 'TypeScript', pct: 45, color: '#3178C6' },
    { name: 'Python', pct: 35, color: '#3572A5' },
    { name: 'CSS', pct: 15, color: '#563d7c' },
    { name: 'JSON/YML', pct: 5, color: '#f1e05a' }
  ];

  const history = [
    { author: 'logesh', action: 'committed settings update', time: '2h ago' },
    { author: 'DevPilot', action: 'proposed orchestrator.py fixes', time: '1h ago' },
    { author: 'logesh', action: 'started backend server', time: '40m ago' },
    { author: 'logesh', action: 'ran npm run dev', time: '35m ago' }
  ];

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] shrink-0 select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Workspace Dashboard</span>
        <span className="text-[9px] text-gray-500 font-mono truncate max-w-[120px]" title={workspacePath || ''}>
          {getWorkspaceName()}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Environment Status */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Local Environment</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-2">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-450 flex items-center gap-1.5">
                <Network className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Backend Port 8000
              </span>
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                Online
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-455 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Secure Settings DB
              </span>
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                Connected
              </span>
            </div>

            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-455 flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Current Git Branch
              </span>
              <span className="text-gray-300 font-mono text-[10px] truncate max-w-[100px]">
                {statusBarBranch}
              </span>
            </div>
          </div>
        </div>

        {/* Language Breakdown */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Project Languages</h3>
            <BarChart2 className="w-3 h-3 text-gray-500" />
          </div>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-3">
            {/* Visual Bar */}
            <div className="w-full h-1.5 rounded-full flex overflow-hidden">
              {languages.map((l) => (
                <div
                  key={l.name}
                  style={{ width: `${l.pct}%`, backgroundColor: l.color }}
                  className="h-full"
                  title={`${l.name}: ${l.pct}%`}
                />
              ))}
            </div>
            {/* Legends */}
            <div className="grid grid-cols-2 gap-2 text-[10px]">
              {languages.map((l) => (
                <div key={l.name} className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: l.color }} />
                  <span className="text-gray-400">{l.name}</span>
                  <span className="text-white font-semibold font-mono ml-auto">{l.pct}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Workspace Timeline */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Recent Workspace Actions</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-3">
            {history.map((h, i) => (
              <div key={i} className="flex gap-2 text-[10px] items-start border-l border-[#2d2d2d] pl-2.5 pb-1 relative">
                <div className="absolute -left-[4px] top-1 w-2 h-2 rounded-full bg-[var(--dp-accent)] border border-[var(--dp-bg-tertiary)] shrink-0" />
                <div className="flex-1">
                  <div className="text-white font-medium leading-none">
                    <span className="text-gray-400 font-semibold">{h.author}</span> {h.action}
                  </div>
                  <div className="text-[8px] text-gray-550 flex items-center gap-0.5 mt-1 font-mono">
                    <Clock className="w-2.5 h-2.5 text-gray-655" />
                    <span>{h.time}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
