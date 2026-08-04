import React, { useState, useEffect, useCallback } from 'react';
import { Plus, FolderPlus, FolderOpen } from 'lucide-react';
import { listFiles, createFile, deleteFile, getWorkspaceStats } from '../api';
import type { FileItem, SidebarProps, WorkspaceStatsData } from './Sidebar/types';
import { SearchBar } from './Sidebar/SearchBar';
import { FileCreationDialog } from './Sidebar/FileCreationDialog';
import { FileContextMenu } from './Sidebar/FileContextMenu';
import { WorkspaceStats } from './Sidebar/WorkspaceStats';
import { FileTree } from './Sidebar/FileTree';
import { useDebounce } from '../hooks/useDebounce';

export default function Sidebar({
  onSelectFile,
  selectedFilePath,
  refreshTrigger,
  workspacePath,
  onOpenFolder,
  gitChanges,
}: SidebarProps) {
  const [rootItems, setRootItems] = useState<FileItem[]>([]);
  const [dirContents, setDirContents] = useState<Record<string, FileItem[]>>({});
  const [expandedPaths, setExpandedPaths] = useState<Record<string, boolean>>({});
  const [loadingDir, setLoadingDir] = useState<string | null>(null);

  // Search & Filters
  const [searchTerm, setSearchTerm] = useState<string>('');
  const debouncedSearchTerm = useDebounce(searchTerm, 300);
  const [showHidden, setShowHidden] = useState(false);

  // Creation State
  const [creatingType, setCreatingType] = useState<'file' | 'folder' | null>(null);
  const [creatingInPath, setCreatingInPath] = useState<string>('');
  const [newItemName, setNewItemName] = useState<string>('');

  // Rename State
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState<string>('');

  // Selection State for Multi-Select
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);

  // Context Menu State
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; item: FileItem } | null>(null);

  // Drag & Drop State
  const [dragItem, setDragItem] = useState<FileItem | null>(null);

  // Stats State
  const [stats, setStats] = useState<WorkspaceStatsData | null>(null);
  const [isStatsExpanded, setIsStatsExpanded] = useState(false);

  const refreshRoot = useCallback(async () => {
    if (!workspacePath) return;
    setLoadingDir('');
    try {
      const items = await listFiles('');
      setRootItems(items || []);
      setDirContents({});
      setExpandedPaths({});
    } catch (err) {
      console.error('Failed to list root files', err);
    } finally {
      setLoadingDir(null);
    }
  }, [workspacePath]);

  useEffect(() => {
    refreshRoot();
  }, [workspacePath, refreshTrigger, refreshRoot]);

  useEffect(() => {
    (async () => {
      try {
        const s = await getWorkspaceStats();
        setStats(s);
      } catch {
        // ignore stats errors
      }
    })();
  }, [workspacePath, refreshTrigger]);

  // Update selectedPaths when selectedFilePath changes from external sources (like editor tabs)
  useEffect(() => {
    if (selectedFilePath) {
      setSelectedPaths(prev => {
        if (prev.includes(selectedFilePath) && prev.length === 1) return prev;
        return [selectedFilePath];
      });
    } else {
      setSelectedPaths([]);
    }
  }, [selectedFilePath]);

  const loadDirectory = async (path: string) => {
    if (dirContents[path]) return;
    setLoadingDir(path);
    try {
      const items = await listFiles(path);
      setDirContents(prev => ({ ...prev, [path]: items || [] }));
    } catch (err) {
      console.error(`Failed to list dir: ${path}`, err);
    } finally {
      setLoadingDir(null);
    }
  };

  const toggleExpand = (path: string) => {
    setExpandedPaths(prev => {
      const nextState = !prev[path];
      if (nextState) {
        loadDirectory(path);
      }
      return { ...prev, [path]: nextState };
    });
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim() || !creatingType) return;
    const fullPath = creatingInPath
      ? `${creatingInPath}/${newItemName.trim()}`
      : newItemName.trim();

    try {
      await createFile(fullPath, creatingType === 'folder');
      setCreatingType(null);
      setNewItemName('');

      if (creatingInPath) {
        const items = await listFiles(creatingInPath);
        setDirContents(prev => ({ ...prev, [creatingInPath]: items || [] }));
      } else {
        refreshRoot();
      }
    } catch (err) {
      console.error('Failed to create file/folder', err);
    }
  };

  const handleRenameSubmit = async (e: React.FormEvent, item: FileItem) => {
    e.preventDefault();
    if (!renameValue.trim() || renameValue === item.name) {
      setRenamingPath(null);
      return;
    }
    const parentDir = item.path.includes('/') ? item.path.split('/').slice(0, -1).join('/') : '';
    const newPath = parentDir ? `${parentDir}/${renameValue.trim()}` : renameValue.trim();

    try {
      await createFile(newPath, item.is_dir);
      await deleteFile(item.path);
      setRenamingPath(null);
      refreshRoot();
    } catch (err) {
      console.error('Failed to rename file', err);
    }
  };

  const handleSelectFileClick = (path: string, isCtrlKey: boolean) => {
    if (isCtrlKey) {
      setSelectedPaths(prev => {
        if (prev.includes(path)) {
          return prev.filter(p => p !== path);
        } else {
          return [...prev, path];
        }
      });
    } else {
      setSelectedPaths([path]);
      onSelectFile(path);
    }
  };

  const handleDeleteItem = async (item: FileItem) => {
    const itemsToDelete = selectedPaths.includes(item.path) && selectedPaths.length > 1
      ? selectedPaths
      : [item.path];

    const names = itemsToDelete.map(p => p.split('/').pop()).join(', ');
    const msg = itemsToDelete.length > 1
      ? `Are you sure you want to delete these ${itemsToDelete.length} items?\n${names}`
      : `Are you sure you want to delete ${item.name}?`;

    if (!window.confirm(msg)) return;

    try {
      for (const path of itemsToDelete) {
        await deleteFile(path);
      }
      setSelectedPaths([]);
      refreshRoot();
    } catch (err) {
      console.error('Failed to delete file(s)', err);
    }
  };

  const handleDrop = async (e: React.DragEvent, targetItem: FileItem) => {
    e.preventDefault();
    if (!dragItem || dragItem.path === targetItem.path) return;

    const targetDir = targetItem.is_dir
      ? targetItem.path
      : targetItem.path.split('/').slice(0, -1).join('/');

    const newPath = targetDir ? `${targetDir}/${dragItem.name}` : dragItem.name;

    try {
      await createFile(newPath, dragItem.is_dir);
      await deleteFile(dragItem.path);
      setDragItem(null);
      refreshRoot();
    } catch (err) {
      console.error('Failed to move file', err);
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#151823] border-r border-[#2a3142] select-none">
      {/* Header Bar */}
      <div className="p-3 border-b border-[#2a3142] bg-[#0f111a] shrink-0">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            EXPLORER
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                setCreatingInPath('');
                setCreatingType('file');
              }}
              title="New File"
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => {
                setCreatingInPath('');
                setCreatingType('folder');
              }}
              title="New Folder"
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
            >
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={onOpenFolder}
              title="Open Workspace Folder"
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-white/5 transition-colors cursor-pointer"
            >
              <FolderOpen className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <SearchBar
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          showHidden={showHidden}
          setShowHidden={setShowHidden}
        />
      </div>

      {/* Inline Creation Dialog */}
      <FileCreationDialog
        creatingType={creatingType}
        creatingInPath={creatingInPath}
        newItemName={newItemName}
        setNewItemName={setNewItemName}
        onSubmit={handleCreateSubmit}
        onCancel={() => setCreatingType(null)}
      />

      {/* Main File Tree Area */}
      <div className="flex-1 overflow-y-auto py-1">
        {rootItems.length === 0 ? (
          <div className="p-4 text-center text-xs text-gray-500 italic">
            No workspace files found.
          </div>
        ) : (
          <FileTree
            items={rootItems}
            dirContents={dirContents}
            expandedPaths={expandedPaths}
            selectedFilePath={selectedFilePath}
            selectedPaths={selectedPaths}
            loadingDir={loadingDir}
            renamingPath={renamingPath}
            renameValue={renameValue}
            gitChanges={gitChanges}
            searchTerm={debouncedSearchTerm}
            showHidden={showHidden}
            onToggleExpand={toggleExpand}
            onSelectFile={handleSelectFileClick}
            onContextMenu={(e, item) => {
              e.preventDefault();
              // If the item is not already selected, select only it
              if (!selectedPaths.includes(item.path)) {
                setSelectedPaths([item.path]);
              }
              setContextMenu({ x: e.clientX, y: e.clientY, item });
            }}
            onRenameSubmit={handleRenameSubmit}
            setRenameValue={setRenameValue}
            setRenamingPath={setRenamingPath}
            onDragStart={setDragItem}
            onDragOver={e => e.preventDefault()}
            onDrop={handleDrop}
          />
        )}
      </div>

      {/* Right-click Context Menu */}
      <FileContextMenu
        contextMenu={contextMenu}
        onClose={() => setContextMenu(null)}
        onStartCreateInFolder={(dir, type) => {
          setCreatingInPath(dir);
          setCreatingType(type);
          setContextMenu(null);
        }}
        onStartRename={item => {
          setRenamingPath(item.path);
          setRenameValue(item.name);
          setContextMenu(null);
        }}
        onDelete={item => {
          handleDeleteItem(item);
          setContextMenu(null);
        }}
        selectedCount={selectedPaths.includes(contextMenu?.item.path || '') ? selectedPaths.length : 1}
      />

      {/* Footer Workspace Stats Drawer */}
      <WorkspaceStats
        stats={stats}
        isExpanded={isStatsExpanded}
        setIsExpanded={setIsStatsExpanded}
      />
    </div>
  );
}
