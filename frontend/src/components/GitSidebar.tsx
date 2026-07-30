import { useState, useEffect, useCallback } from 'react';
import {
  GitBranch, ArrowUp, ArrowDown, GitCommit,
  ChevronRight, ChevronDown, Sparkles, Plus, Minus, Loader2,
  AlertTriangle
} from 'lucide-react';



interface GitFile {
  path: string;
  status: string;
  staged: boolean;
}

interface ConflictFile {
  path: string;
  has_conflicts: boolean;
}

interface DiffLine {
  type: 'add' | 'remove' | 'context' | 'hunk';
  content: string;
}

function parseDiff(raw: string): DiffLine[] {
  const lines: DiffLine[] = [];
  for (const line of raw.split('\n')) {
    if (line.startsWith('@@')) lines.push({ type: 'hunk', content: line });
    else if (line.startsWith('+') && !line.startsWith('+++')) lines.push({ type: 'add', content: line.slice(1) });
    else if (line.startsWith('-') && !line.startsWith('---')) lines.push({ type: 'remove', content: line.slice(1) });
    else if (line.startsWith(' ')) lines.push({ type: 'context', content: line.slice(1) });
  }
  return lines;
}

function statusLabel(status: string): string {
  if (status === '??' || status === 'U') return 'U';
  if (status.includes('A')) return 'A';
  if (status.includes('D')) return 'D';
  return 'M';
}

function statusColor(s: string): string {
  const lbl = statusLabel(s);
  if (lbl === 'A') return 'var(--dp-git-added)';
  if (lbl === 'D') return 'var(--dp-git-deleted)';
  if (lbl === 'U') return 'var(--dp-git-untracked)';
  return 'var(--dp-git-modified)';
}

