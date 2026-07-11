import { useState, useEffect } from 'react';
import { GitBranch, ArrowUp, ArrowDown, GitCommit } from 'lucide-react';

interface GitFile {
  path: string;
  status: string; // M, A, D, ??
}

export default function GitSidebar() {
  const [branch, setBranch] = useState('main');
  const [files, setFiles] = useState<GitFile[]>([]);
  const [branches, setBranches] = useState<string[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [commitMsg, setCommitMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const loadGitData = async () => {
    setLoading(true);
    try {
      // 1. Status
      const statusRes = await fetch('/api/git/status');
      const statusData = await statusRes.json();
      setBranch(statusData.branch || 'main');
      setFiles(statusData.files || []);

      // 2. Branches
      const branchRes = await fetch('/api/git/branches');
      const branchData = await branchRes.json();
      setBranches(branchData.branches || []);

      // 3. History
      const historyRes = await fetch('/api/git/history');
      const historyData = await historyRes.json();
      setHistory(historyData.history || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGitData();
  }, []);

  const handleStageFile = async (path: string, currentlyStaged: boolean) => {
    try {
      const action = currentlyStaged ? 'unstage' : 'stage';
      const res = await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, path })
      });
      if (res.ok) {
        loadGitData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCommit = async () => {
    if (!commitMsg.trim()) return;
    try {
      const res = await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'commit', message: commitMsg })
      });
      if (res.ok) {
        setCommitMsg('');
        loadGitData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCheckoutBranch = async (targetBranch: string) => {
    try {
      const res = await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'checkout', branch: targetBranch })
      });
      if (res.ok) {
        loadGitData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handlePush = async () => {
    try {
      setLoading(true);
      await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'push' })
      });
    } catch (e) {
      console.error(e);
    } finally {
      loadGitData();
    }
  };

  const handlePull = async () => {
    try {
      setLoading(true);
      await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'pull' })
      });
    } catch (e) {
      console.error(e);
    } finally {
      loadGitData();
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0e1014] text-gray-300 font-sans">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 bg-[#111318] flex items-center justify-between shrink-0 select-none">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Source Control</span>
        <button
          onClick={loadGitData}
          disabled={loading}
          className="text-[10px] text-violet-400 hover:text-violet-300 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {/* Branch selector */}
      <div className="p-3 border-b border-white/5 bg-[#0e1014] flex items-center justify-between gap-2 shrink-0 select-none">
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <GitBranch className="w-3.5 h-3.5 text-violet-400" />
          <span className="font-mono">{branch}</span>
        </div>
        
        {branches.length > 0 && (
          <select
            value={branch}
            onChange={(e) => handleCheckoutBranch(e.target.value)}
            className="bg-[#171922] border border-white/5 rounded text-[10px] px-1 py-0.5 text-white focus:outline-none max-w-[120px]"
          >
            {branches.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        )}
      </div>

      {/* Commit Input Box */}
      <div className="p-3 border-b border-white/5 bg-[#0e1014] space-y-2 shrink-0 select-none">
        <textarea
          value={commitMsg}
          onChange={(e) => setCommitMsg(e.target.value)}
          placeholder="Commit message..."
          className="w-full bg-[#171922] border border-white/5 hover:border-white/10 rounded p-2 text-[10px] text-white focus:outline-none resize-none h-12"
        />
        <div className="flex gap-2">
          <button
            onClick={handleCommit}
            className="flex-1 py-1 bg-violet-650 hover:bg-violet-600 border border-violet-500/20 text-white rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition-all"
          >
            <GitCommit className="w-3.5 h-3.5" /> Commit
          </button>
          <button
            onClick={handlePull}
            className="py-1 px-2.5 bg-white/5 hover:bg-white/10 border border-white/5 rounded text-[10px] font-semibold flex items-center gap-1 text-gray-300"
            title="Pull"
          >
            <ArrowDown className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handlePush}
            className="py-1 px-2.5 bg-white/5 hover:bg-white/10 border border-white/5 rounded text-[10px] font-semibold flex items-center gap-1 text-gray-300"
            title="Push"
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Files Feed */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-4">
        {files.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-650 italic">
            No changes detected
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
              Changes ({files.length})
            </div>
            <div className="space-y-1">
              {files.map((file) => {
                const isStaged = file.status === 'A' || file.status === 'M' || file.status === 'D';
                return (
                  <div key={file.path} className="flex items-center justify-between p-1.5 bg-black/15 hover:bg-white/5 rounded border border-white/5 transition-all">
                    <div className="flex items-center gap-2 min-w-0">
                      <input
                        type="checkbox"
                        checked={isStaged}
                        onChange={() => handleStageFile(file.path, isStaged)}
                        className="accent-violet-650 rounded shrink-0 cursor-pointer w-3 h-3"
                      />
                      <span className="text-[10px] text-gray-250 truncate font-mono" title={file.path}>
                        {file.path.split('/').pop()}
                      </span>
                      <span className="text-[8px] text-gray-500 font-mono truncate max-w-[100px]">
                        ({file.path})
                      </span>
                    </div>
                    <span className={`px-1 py-0.2 rounded text-[8px] font-bold ${
                      file.status === '??' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
                    }`}>
                      {file.status}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* History Log */}
        {history.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-white/5 select-none">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
              Commit History
            </div>
            <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
              {history.map((log, idx) => (
                <div key={idx} className="p-1.5 bg-black/25 rounded border border-white/5 font-mono text-[9px] text-gray-500 truncate" title={log}>
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
