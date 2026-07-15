import React from 'react';
import { useWorkspace } from '../core/workspace/WorkspaceContext';

export const OpenFolderModal: React.FC = () => {
  const {
    isOpenFolderModalOpen,
    setIsOpenFolderModalOpen,
    folderPathInput,
    setFolderPathInput,
    changeWorkspacePath,
    selectFolder
  } = useWorkspace();

  if (!isOpenFolderModalOpen) return null;

  const handleBrowseFolderClick = async () => {
    const selected = await selectFolder();
    if (selected) {
      setFolderPathInput(selected);
    }
  };

  const handleOpenFolderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderPathInput.trim()) return;
    await changeWorkspacePath(folderPathInput.trim());
    setIsOpenFolderModalOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <form
        onSubmit={handleOpenFolderSubmit}
        className="w-[450px] bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] rounded-none shadow-2xl p-5"
      >
        <h3 className="text-xs font-semibold text-white mb-2 font-sans">Open Workspace Folder</h3>
        <p className="text-[10px] text-gray-500 mb-4 font-sans">
          Enter or browse the absolute folder path on your computer. DevPilot will load its file tree and run commands inside it.
        </p>
        <div className="flex gap-2 mb-4">
          <input
            autoFocus
            type="text"
            value={folderPathInput}
            onChange={(e) => setFolderPathInput(e.target.value)}
            className="flex-1 px-3 py-2 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-none text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]/50 font-mono"
            placeholder="e.g. E:/my-project"
          />
          <button
            type="button"
            onClick={handleBrowseFolderClick}
            className="px-3 py-2 bg-[var(--dp-bg-tertiary)] hover:bg-[var(--dp-bg-hover)] text-white text-xs font-medium rounded-none border border-[var(--dp-border)] hover:border-[var(--dp-accent)]/50 transition-colors cursor-pointer"
          >
            Browse...
          </button>
        </div>
        <div className="flex justify-end gap-2 text-xs font-sans">
          <button
            type="button"
            onClick={() => setIsOpenFolderModalOpen(false)}
            className="px-4 py-2 bg-transparent text-gray-400 hover:text-white transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-4 py-2 bg-[var(--dp-accent)] hover:bg-[var(--dp-accent-hover)] text-white rounded-none transition-colors font-medium cursor-pointer"
          >
            Open Folder
          </button>
        </div>
      </form>
    </div>
  );
};