export default function GitSidebar() {
  const [branch, setBranch] = useState('main');
  const [files, setFiles] = useState<GitFile[]>([]);
  const [conflicts, setConflicts] = useState<ConflictFile[]>([]);
  const [branches, setBranches] = useState<string[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [commitMsg, setCommitMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatingMsg, setGeneratingMsg] = useState(false);
  const [resolvingPath, setResolvingPath] = useState<string | null>(null);

  // Per-file expanded diff state
  const [expandedFile, setExpandedFile] = useState<string | null>(null);
  const [fileDiffs, setFileDiffs] = useState<Record<string, DiffLine[]>>({});
  const [loadingDiff, setLoadingDiff] = useState<string | null>(null);

  const loadGitData = useCallback(async () => {
    setLoading(true);
    try {
      const [statusRes, branchRes, historyRes, conflictsRes] = await Promise.all([
        fetch('/api/git/status'),
        fetch('/api/git/branches'),
        fetch('/api/git/history'),
        fetch('/api/git/conflicts')
      ]);
      const statusData = await statusRes.json();
      setBranch(statusData.branch || 'main');
      setFiles(statusData.files || []);
      const branchData = await branchRes.json();
      setBranches(branchData.branches || []);
      const historyData = await historyRes.json();
      setHistory(historyData.history || []);
      const conflictsData = await conflictsRes.json();
      setConflicts(conflictsData.conflicts || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadGitData(); }, [loadGitData]);

  const handleResolveConflict = async (path: string, strategy: 'current' | 'incoming' | 'both') => {
    setResolvingPath(path);
    try {
      const res = await fetch('/api/git/resolve-conflict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, strategy })
      });
      if (res.ok) {
        loadGitData();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setResolvingPath(null);
    }
  };

  // ── AI commit message generation ─────────────────────────────────────────
  const handleGenerateCommitMsg = async () => {
    setGeneratingMsg(true);
    try {
      const diffRes = await fetch('/api/git/diff?staged=true');
      const { diff } = await diffRes.json();
      if (!diff?.trim()) {
        setCommitMsg('chore: no staged changes');
        return;
      }
      const res = await fetch('/api/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prefix: `You are a commit message generator. Given the following git diff, output ONLY a single conventional commit message (e.g. feat(scope): description). No explanation, no markdown, no quotes.\n\nDiff:\n${diff.slice(0, 3000)}\n\nCommit message:`,
          suffix: '',
          language: 'text',
          file_path: '',
          max_tokens: 80,
        }),
      });
      if (!res.ok) throw new Error('completions failed');
      const data = await res.json();
      const msg = (data.completion || '').trim().replace(/^["']|["']$/g, '');
      if (msg) setCommitMsg(msg);
    } catch (e) {
      console.error('AI commit gen error', e);
    } finally {
      setGeneratingMsg(false);
    }
  };

  // ── Inline file diff ──────────────────────────────────────────────────────
  const toggleFileDiff = async (path: string) => {
    if (expandedFile === path) { setExpandedFile(null); return; }
    setExpandedFile(path);
    if (fileDiffs[path]) return; // already loaded
    setLoadingDiff(path);
    try {
      const res = await fetch(`/api/git/diff?path=${encodeURIComponent(path)}`);
      const { diff } = await res.json();
      setFileDiffs(prev => ({ ...prev, [path]: parseDiff(diff || '') }));
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDiff(null);
    }
  };

  // ── Git actions ───────────────────────────────────────────────────────────
  const gitAction = async (body: object) => {
    try {
      const res = await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) loadGitData();
    } catch (e) { console.error(e); }
  };

  const handleCommit = async () => {
    if (!commitMsg.trim()) return;
    await gitAction({ action: 'commit', message: commitMsg });
    setCommitMsg('');
  };

  const stagedFiles = files.filter(f => f.staged);
  const unstagedFiles = files.filter(f => !f.staged);

  // ── File row ──────────────────────────────────────────────────────────────
  const FileRow = ({ file }: { file: GitFile }) => {
    const isOpen = expandedFile === file.path;
    const diffLines = fileDiffs[file.path] || [];
    const addCount = diffLines.filter(l => l.type === 'add').length;
    const delCount = diffLines.filter(l => l.type === 'remove').length;
    const color = statusColor(file.status);
    const lbl = statusLabel(file.status);

    return (
      <div style={{ borderBottom: '1px solid var(--dp-border)' }}>
        {/* Row header */}
        <div
          className="flex items-center gap-1.5 px-2 py-1 cursor-pointer group"
          style={{ background: 'var(--dp-bg-secondary)' }}
          onClick={() => toggleFileDiff(file.path)}
        >
          {/* Chevron */}
          <span style={{ color: 'var(--dp-text-muted)' }}>
            {isOpen
              ? <ChevronDown className="w-3 h-3" />
              : <ChevronRight className="w-3 h-3" />}
          </span>

          {/* Filename */}
          <span
            className="flex-1 text-[10px] font-mono truncate"
            style={{ color: 'var(--dp-text-primary)' }}
            title={file.path}
          >
            {file.path.split('/').pop()}
          </span>

          {/* +/- counts */}
          {isOpen && (addCount > 0 || delCount > 0) && (
            <span className="flex items-center gap-1 text-[9px] font-mono shrink-0">
              <span style={{ color: 'var(--dp-git-added)' }}>+{addCount}</span>
              <span style={{ color: 'var(--dp-git-deleted)' }}>-{delCount}</span>
            </span>
          )}

          {/* Status badge */}
          <span
            className="text-[8px] font-bold px-1 rounded shrink-0"
            style={{
              color,
              background: `color-mix(in srgb, ${color} 14%, transparent)`,
              border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
            }}
          >
            {lbl}
          </span>

          {/* Stage / unstage toggle */}
          <button
            onClick={e => { e.stopPropagation(); gitAction({ action: file.staged ? 'unstage' : 'stage', path: file.path }); }}
            className="opacity-0 group-hover:opacity-100 text-[9px] px-1.5 py-0.5 rounded transition-all cursor-pointer shrink-0"
            style={{
              background: 'var(--dp-accent-dim)',
              color: 'var(--dp-accent)',
              border: '1px solid color-mix(in srgb, var(--dp-accent) 25%, transparent)',
            }}
            title={file.staged ? 'Unstage' : 'Stage'}
          >
            {file.staged ? '−' : '+'}
          </button>
        </div>

        {/* Inline diff panel */}
        {isOpen && (
          <div
            className="text-[10px] font-mono overflow-x-auto"
            style={{ background: 'var(--dp-bg-primary)', maxHeight: '200px', overflowY: 'auto' }}
          >
            {loadingDiff === file.path ? (
              <div className="flex items-center gap-1.5 px-3 py-2" style={{ color: 'var(--dp-text-muted)' }}>
                <Loader2 className="w-3 h-3 animate-spin" /> Loading diff…
              </div>
            ) : diffLines.length === 0 ? (
              <div className="px-3 py-2" style={{ color: 'var(--dp-text-muted)' }}>No diff available</div>
            ) : (
              diffLines.map((line, i) => {
                let bg = 'transparent';
                let fg = 'var(--dp-text-primary)';
                let borderLeft = 'none';
                if (line.type === 'add') {
                  bg = 'rgba(52,211,153,0.08)';
                  fg = 'var(--dp-git-added)';
                  borderLeft = '2px solid var(--dp-git-added)';
                } else if (line.type === 'remove') {
                  bg = 'rgba(248,113,113,0.08)';
                  fg = 'var(--dp-git-deleted)';
                  borderLeft = '2px solid var(--dp-git-deleted)';
                } else if (line.type === 'hunk') {
                  bg = 'rgba(96,165,250,0.06)';
                  fg = 'var(--dp-info)';
                }
                return (
                  <div
                    key={i}
                    style={{ background: bg, color: fg, borderLeft, paddingLeft: '8px', whiteSpace: 'pre', lineHeight: '1.5' }}
                  >
                    {line.type === 'add' && <Plus className="inline w-2.5 h-2.5 mr-1" />}
                    {line.type === 'remove' && <Minus className="inline w-2.5 h-2.5 mr-1" />}
                    {line.content}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    );
  };

  // ── Section header ────────────────────────────────────────────────────────
  const SectionHeader = ({ title, count }: { title: string; count: number }) => (
    <div
      className="px-3 py-1 flex items-center justify-between select-none"
      style={{
        background: 'var(--dp-bg-tertiary)',
        borderBottom: '1px solid var(--dp-border)',
        fontSize: '9px',
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: 'var(--dp-text-muted)',
      }}
    >
      <span>{title}</span>
      <span
        className="px-1.5 py-0.5 rounded-full"
        style={{
          background: 'var(--dp-accent-dim)',
          color: 'var(--dp-accent)',
          fontSize: '8px',
          fontWeight: 800,
        }}
      >
        {count}
      </span>
    </div>
  );

  return (
    <div className="h-full flex flex-col font-sans" style={{ background: 'var(--dp-bg-primary)', color: 'var(--dp-text-primary)' }}>

      {/* ── Header ── */}
      <div
        className="px-3 py-1.5 flex items-center justify-between shrink-0 select-none"
        style={{ borderBottom: '1px solid var(--dp-border)', background: 'var(--dp-bg-tertiary)' }}
      >
        <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--dp-text-muted)' }}>
          Source Control
        </span>
        <button
          onClick={loadGitData}
          disabled={loading}
          className="cursor-pointer disabled:opacity-50 transition-colors"
          style={{ fontSize: '10px', color: 'var(--dp-accent)' }}
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Refresh'}
        </button>
      </div>

      {/* ── Branch selector ── */}
      <div
        className="px-2 py-1.5 flex items-center justify-between gap-2 shrink-0 select-none"
        style={{ borderBottom: '1px solid var(--dp-border)', background: 'var(--dp-bg-secondary)' }}
      >
        <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--dp-text-secondary)' }}>
          <GitBranch className="w-3.5 h-3.5" style={{ color: 'var(--dp-accent)' }} />
          <span className="font-mono">{branch}</span>
        </div>
        {branches.length > 0 && (
          <select
            value={branch}
            onChange={e => gitAction({ action: 'checkout', branch: e.target.value })}
            className="focus:outline-none cursor-pointer"
            style={{
              background: 'var(--dp-bg-elevated)',
              border: '1px solid var(--dp-border)',
              borderRadius: 'var(--dp-radius-sm)',
              fontSize: '10px',
              padding: '2px 4px',
              color: 'var(--dp-text-primary)',
              maxWidth: '120px',
            }}
          >
            {branches.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        )}
      </div>

      {/* Merge Conflicts Banner Panel */}
      {conflicts.length > 0 && (
        <div className="p-2 border-b border-amber-500/30 bg-amber-950/30 space-y-2 shrink-0">
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-amber-400">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{conflicts.length} Merge Conflict{conflicts.length > 1 ? 's' : ''} Detected</span>
          </div>
          <div className="space-y-1.5">
            {conflicts.map(cf => (
              <div key={cf.path} className="p-2 bg-black/40 border border-amber-500/20 rounded-lg text-[10px] space-y-1 font-mono">
                <div className="text-zinc-200 font-semibold truncate">{cf.path}</div>
                <div className="flex gap-1 pt-0.5">
                  <button
                    onClick={() => handleResolveConflict(cf.path, 'current')}
                    disabled={resolvingPath === cf.path}
                    className="flex-1 py-1 bg-emerald-600/80 hover:bg-emerald-500 text-white rounded text-[9px] font-sans font-bold cursor-pointer"
                  >
                    Accept Current
                  </button>
                  <button
                    onClick={() => handleResolveConflict(cf.path, 'incoming')}
                    disabled={resolvingPath === cf.path}
                    className="flex-1 py-1 bg-blue-600/80 hover:bg-blue-500 text-white rounded text-[9px] font-sans font-bold cursor-pointer"
                  >
                    Accept Incoming
                  </button>
                  <button
                    onClick={() => handleResolveConflict(cf.path, 'both')}
                    disabled={resolvingPath === cf.path}
                    className="flex-1 py-1 bg-[#3B7AE8]/80 hover:bg-[#4C8DFF] text-white rounded text-[9px] font-sans font-bold cursor-pointer"
                  >
                    Accept Both
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Commit area ── */}
      <div
        className="p-2 space-y-2 shrink-0"
        style={{ borderBottom: '1px solid var(--dp-border)', background: 'var(--dp-bg-secondary)' }}
      >
        <div className="relative">
          <textarea
            value={commitMsg}
            onChange={e => setCommitMsg(e.target.value)}
            placeholder="Commit message…"
            rows={2}
            className="w-full resize-none focus:outline-none font-sans"
            style={{
              background: 'var(--dp-bg-primary)',
              border: '1px solid var(--dp-border)',
              borderRadius: 'var(--dp-radius-sm)',
              padding: '6px 28px 6px 8px',
              fontSize: '10px',
              color: 'var(--dp-text-primary)',
            }}
          />
          {/* AI generate button */}
          <button
            onClick={handleGenerateCommitMsg}
            disabled={generatingMsg}
            title="Generate commit message with AI"
            className="absolute top-1.5 right-1.5 cursor-pointer disabled:opacity-50 transition-colors"
            style={{ color: 'var(--dp-accent)' }}
          >
            {generatingMsg
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Sparkles className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="flex gap-1.5">
          <button
            onClick={handleCommit}
            disabled={!commitMsg.trim() || stagedFiles.length === 0}
            className="flex-1 py-1 flex items-center justify-center gap-1 font-semibold cursor-pointer disabled:opacity-40 transition-colors"
            style={{
              background: 'var(--dp-accent)',
              color: '#fff',
              borderRadius: 'var(--dp-radius-sm)',
              fontSize: '10px',
            }}
          >
            <GitCommit className="w-3.5 h-3.5" />
            Commit ({stagedFiles.length})
          </button>
          <button
            onClick={() => gitAction({ action: 'pull' })}
            title="Pull"
            className="py-1 px-2 flex items-center gap-1 cursor-pointer transition-colors"
            style={{
              background: 'var(--dp-bg-active)',
              border: '1px solid var(--dp-border)',
              borderRadius: 'var(--dp-radius-sm)',
              fontSize: '10px',
              color: 'var(--dp-text-secondary)',
            }}
          >
            <ArrowDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => gitAction({ action: 'push' })}
            title="Push"
            className="py-1 px-2 flex items-center gap-1 cursor-pointer transition-colors"
            style={{
              background: 'var(--dp-bg-active)',
              border: '1px solid var(--dp-border)',
              borderRadius: 'var(--dp-radius-sm)',
              fontSize: '10px',
              color: 'var(--dp-text-secondary)',
            }}
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── Files feed ── */}
      <div className="flex-1 overflow-y-auto">
        {files.length === 0 ? (
          <div className="py-10 text-center text-xs italic" style={{ color: 'var(--dp-text-muted)' }}>
            No changes detected
          </div>
        ) : (
          <>
            {/* Staged */}
            {stagedFiles.length > 0 && (
              <div>
                <SectionHeader title="Staged Changes" count={stagedFiles.length} />
                {stagedFiles.map(f => <FileRow key={f.path} file={f} />)}
              </div>
            )}

            {/* Unstaged */}
            {unstagedFiles.length > 0 && (
              <div>
                <SectionHeader title="Changes" count={unstagedFiles.length} />
                {unstagedFiles.map(f => <FileRow key={f.path} file={f} />)}
              </div>
            )}
          </>
        )}

        {/* History */}
        {history.length > 0 && (
          <div className="pt-1">
            <SectionHeader title="Commit History" count={history.length} />
            <div className="space-y-0">
              {history.map((log, idx) => (
                <div
                  key={idx}
                  className="px-3 py-1.5 font-mono text-[9px] truncate"
                  style={{
                    color: 'var(--dp-text-secondary)',
                    borderBottom: '1px solid var(--dp-border)',
                  }}
                  title={log}
                >
                  {log}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}