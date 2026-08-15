import React, { useState, useEffect, useCallback } from 'react';
import {
  GitBranch,
  ArrowUp,
  ArrowDown,
  GitCommit,
  ChevronRight,
  ChevronDown,
  Sparkles,
  Plus,
  Minus,
  Loader2,
  AlertTriangle,
  FolderGit2
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
  
  // New branch modal
  const [showNewBranch, setShowNewBranch] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');

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

  const handleGenerateCommitMsg = async () => {
    setGeneratingMsg(true);
    try {
      const diffRes = await fetch('/api/git/diff?staged=true');
      const { diff } = await diffRes.json();
      if (!diff?.trim()) {
        setCommitMsg('chore: workspace update');
        return;
      }
      const res = await fetch('/api/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prefix: `Generate a single concise conventional git commit message (e.g. feat: add feature or fix: bug) for the following changes:\n\n${diff.slice(0, 3000)}\n\nCommit message:`,
          suffix: '',
          language: 'text',
          file_path: '',
          max_tokens: 60,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const msg = (data.completion || '').trim().replace(/^["']|["']$/g, '');
        if (msg) setCommitMsg(msg);
      }
    } catch (e) {
      console.error('AI commit gen error', e);
    } finally {
      setGeneratingMsg(false);
    }
  };

  const gitAction = async (payload: { action: string; path?: string; message?: string; branch?: string }) => {
    try {
      const res = await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        loadGitData();
      }
    } catch (e) {
      console.error('git action error', e);
    }
  };

  const handleCreateBranch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBranchName.trim()) return;
    await gitAction({ action: 'create_branch', branch: newBranchName.trim() });
    setNewBranchName('');
    setShowNewBranch(false);
  };

  const toggleFileDiff = async (filePath: string) => {
    if (expandedFile === filePath) {
      setExpandedFile(null);
      return;
    }
    setExpandedFile(filePath);
    if (!fileDiffs[filePath]) {
      setLoadingDiff(filePath);
      try {
        const res = await fetch(`/api/git/diff?path=${encodeURIComponent(filePath)}`);
        const data = await res.json();
        setFileDiffs(prev => ({ ...prev, [filePath]: parseDiff(data.diff || '') }));
      } catch (e) {
        console.error('diff fetch error', e);
      } finally {
        setLoadingDiff(null);
      }
    }
  };

  const stagedFiles = files.filter(f => f.staged);
  const unstagedFiles = files.filter(f => !f.staged);

  const FileRow = ({ file }: { file: GitFile }) => {
    const isOpen = expandedFile === file.path;
    const diffLines = fileDiffs[file.path] || [];
    const lbl = statusLabel(file.status);
    const color = statusColor(file.status);

    const addCount = diffLines.filter(l => l.type === 'add').length;
    const delCount = diffLines.filter(l => l.type === 'remove').length;

    return (
      <div className="group border-b border-white/5 font-sans">
        <div
          onClick={() => toggleFileDiff(file.path)}
          className="flex items-center gap-2 px-3 py-1.5 hover:bg-white/[0.04] cursor-pointer transition-colors select-none"
        >
          <span className="text-zinc-500">
            {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </span>

          <span className="flex-1 text-xs font-mono text-zinc-200 truncate" title={file.path}>
            {file.path.split(/[/\\]/).pop()}
          </span>

          {isOpen && (addCount > 0 || delCount > 0) && (
            <span className="flex items-center gap-1 text-[9px] font-mono shrink-0">
              <span className="text-emerald-400">+{addCount}</span>
              <span className="text-red-400">-{delCount}</span>
            </span>
          )}

          <span
            className="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded shrink-0 uppercase"
            style={{ color, background: `color-mix(in srgb, ${color} 15%, transparent)` }}
          >
            {lbl}
          </span>

          <button
            onClick={e => { e.stopPropagation(); gitAction({ action: file.staged ? 'unstage' : 'stage', path: file.path }); }}
            className="opacity-0 group-hover:opacity-100 text-xs px-1.5 py-0.5 rounded transition-all cursor-pointer shrink-0 bg-[#4C8DFF]/20 hover:bg-[#4C8DFF]/30 text-[#4C8DFF]"
            title={file.staged ? 'Unstage Changes' : 'Stage Changes'}
          >
            {file.staged ? '−' : '+'}
          </button>
        </div>

        {isOpen && (
          <div className="text-[10px] font-mono max-h-48 overflow-y-auto bg-black/40 border-t border-white/5">
            {loadingDiff === file.path ? (
              <div className="flex items-center gap-1.5 px-3 py-2 text-zinc-400">
                <Loader2 className="w-3 h-3 animate-spin" /> Loading diff...
              </div>
            ) : diffLines.length === 0 ? (
              <div className="px-3 py-2 text-zinc-500 italic">No diff available</div>
            ) : (
              diffLines.map((line, i) => (
                <div
                  key={i}
                  className={`px-3 py-0.5 whitespace-pre leading-relaxed ${
                    line.type === 'add'
                      ? 'bg-emerald-500/10 text-emerald-400 border-l-2 border-emerald-500'
                      : line.type === 'remove'
                      ? 'bg-red-500/10 text-red-400 border-l-2 border-red-500'
                      : line.type === 'hunk'
                      ? 'bg-blue-500/10 text-blue-400 font-bold'
                      : 'text-zinc-300'
                  }`}
                >
                  {line.type === 'add' && '+ '}
                  {line.type === 'remove' && '- '}
                  {line.content}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    );
  };

  const SectionHeader = ({ title, count, actionBtn }: { title: string; count: number; actionBtn?: React.ReactNode }) => (
    <div className="px-3 py-1.5 flex items-center justify-between select-none bg-[#141620] border-b border-[#2A3146] text-[10px] font-bold uppercase tracking-wider text-zinc-400">
      <div className="flex items-center gap-1.5">
        <span>{title}</span>
        <span className="px-1.5 py-0.2 rounded-full bg-[#4C8DFF]/20 text-[#4C8DFF] text-[9px] font-mono">
          {count}
        </span>
      </div>
      {actionBtn}
    </div>
  );

  return (
    <div className="h-full flex flex-col font-sans select-none border-r border-[#2A3146] bg-[#11131A] text-zinc-200">
      
      {/* Header */}
      <div className="px-3.5 py-2.5 flex items-center justify-between shrink-0 bg-[#161922] border-b border-[#2A3146]">
        <div className="flex items-center gap-2">
          <FolderGit2 className="w-4 h-4 text-[#4C8DFF]" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">Source Control</span>
        </div>
        <button
          onClick={loadGitData}
          disabled={loading}
          className="text-xs font-semibold text-[#4C8DFF] hover:underline cursor-pointer disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Refresh'}
        </button>
      </div>

      {/* Branch selector & New Branch */}
      <div className="px-3 py-2 flex items-center justify-between gap-2 shrink-0 bg-[#141620] border-b border-[#2A3146]">
        <div className="flex items-center gap-1.5 text-xs text-zinc-300 min-w-0">
          <GitBranch className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0" />
          <span className="font-mono truncate">{branch}</span>
        </div>
        <div className="flex items-center gap-1">
          {branches.length > 0 && (
            <select
              value={branch}
              onChange={e => gitAction({ action: 'checkout', branch: e.target.value })}
              className="bg-black/40 border border-white/10 rounded-lg text-xs px-2 py-1 text-zinc-200 focus:outline-none cursor-pointer font-mono max-w-[110px]"
            >
              {branches.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          )}
          <button
            onClick={() => setShowNewBranch(!showNewBranch)}
            className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white cursor-pointer"
            title="Create New Branch"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* New Branch Inline Form */}
      {showNewBranch && (
        <form onSubmit={handleCreateBranch} className="p-2.5 bg-black/40 border-b border-[#2A3146] flex gap-1.5 animate-[fadeIn_150ms_ease-out]">
          <input
            type="text"
            placeholder="New branch name..."
            value={newBranchName}
            onChange={e => setNewBranchName(e.target.value)}
            className="flex-1 bg-black/50 border border-white/10 rounded-lg px-2 py-1 text-xs text-zinc-200 placeholder-zinc-500 font-mono focus:outline-none focus:border-[#4C8DFF]"
            autoFocus
          />
          <button
            type="submit"
            className="px-2.5 py-1 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-lg text-xs font-bold cursor-pointer"
          >
            Create
          </button>
        </form>
      )}

      {/* Merge Conflicts Banner */}
      {conflicts.length > 0 && (
        <div className="p-2.5 border-b border-amber-500/30 bg-amber-950/40 space-y-2 shrink-0">
          <div className="flex items-center gap-1.5 text-xs font-bold text-amber-400">
            <AlertTriangle className="w-4 h-4" />
            <span>{conflicts.length} Conflict{conflicts.length > 1 ? 's' : ''} Detected</span>
          </div>
          <div className="space-y-1.5">
            {conflicts.map(cf => (
              <div key={cf.path} className="p-2 bg-black/40 border border-amber-500/20 rounded-lg text-xs space-y-1 font-mono">
                <div className="text-zinc-200 font-semibold truncate">{cf.path}</div>
                <div className="flex gap-1 pt-0.5">
                  <button
                    onClick={() => handleResolveConflict(cf.path, 'current')}
                    disabled={resolvingPath === cf.path}
                    className="flex-1 py-1 bg-emerald-600/80 hover:bg-emerald-500 text-white rounded text-[10px] font-bold cursor-pointer"
                  >
                    Current
                  </button>
                  <button
                    onClick={() => handleResolveConflict(cf.path, 'incoming')}
                    disabled={resolvingPath === cf.path}
                    className="flex-1 py-1 bg-blue-600/80 hover:bg-blue-500 text-white rounded text-[10px] font-bold cursor-pointer"
                  >
                    Incoming
                  </button>
                  <button
                    onClick={() => handleResolveConflict(cf.path, 'both')}
                    disabled={resolvingPath === cf.path}
                    className="flex-1 py-1 bg-purple-600/80 hover:bg-purple-500 text-white rounded text-[10px] font-bold cursor-pointer"
                  >
                    Both
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Commit message & Action buttons */}
      <div className="p-3 space-y-2 shrink-0 bg-[#141620] border-b border-[#2A3146]">
        <div className="relative">
          <textarea
            value={commitMsg}
            onChange={e => setCommitMsg(e.target.value)}
            placeholder="Commit message (Ctrl+Enter to commit)..."
            rows={2}
            className="w-full resize-none bg-black/40 border border-white/10 rounded-xl p-2 pr-7 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[#4C8DFF]"
          />
          <button
            onClick={handleGenerateCommitMsg}
            disabled={generatingMsg}
            title="Generate commit message with AI"
            className="absolute top-2 right-2 text-[#4C8DFF] hover:text-[#6AA3FF] cursor-pointer disabled:opacity-50 transition-colors"
          >
            {generatingMsg ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="flex gap-1.5">
          <button
            onClick={() => gitAction({ action: 'commit', message: commitMsg })}
            disabled={!commitMsg.trim() || stagedFiles.length === 0}
            className="flex-1 py-1.5 bg-[#4C8DFF] hover:bg-[#6AA3FF] disabled:opacity-40 text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer shadow-sm transition-all"
          >
            <GitCommit className="w-3.5 h-3.5" /> Commit
          </button>
          <button
            onClick={() => gitAction({ action: 'pull' })}
            title="Pull remote changes"
            className="px-2.5 py-1.5 bg-[#1A1F2E] hover:bg-white/10 border border-[#2A3146] text-zinc-300 rounded-xl text-xs flex items-center cursor-pointer transition-colors"
          >
            <ArrowDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => gitAction({ action: 'push' })}
            title="Push to remote"
            className="px-2.5 py-1.5 bg-[#1A1F2E] hover:bg-white/10 border border-[#2A3146] text-zinc-300 rounded-xl text-xs flex items-center cursor-pointer transition-colors"
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Files Feed */}
      <div className="flex-1 overflow-y-auto">
        {files.length === 0 ? (
          <div className="py-12 text-center text-xs text-zinc-500 italic">
            Working tree clean — no changes detected
          </div>
        ) : (
          <>
            {/* Staged Changes */}
            {stagedFiles.length > 0 && (
              <div>
                <SectionHeader
                  title="Staged Changes"
                  count={stagedFiles.length}
                  actionBtn={
                    <button
                      onClick={() => gitAction({ action: 'unstage', path: '.' })}
                      className="text-zinc-400 hover:text-white p-0.5 cursor-pointer"
                      title="Unstage All Changes"
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                  }
                />
                {stagedFiles.map(f => <FileRow key={f.path} file={f} />)}
              </div>
            )}

            {/* Unstaged Changes */}
            {unstagedFiles.length > 0 && (
              <div>
                <SectionHeader
                  title="Changes"
                  count={unstagedFiles.length}
                  actionBtn={
                    <button
                      onClick={() => gitAction({ action: 'accept_all' })}
                      className="text-zinc-400 hover:text-white p-0.5 cursor-pointer"
                      title="Stage All Changes"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  }
                />
                {unstagedFiles.map(f => <FileRow key={f.path} file={f} />)}
              </div>
            )}
          </>
        )}

        {/* History Feed */}
        {history.length > 0 && (
          <div className="pt-2">
            <SectionHeader title="Recent Commits" count={history.length} />
            <div className="divide-y divide-white/5 font-mono text-[10px]">
              {history.map((log, idx) => (
                <div key={idx} className="px-3 py-1.5 text-zinc-400 hover:text-zinc-200 truncate" title={log}>
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