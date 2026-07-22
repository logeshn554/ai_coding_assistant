import { useEffect, useState } from 'react';
import { Database, Network, Clock, BarChart2, GitBranch, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { useWorkspace } from '../core/workspace/WorkspaceContext';
import { useGit } from '../core/git/GitContext';

// Language colour palette (deterministic by name)
const LANG_COLOURS: Record<string, string> = {
  TypeScript: '#3178C6',
  Python: '#3572A5',
  JavaScript: '#F1E05A',
  CSS: '#563D7C',
  HTML: '#E44D26',
  JSON: '#8BC34A',
  YAML: '#CB171E',
  Markdown: '#6E6E6E',
  Shell: '#89E051',
  Go: '#00ADD8',
  Rust: '#DEA584',
  Java: '#B07219',
  'C++': '#F34B7D',
  C: '#555555',
  'C#': '#178600',
  Ruby: '#701516',
  PHP: '#4F5D95',
  Kotlin: '#A97BFF',
  Swift: '#FA7343',
};

function getColour(lang: string): string {
  return LANG_COLOURS[lang] ?? '#7C6AF0';
}

interface WorkspaceStats {
  total_files: number;
  total_lines: number;
  languages: Record<string, number>;
  git_commits: number;
}

interface HealthData {
  status: string;
  db_connected: boolean;
  uptime_seconds: number;
}

function SkeletonBar() {
  return <div className="h-2 rounded-full bg-white/5 animate-pulse w-full" />;
}

export default function WorkspaceSidebar() {
  const { workspacePath } = useWorkspace();
  const { statusBarBranch } = useGit();

  const [stats, setStats] = useState<WorkspaceStats | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [history, setHistory] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const getWorkspaceName = () => {
    if (!workspacePath) return 'No Folder';
    return workspacePath.replace(/\\/g, '/').split('/').pop() || 'Workspace';
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      const [statsRes, healthRes, histRes] = await Promise.allSettled([
        fetch('/api/workspace/stats').then(r => r.json()),
        fetch('/api/health').then(r => r.json()),
        fetch('/api/git/history').then(r => r.json()),
      ]);

      if (statsRes.status === 'fulfilled') setStats(statsRes.value as WorkspaceStats);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value as HealthData);
      if (histRes.status === 'fulfilled') setHistory((histRes.value as any).history || []);
    } catch (e) {
      console.error('WorkspaceSidebar loadAll error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, [workspacePath]);

  // Build sorted language list for bar chart
  const langEntries = stats
    ? Object.entries(stats.languages).sort((a, b) => b[1] - a[1]).slice(0, 8)
    : [];

  const formatUptime = (secs: number) => {
    if (secs < 60) return `${Math.round(secs)}s`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m`;
    return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
  };

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] shrink-0 select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Workspace Dashboard</span>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-gray-500 font-mono truncate max-w-[100px]" title={workspacePath || ''}>
            {getWorkspaceName()}
          </span>
          <button
            onClick={loadAll}
            disabled={loading}
            className="p-0.5 text-gray-500 hover:text-gray-300 disabled:opacity-40 cursor-pointer rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Environment Status */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Local Environment</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-2">
            {/* Backend port */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-450 flex items-center gap-1.5">
                <Network className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Backend Port 8000
              </span>
              {loading ? (
                <span className="w-16 h-3 bg-white/5 animate-pulse rounded" />
              ) : health?.status === 'ok' ? (
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                  Online
                </span>
              ) : (
                <span className="text-red-400 font-semibold flex items-center gap-1">
                  <XCircle className="w-3 h-3 text-red-500" />
                  Offline
                </span>
              )}
            </div>

            {/* Secure Settings DB */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-455 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Secure Settings DB
              </span>
              {loading ? (
                <span className="w-16 h-3 bg-white/5 animate-pulse rounded" />
              ) : health?.db_connected ? (
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                  Connected
                </span>
              ) : (
                <span className="text-red-400 font-semibold flex items-center gap-1">
                  <XCircle className="w-3 h-3 text-red-500" />
                  Not found
                </span>
              )}
            </div>

            {/* Git Branch */}
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-455 flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Current Git Branch
              </span>
              <span className="text-gray-300 font-mono text-[10px] truncate max-w-[100px]">
                {statusBarBranch || '—'}
              </span>
            </div>

            {/* Uptime */}
            {health && (
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-gray-455 flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                  Server Uptime
                </span>
                <span className="text-gray-300 font-mono text-[10px]">
                  {formatUptime(health.uptime_seconds)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Stats Summary */}
        {(stats || loading) && (
          <div className="space-y-2">
            <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Codebase Stats</h3>
            <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 grid grid-cols-2 gap-2">
              {[
                { label: 'Files Tracked', val: stats ? stats.total_files.toLocaleString() : null },
                { label: 'Total Lines', val: stats ? stats.total_lines.toLocaleString() : null },
                { label: 'Git Commits', val: stats ? stats.git_commits.toLocaleString() : null },
                { label: 'Languages', val: stats ? Object.keys(stats.languages).length.toString() : null },
              ].map(({ label, val }) => (
                <div key={label} className="flex flex-col gap-0.5">
                  <span className="text-[8px] text-gray-600 uppercase tracking-wider">{label}</span>
                  {val == null ? (
                    <span className="h-3 w-10 bg-white/5 animate-pulse rounded" />
                  ) : (
                    <span className="text-[12px] text-white font-bold font-mono">{val}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Language Breakdown */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Project Languages</h3>
            <BarChart2 className="w-3 h-3 text-gray-500" />
          </div>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-3">
            {loading ? (
              <div className="space-y-1.5">
                <SkeletonBar />
                <div className="grid grid-cols-2 gap-2">
                  {[1, 2, 3, 4].map(i => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-white/10 shrink-0" />
                      <span className="h-2.5 bg-white/5 animate-pulse rounded w-full" />
                    </div>
                  ))}
                </div>
              </div>
            ) : langEntries.length === 0 ? (
              <div className="text-[9px] text-gray-600 italic text-center py-3">
                No workspace open or no recognised files found.
              </div>
            ) : (
              <>
                {/* Visual Bar */}
                <div className="w-full h-1.5 rounded-full flex overflow-hidden gap-px">
                  {langEntries.map(([lang, pct]) => (
                    <div
                      key={lang}
                      style={{ width: `${pct}%`, backgroundColor: getColour(lang) }}
                      className="h-full transition-all duration-500"
                      title={`${lang}: ${pct}%`}
                    />
                  ))}
                </div>
                {/* Legends */}
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  {langEntries.map(([lang, pct]) => (
                    <div key={lang} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: getColour(lang) }} />
                      <span className="text-gray-400 truncate">{lang}</span>
                      <span className="text-white font-semibold font-mono ml-auto">{pct}%</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Workspace Timeline (real git history) */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Recent Commits</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-3">
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="flex gap-2 items-start pl-2.5 border-l border-[#2d2d2d]">
                    <div className="h-3 bg-white/5 animate-pulse rounded w-full" />
                  </div>
                ))}
              </div>
            ) : history.length === 0 ? (
              <div className="text-[9px] text-gray-600 italic text-center py-3">
                No git history found in this workspace.
              </div>
            ) : (
              history.slice(0, 8).map((entry, i) => (
                <div key={i} className="flex gap-2 text-[10px] items-start border-l border-[#2d2d2d] pl-2.5 pb-1 relative">
                  <div className="absolute -left-[4px] top-1 w-2 h-2 rounded-full bg-[var(--dp-accent)] border border-[var(--dp-bg-tertiary)] shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-300 font-mono text-[9px] truncate" title={entry}>
                      {entry}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
