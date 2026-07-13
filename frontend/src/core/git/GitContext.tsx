import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useWorkspace } from '../workspace/WorkspaceContext';
import { useTerminal } from '../terminal/TerminalContext';
import { useToast } from '../toast/ToastContext';

interface GitContextType {
  gitChanges: Record<string, string>;
  gitChangesList: any[];
  statusBarBranch: string;
  statusBarDebug: string;
  setStatusBarDebug: (status: string) => void;
  updateStatusBarInfo: () => Promise<void>;
  handleGitAction: (action: 'stage' | 'unstage' | 'commit' | 'push' | 'pull' | 'checkout' | 'discard_file' | 'discard_all' | 'accept_file' | 'accept_all', path?: string, message?: string, branch?: string) => Promise<boolean>;
}

const GitContext = createContext<GitContextType | undefined>(undefined);

export const GitProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [gitChanges, setGitChanges] = useState<Record<string, string>>({});
  const [gitChangesList, setGitChangesList] = useState<any[]>([]);
  const [statusBarBranch, setStatusBarBranch] = useState('Not a Git Repo');
  const [statusBarDebug, setStatusBarDebug] = useState('Idle');

  const { workspacePath, triggerRefresh } = useWorkspace();
  const { setConsoleLogs } = useTerminal();
  const { showToast } = useToast();

  const updateStatusBarInfo = async () => {
    if (!workspacePath) {
      setStatusBarBranch('No workspace open');
      setGitChanges({});
      setGitChangesList([]);
      return;
    }
    try {
      const gitRes = await fetch('/api/git/status');
      if (gitRes.ok) {
        const gitData = await gitRes.json();
        setStatusBarBranch(gitData.branch || 'Not a Git Repo');
        const mapping: Record<string, string> = {};
        if (gitData.files) {
          gitData.files.forEach((f: any) => {
            mapping[f.path] = f.status;
          });
        }
        setGitChanges(mapping);
      }

      const changesRes = await fetch('/api/git/changes');
      if (changesRes.ok) {
        const changesData = await changesRes.json();
        setGitChangesList(changesData.files || []);
      }

      const debugRes = await fetch('/api/debug/status');
      if (debugRes.ok) {
        const debugData = await debugRes.json();
        setStatusBarDebug(debugData.running ? 'Running' : 'Idle');
      }

      const logsRes = await fetch('/api/debug/logs');
      if (logsRes.ok) {
        const logsData = await logsRes.json();
        setConsoleLogs(logsData.logs || []);
      }
    } catch (e) {
      // ignore
    }
  };

  const handleGitAction = async (
    action: 'stage' | 'unstage' | 'commit' | 'push' | 'pull' | 'checkout' | 'discard_file' | 'discard_all' | 'accept_file' | 'accept_all',
    path?: string,
    message?: string,
    branch?: string
  ): Promise<boolean> => {
    try {
      const res = await fetch('/api/git/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, path, message, branch })
      });
      if (res.ok) {
        showToast(
          action === 'accept_all'
            ? 'Accepted all changes!'
            : action === 'discard_all'
            ? 'Discarded all changes!'
            : action === 'accept_file'
            ? `Staged ${path?.split('/').pop()}`
            : action === 'discard_file'
            ? `Discarded ${path?.split('/').pop()}`
            : `Git ${action} succeeded`,
          action.startsWith('discard') ? 'info' : 'success'
        );
        await updateStatusBarInfo();
        triggerRefresh();
        return true;
      } else {
        const data = await res.json();
        showToast(data.detail || 'Git action failed', 'error');
        return false;
      }
    } catch (e) {
      console.error('Failed to perform git action:', e);
      showToast('Connection error during git action', 'error');
      return false;
    }
  };

  useEffect(() => {
    updateStatusBarInfo();
    const timer = setInterval(updateStatusBarInfo, 4000);
    return () => clearInterval(timer);
  }, [workspacePath]);

  return (
    <GitContext.Provider
      value={{
        gitChanges,
        gitChangesList,
        statusBarBranch,
        statusBarDebug,
        setStatusBarDebug,
        updateStatusBarInfo,
        handleGitAction
      }}
    >
      {children}
    </GitContext.Provider>
  );
};

export const useGit = () => {
  const context = useContext(GitContext);
  if (!context) {
    throw new Error('useGit must be used within a GitProvider');
  }
  return context;
};
