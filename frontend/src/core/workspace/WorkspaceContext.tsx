import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useToast } from '../toast/ToastContext';

interface WorkspaceContextType {
  workspacePath: string;
  refreshTrigger: number;
  fetchWorkspacePath: () => Promise<void>;
  changeWorkspacePath: (path: string) => Promise<boolean>;
  handleOpenWorkspaceFolder: () => Promise<void>;
  triggerRefresh: () => void;
  selectFolder: () => Promise<{ path: string | null; cancelled?: boolean; dialog_unavailable?: boolean }>;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [workspacePath, setWorkspacePath] = useState('');
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { showToast } = useToast();

  const fetchWorkspacePath = async () => {
    try {
      const res = await fetch('/api/workspace');
      if (res.ok) {
        const data = await res.json();
        setWorkspacePath(data.workspace);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const changeWorkspacePath = async (path: string): Promise<boolean> => {
    try {
      const res = await fetch('/api/workspace/change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setWorkspacePath(data.workspace);
        setRefreshTrigger(prev => prev + 1);
        showToast(
          data.workspace ? 'Folder opened: ' + data.workspace : 'Workspace closed.',
          'success'
        );
        return true;
      } else {
        showToast('Failed to open folder: ' + (data.detail || 'Directory does not exist'), 'error');
        return false;
      }
    } catch (err) {
      showToast('Error opening folder: ' + err, 'error');
      return false;
    }
  };

  const selectFolder = async (): Promise<{ path: string | null; cancelled?: boolean; dialog_unavailable?: boolean }> => {
    // 1. Electron — native OS dialog via contextBridge IPC (highest priority)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const electronAPI = (window as any).electronAPI;
    if (electronAPI?.openFolder) {
      try {
        const result = await electronAPI.openFolder();
        // result is { path: string } or { cancelled: true }
        if (result.cancelled) return { path: null, cancelled: true };
        return { path: result.path ?? null };
      } catch (e) {
        console.error('Electron openFolder failed:', e);
      }
    }

    // 2. pywebview (desktop wrapper without Electron)
    // @ts-ignore
    if (window.pywebview?.api?.select_folder) {
      try {
        // @ts-ignore
        const path = await window.pywebview.api.select_folder();
        if (path) return { path };
        return { path: null, cancelled: true };
      } catch (e) {
        console.error('pywebview select_folder failed:', e);
      }
    }

    // 3. Backend tkinter dialog (non-Docker desktop)
    try {
      const res = await fetch('/api/workspace/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        return data;
      }
    } catch (e) {
      console.error('Backend select_folder failed:', e);
    }

    return { path: null, dialog_unavailable: true };
  };

  const handleOpenWorkspaceFolder = async () => {
    const result = await selectFolder();
    if (result.path) {
      await changeWorkspacePath(result.path);
    } else if (result.cancelled) {
      // User cancelled, do nothing
      return;
    } else {
      const path = window.prompt("Native folder dialog is unavailable.\nPlease enter the full directory path to open a project from your laptop:");
      if (path && path.trim()) {
        await changeWorkspacePath(path.trim());
      }
    }
  };

  const triggerRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  useEffect(() => {
    fetchWorkspacePath();
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        workspacePath,
        refreshTrigger,
        fetchWorkspacePath,
        changeWorkspacePath,
        handleOpenWorkspaceFolder,
        triggerRefresh,
        selectFolder
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
};
