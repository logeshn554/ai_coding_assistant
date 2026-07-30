import React from 'react';

interface FileCreationDialogProps {
  creatingType: 'file' | 'folder' | null;
  creatingInPath: string;
  newItemName: string;
  setNewItemName: (name: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
}

export const FileCreationDialog: React.FC<FileCreationDialogProps> = ({
  creatingType,
  creatingInPath,
  newItemName,
  setNewItemName,
  onSubmit,
  onCancel,
}) => {
  if (!creatingType) return null;

  return (
    <form onSubmit={onSubmit} className="p-2 border-b border-[#2a3142] bg-[#1e2330]">
      <div className="text-[10px] font-semibold text-[#4C8DFF] uppercase mb-1">
        New {creatingType} {creatingInPath ? `in ${creatingInPath}` : 'in Root'}
      </div>
      <div className="flex gap-1">
        <input
          type="text"
          value={newItemName}
          onChange={e => setNewItemName(e.target.value)}
          placeholder={creatingType === 'file' ? 'filename.ts' : 'folder-name'}
          autoFocus
          className="flex-1 bg-[#151823] text-white text-[11px] px-2 py-1 rounded border border-[#4C8DFF] focus:outline-none"
        />
        <button
          type="submit"
          disabled={!newItemName.trim()}
          className="px-2 py-1 bg-[#4C8DFF] hover:bg-[#9176FF] disabled:opacity-40 text-white text-[10px] font-semibold rounded cursor-pointer transition-colors"
        >
          Create
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-2 py-1 bg-white/5 hover:bg-white/10 text-gray-300 text-[10px] rounded cursor-pointer transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
};
