import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { useWorkspace } from '../workspace/WorkspaceContext';
import { useToast } from '../toast/ToastContext';

interface ProposedDiff {
  path: string;
  original: string;
  proposed: string;
}

interface EditorContextType {
  openFiles: string[];
  activeFilePath: string | null;
  proposedDiff: ProposedDiff | null;
  setProposedDiff: (diff: ProposedDiff | null) => void;
  handleSelectFile: (path: string) => void;
  handleCloseFile: (path: string) => void;
  handleSaveFile: (path: string, content: string) => Promise<boolean>;
}

const EditorContext = createContext<EditorContextType | undefined>(undefined);

export const EditorProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [openFiles, setOpenFiles] = useState<string[]>([]);
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [proposedDiff, setProposedDiff] = useState<ProposedDiff | null>(null);
  
  const { workspacePath } = useWorkspace();
  const { showToast } = useToast();

  // Reset editor state when workspace root changes
  useEffect(() => {
    setOpenFiles([]);
    setActiveFilePath(null);
    setProposedDiff(null);
  }, [workspacePath]);

  const handleSelectFile = (path: string) => {
    setOpenFiles(prev => {
      if (prev.includes(path)) return prev;
      return [...prev, path];
    });
    setActiveFilePath(path);
  };

  const handleCloseFile = (path: string) => {
    setOpenFiles(prev => {
      const filtered = prev.filter(f => f !== path);
      if (activeFilePath === path) {
        setActiveFilePath(filtered.length > 0 ? filtered[filtered.length - 1] : null);
      }
      return filtered;
    });
  };

  const handleSaveFile = async (path: string, content: string): Promise<boolean> => {
    try {
      const res = await fetch('/api/files/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`Saved ${path.split('/').pop()} successfully`, 'success');
        return true;
      } else {
        showToast(`Failed to save file: ${data.detail || 'unknown error'}`, 'error');
        return false;
      }
    } catch (err) {
      showToast(`Error saving file: ${err}`, 'error');
      return false;
    }
  };

  return (
    <EditorContext.Provider
      value={{
        openFiles,
        activeFilePath,
        proposedDiff,
        setProposedDiff,
        handleSelectFile,
        handleCloseFile,
        handleSaveFile
      }}
    >
      {children}
    </EditorContext.Provider>
  );
};

export const useEditor = () => {
  const context = useContext(EditorContext);
  if (!context) {
    throw new Error('useEditor must be used within an EditorProvider');
  }
  return context;
};
