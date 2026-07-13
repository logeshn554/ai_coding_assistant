import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useToast } from '../toast/ToastContext';

interface WorkspaceContextType {
  workspacePath: string;
  folderPathInput: string;
  isOpenFolderModalOpen: boolean;
  refreshTrigger: number;
  setFolderPathInput: (path: string) => void;
  setIsOpenFolderModalOpen: (open: boolean) => void;
  fetchWorkspacePath: () => Promise<void>;
  changeWorkspacePath: (path: string) => Promise<boolean>;
  handleOpenWorkspaceFolder: () => Promise<void>;
  triggerRefresh: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [workspacePath, setWorkspacePath] = useState('');
  const [folderPathInput, setFolderPathInput] = useState('');
  const [isOpenFolderModalOpen, setIsOpenFolderModalOpen] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const { showToast } = useToast();

  const fetchWorkspacePath = async () => {
    try {
      const res = await fetch('/api/workspace');
      if (res.ok) {
        const data = await res.json();
        setWorkspacePath(data.workspace);
        setFolderPathInput(data.workspace);
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
        setFolderPathInput(data.workspace);
        setRefreshTrigger(prev => prev + 1);
        setIsOpenFolderModalOpen(false);
        showToast(
          data.workspace ? 'Workspace folder opened successfully!' : 'Workspace folder closed.',
          'success'
        );
        return true;
      } else {
        showToast('Failed to open folder: ' + data.detail, 'error');
        return false;
      }
    } catch (err) {
      showToast('Error opening folder: ' + err, 'error');
      return false;
    }
  };

  const handleOpenWorkspaceFolder = async () => {
    const win = window as any;
    if (win.pywebview && win.pywebview.api && typeof win.pywebview.api.select_folder === 'function') {
      try {
        const selected = await win.pywebview.api.select_folder();
        if (selected) {
          await changeWorkspacePath(selected);
        }
      } catch (err) {
        showToast('Native folder selector error: ' + err, 'error');
      }
    } else {
      setIsOpenFolderModalOpen(true);
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
        folderPathInput,
        isOpenFolderModalOpen,
        refreshTrigger,
        setFolderPathInput,
        setIsOpenFolderModalOpen,
        fetchWorkspacePath,
        changeWorkspacePath,
        handleOpenWorkspaceFolder,
        triggerRefresh
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
