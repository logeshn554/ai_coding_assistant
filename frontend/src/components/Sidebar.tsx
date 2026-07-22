import React, { useState, useEffect, useCallback } from 'react';
import {
  Folder, FolderOpen, File as FileIcon, Plus, FolderPlus, Trash2,
  ChevronRight, ChevronDown, Terminal, ChevronsDownUp, ChevronsUpDown,
  Eye, EyeOff, Copy, Clipboard, Pencil
} from 'lucide-react';
import { listFiles, createFile, deleteFile, getWorkspaceStats } from '../api';
import { LoadingSpinner } from './LoadingSpinner';
import { ContextMenu } from './ContextMenu';
import type { ContextMenuEntry } from './ContextMenu';
import { useTerminal } from '../core/terminal/TerminalContext';

interface FileItem {
  name: string;
  path: string;
  is_dir: boolean;
  size?: number;
}

interface SidebarProps {
  onSelectFile: (path: string) => void;
  selectedFilePath: string | null;
  refreshTrigger: number;
  workspacePath: string;
  onOpenFolder: () => void;
  gitChanges?: Record<string, string>;
}

// ── File Icon System ──
const FILE_ICON_MAP: Record<string, { color: string; label: string }> = {
  py: { color: '#3572A5', label: '🐍' },
  ts: { color: '#3178C6', label: 'TS' },
  tsx: { color: '#3178C6', label: 'TX' },
  js: { color: '#F7DF1E', label: 'JS' },
  jsx: { color: '#F7DF1E', label: 'JX' },
  json: { color: '#cbcb41', label: '{}' },
  html: { color: '#E34F26', label: '<>' },
  css: { color: '#563d7c', label: '#' },
  scss: { color: '#c6538c', label: 'S#' },
  md: { color: '#519aba', label: 'M↓' },
  yml: { color: '#cb171e', label: 'YM' },
  yaml: { color: '#cb171e', label: 'YM' },
  toml: { color: '#9c4121', label: 'TL' },
  sh: { color: '#89e051', label: '$_' },
  bat: { color: '#C1F12E', label: '⌘' },
  sql: { color: '#e38c00', label: 'SQ' },
  graphql: { color: '#e10098', label: 'GQ' },
  env: { color: '#ECD53F', label: '.E' },
  gitignore: { color: '#F54D27', label: '.G' },
  dockerfile: { color: '#2496ED', label: '🐳' },
  rs: { color: '#DEA584', label: 'Rs' },
  go: { color: '#00ADD8', label: 'Go' },
  java: { color: '#b07219', label: 'Jv' },
  c: { color: '#555555', label: 'C' },
  cpp: { color: '#f34b7d', label: 'C+' },
  h: { color: '#555555', label: '.H' },
  rb: { color: '#CC342D', label: 'Rb' },
  php: { color: '#4F5D95', label: 'P?' },
  svg: { color: '#ff9900', label: '◇' },
  png: { color: '#a074c4', label: '🖼' },
  jpg: { color: '#a074c4', label: '🖼' },
  gif: { color: '#a074c4', label: '🖼' },
  ico: { color: '#a074c4', label: '▣' },
  woff: { color: '#aaaaaa', label: 'Fn' },
  woff2: { color: '#aaaaaa', label: 'Fn' },
  lock: { color: '#776e6e', label: '🔒' },
  txt: { color: '#89898b', label: 'Tx' },
  log: { color: '#776e6e', label: '📋' },
  xml: { color: '#f36e1f', label: 'XM' },
  zip: { color: '#afb42b', label: '📦' },
  gz: { color: '#afb42b', label: '📦' },
  tar: { color: '#afb42b', label: '📦' },
  map: { color: '#776e6e', label: '.M' },
};

const HIDDEN_PATTERNS = [
  'node_modules', '__pycache__', '.git', '.venv', 'venv', '.mypy_cache',
  '.pytest_cache', '.next', 'dist', '.DS_Store', 'thumbs.db',
  '.env.local', '.vercel', '.turbo', '.cache'
];

/** Get a styled icon element for a filename */
function getFileIconElement(name: string, isDir: boolean, isExpanded: boolean) {
  if (isDir) {
    return isExpanded
      ? <FolderOpen className="w-4 h-4 text-yellow-500/90 shrink-0" />
      : <Folder className="w-4 h-4 text-yellow-500/80 shrink-0" />;
  }

  const lower = name.toLowerCase();
  // Special filenames
  if (lower === 'dockerfile' || lower.startsWith('dockerfile.')) {
    const m = FILE_ICON_MAP['dockerfile'];
    return <span className="w-4 h-4 flex items-center justify-center text-[9px] font-bold shrink-0 rounded-sm" style={{ color: m.color }}>{m.label}</span>;
  }
  if (lower === '.gitignore') {
    const m = FILE_ICON_MAP['gitignore'];
    return <span className="w-4 h-4 flex items-center justify-center text-[9px] font-bold shrink-0 rounded-sm" style={{ color: m.color }}>{m.label}</span>;
  }
  if (lower === '.env' || lower.startsWith('.env.')) {
    const m = FILE_ICON_MAP['env'];
    return <span className="w-4 h-4 flex items-center justify-center text-[9px] font-bold shrink-0 rounded-sm" style={{ color: m.color }}>{m.label}</span>;
  }

  const ext = name.split('.').pop()?.toLowerCase() || '';
  const mapping = FILE_ICON_MAP[ext];
  if (mapping) {
    return <span className="w-4 h-4 flex items-center justify-center text-[9px] font-bold shrink-0 rounded-sm" style={{ color: mapping.color }}>{mapping.label}</span>;
  }

  // Fallback
  return <FileIcon className="w-3.5 h-3.5 text-gray-400 shrink-0" />;
}

/** Git status badge */
function GitBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; cls: string }> = {
    M: { label: 'M', cls: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20' },
    A: { label: 'A', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
    D: { label: 'D', cls: 'bg-red-500/15 text-red-400 border-red-500/20' },
    '??': { label: 'U', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/20' },
    R: { label: 'R', cls: 'bg-purple-500/15 text-purple-400 border-purple-500/20' },
  };
  const c = config[status] || config['??'];
  return (
    <span className={`text-[8px] font-bold px-1 py-px rounded border leading-none shrink-0 font-mono ${c.cls}`}>
      {c.label}
    </span>
  );
}

export default function Sidebar({ onSelectFile, selectedFilePath, refreshTrigger, workspacePath, onOpenFolder, gitChanges }: SidebarProps) {
  const { setBottomTab, setActiveTerminalCommand } = useTerminal();
  const [rootItems, setRootItems] = useState<FileItem[]>([]);
  const [dirContents, setDirContents] = useState<Record<string, FileItem[]>>({});
  const [expandedPaths, setExpandedPaths] = useState<Record<string, boolean>>({});
  const [loadingDir, setLoadingDir] = useState<string | null>(null);
  const [creatingType, setCreatingType] = useState<'file' | 'folder' | null>(null);
  const [creatingInPath, setCreatingInPath] = useState<string>('');
  const [newItemName, setNewItemName] = useState<string>('');
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [showHidden, setShowHidden] = useState(false);
  const [stats, setStats] = useState<null | {
    total_files: number;
    total_lines: number;
    languages: Record<string, number>;
    git_commits: number;
  }>(null);
  const [isStatsExpanded, setIsStatsExpanded] = useState(false);

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    item: FileItem;
  } | null>(null);

  // Drag & drop state
  const [dragItem, setDragItem] = useState<FileItem | null>(null);
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);

  useEffect(() => {
    refreshRoot();
  }, [workspacePath, refreshTrigger]);

  useEffect(() => {
    (async () => {
      try {
        const s = await getWorkspaceStats();
        setStats(s);
      } catch {
        // ignore
      }
    })();
  }, [workspacePath, refreshTrigger]);

  const refreshRoot = async () => {
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
  };

  const loadDirectory = async (path: string) => {
    if (dirContents[path]) return;
    setLoadingDir(path);
    try {
      const items = await listFiles(path);
      setDirContents(prev => ({ ...prev, [path]: items || [] }));
    } catch (err) {
      console.error('Failed to load directory', path, err);
    } finally {
      setLoadingDir(null);
    }
  };

  const handleToggleFolder = async (path: string) => {
    const isExpanded = !!expandedPaths[path];
    if (isExpanded) {
      setExpandedPaths(prev => ({ ...prev, [path]: false }));
      return;
    }
    await loadDirectory(path);
    setExpandedPaths(prev => ({ ...prev, [path]: true }));
  };

  const handleCreateItem = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!newItemName.trim()) return setCreatingType(null);
    const fullPath = creatingInPath ? `${creatingInPath}/${newItemName}` : newItemName;
    try {
      await createFile(fullPath, creatingType === 'folder');
      setNewItemName('');
      setCreatingType(null);
      if (!creatingInPath) {
        await refreshRoot();
      } else {
        // Force re-fetch by removing cached contents
        setDirContents(prev => {
          const next = { ...prev };
          delete next[creatingInPath];
          return next;
        });
        await loadDirectory(creatingInPath);
        setExpandedPaths(prev => ({ ...prev, [creatingInPath]: true }));
      }
    } catch (err) {
      console.error('Failed to create item', err);
    }
  };

  const handleDeleteItem = async (path: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (!confirm(`Delete ${path}?`)) return;
    try {
      await deleteFile(path);
      const parent = path.includes('/') ? path.split('/').slice(0, -1).join('/') : '';
      if (!parent) await refreshRoot();
      else {
        setDirContents(prev => ({ ...prev, [parent]: (prev[parent] || []).filter(i => i.path !== path) }));
      }
    } catch (err) {
      console.error('Failed to delete', err);
    }
  };

  const handleRename = async (oldPath: string, newName: string) => {
    if (!newName.trim()) { setRenamingPath(null); return; }
    const parent = oldPath.includes('/') ? oldPath.split('/').slice(0, -1).join('/') : '';
    const newPath = parent ? `${parent}/${newName}` : newName;
    try {
      const res = await fetch('/api/files/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_path: oldPath, new_path: newPath })
      });
      if (res.ok) {
        setRenamingPath(null);
        setRenameValue('');
        if (!parent) await refreshRoot();
        else {
          setDirContents(prev => { const next = { ...prev }; delete next[parent]; return next; });
          await loadDirectory(parent);
        }
      } else {
        alert('Rename failed');
      }
    } catch (err) {
      console.error('Rename error', err);
      alert('Rename failed');
    }
  };

  // ── Collapse / Expand All ──
  const collapseAll = () => setExpandedPaths({});
  const expandAll = async () => {
    const expandRecursive = async (items: FileItem[]) => {
      for (const item of items) {
        if (item.is_dir) {
          setExpandedPaths(prev => ({ ...prev, [item.path]: true }));
          if (!dirContents[item.path]) {
            await loadDirectory(item.path);
          }
        }
      }
    };
    await expandRecursive(rootItems);
  };

  // ── Copy path to clipboard ──
  const copyPath = (path: string, relative = true) => {
    const fullPath = relative ? path : `${workspacePath}/${path}`;
    navigator.clipboard.writeText(fullPath.replace(/\//g, '\\'));
  };

  // ── Context Menu Builder ──
  const buildContextMenu = (item: FileItem): ContextMenuEntry[] => {
    const entries: ContextMenuEntry[] = [];

    if (item.is_dir) {
      entries.push(
        { label: 'New File', icon: <Plus className="w-3.5 h-3.5" />, onClick: () => { setCreatingInPath(item.path); setCreatingType('file'); } },
        { label: 'New Folder', icon: <FolderPlus className="w-3.5 h-3.5" />, onClick: () => { setCreatingInPath(item.path); setCreatingType('folder'); } },
        { type: 'divider' as const },
      );
    }

    entries.push(
      { label: 'Rename', icon: <Pencil className="w-3.5 h-3.5" />, shortcut: 'F2', onClick: () => { setRenamingPath(item.path); setRenameValue(item.name); } },
      { label: 'Copy Path', icon: <Copy className="w-3.5 h-3.5" />, onClick: () => copyPath(item.path, false) },
      { label: 'Copy Relative Path', icon: <Clipboard className="w-3.5 h-3.5" />, onClick: () => copyPath(item.path, true) },
    );

    if (item.is_dir) {
      entries.push(
        { type: 'divider' as const },
        { label: 'Reveal in Terminal', icon: <Terminal className="w-3.5 h-3.5" />, onClick: () => {
          // Navigate terminal to the directory containing this file/folder
          const dir = item.is_dir
            ? item.path
            : item.path.includes('/') || item.path.includes('\\')
              ? item.path.substring(0, Math.max(item.path.lastIndexOf('/'), item.path.lastIndexOf('\\')))
              : '';
          setBottomTab('terminal');
          if (dir) setActiveTerminalCommand(`cd "${dir}"`);
        } },
      );
    }

    entries.push(
      { type: 'divider' as const },
      { label: 'Delete', icon: <Trash2 className="w-3.5 h-3.5" />, destructive: true, onClick: () => handleDeleteItem(item.path) },
    );

    return entries;
  };

  // ── Drag & Drop Handlers ──
  const handleDragStart = (e: React.DragEvent, item: FileItem) => {
    e.dataTransfer.setData('text/plain', item.path);
    setDragItem(item);
  };

  const handleDragOver = (e: React.DragEvent, targetItem: FileItem) => {
    if (!targetItem.is_dir) return;
    e.preventDefault();
    e.stopPropagation();
    setDragOverPath(targetItem.path);
  };

  const handleDragLeave = () => setDragOverPath(null);

  const handleDrop = async (e: React.DragEvent, targetDir: FileItem) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOverPath(null);

    if (!dragItem || !targetDir.is_dir) return;
    if (dragItem.path === targetDir.path) return;
    // Don't allow dropping into itself
    if (targetDir.path.startsWith(dragItem.path + '/')) return;

    const newPath = `${targetDir.path}/${dragItem.name}`;
    try {
      const res = await fetch('/api/files/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_path: dragItem.path, new_path: newPath })
      });
      if (res.ok) {
        // Refresh both source and target directories
        const sourceParent = dragItem.path.includes('/') ? dragItem.path.split('/').slice(0, -1).join('/') : '';
        setDirContents(prev => {
          const next = { ...prev };
          delete next[sourceParent || '__root__'];
          delete next[targetDir.path];
          return next;
        });
        if (!sourceParent) await refreshRoot();
        else await loadDirectory(sourceParent);
        await loadDirectory(targetDir.path);
      }
    } catch (err) {
      console.error('Move failed', err);
    }
    setDragItem(null);
  };

  const handleDragEnd = () => { setDragItem(null); setDragOverPath(null); };

  // ── Filter hidden files ──
  const filterItems = useCallback((items: FileItem[]) => {
    let filtered = items;
    if (!showHidden) {
      filtered = filtered.filter(item => !HIDDEN_PATTERNS.some(p => item.name === p || item.name.startsWith('.')));
    }
    if (searchTerm) {
      filtered = filtered.filter(item => item.name.toLowerCase().includes(searchTerm.toLowerCase()));
    }
    // Sort: directories first, then alphabetical
    return filtered.sort((a, b) => {
      if (a.is_dir && !b.is_dir) return -1;
      if (!a.is_dir && b.is_dir) return 1;
      return a.name.localeCompare(b.name);
    });
  }, [showHidden, searchTerm]);

  // ── Breadcrumb for selected file ──
  const renderBreadcrumb = () => {
    if (!selectedFilePath) return null;
    const parts = selectedFilePath.split('/');
    return (
      <div className="dp-breadcrumb border-b border-[#2d2d2d] bg-[#1a1a1a]">
        {parts.map((part, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="dp-breadcrumb-separator">›</span>}
            <span
              className={`dp-breadcrumb-item ${i === parts.length - 1 ? 'text-white font-medium' : ''}`}
              onClick={() => {
                if (i < parts.length - 1) {
                  const dirPath = parts.slice(0, i + 1).join('/');
                  handleToggleFolder(dirPath);
                }
              }}
            >
              {i < parts.length - 1 && <Folder className="w-3 h-3 text-yellow-500/70" />}
              {part}
            </span>
          </React.Fragment>
        ))}
      </div>
    );
  };

  // ── Tree Renderer ──
  const renderTree = (items: FileItem[], depth = 0) => (
    <div className="flex flex-col">
      {filterItems(items).map(item => {
        const isExpanded = !!expandedPaths[item.path];
        const isSelected = selectedFilePath === item.path;
        const gitStatus = gitChanges ? gitChanges[item.path] : undefined;
        const isDragTarget = dragOverPath === item.path;
        const isBeingRenamed = renamingPath === item.path;

        return (
          <div key={item.path} className="flex flex-col">
            {/* File / Folder Row */}
            <div
              draggable
              onDragStart={(e) => handleDragStart(e, item)}
              onDragOver={(e) => handleDragOver(e, item)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, item)}
              onDragEnd={handleDragEnd}
              onClick={() => (item.is_dir ? handleToggleFolder(item.path) : onSelectFile(item.path))}
              onContextMenu={(e) => { e.preventDefault(); setContextMenu({ x: e.clientX, y: e.clientY, item }); }}
              style={{ paddingLeft: `${depth * 14 + 8}px` }}
              className={`group flex items-center justify-between py-[3px] pr-2 cursor-pointer transition-colors duration-75 border-l-2
                ${isDragTarget ? 'dp-drag-over' : ''}
                ${dragItem?.path === item.path ? 'dp-dragging' : ''}
                ${isSelected
                  ? 'bg-[#2a2a2b] border-[var(--dp-accent)] text-white'
                  : 'border-transparent text-gray-400 hover:bg-white/[0.04] hover:text-[#cccccc]'
                }`}
            >
              <div className="flex items-center gap-1.5 min-w-0 select-none">
                {/* Expand/Collapse chevron */}
                {item.is_dir ? (
                  <span className="w-4 h-4 flex items-center justify-center shrink-0">
                    {isExpanded
                      ? <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                      : <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
                    }
                  </span>
                ) : (
                  <span className="w-4" />
                )}

                {/* File/Folder Icon */}
                {getFileIconElement(item.name, item.is_dir, isExpanded)}

                {/* Name or Rename input */}
                {isBeingRenamed ? (
                  <form
                    onSubmit={(e) => { e.preventDefault(); handleRename(item.path, renameValue); }}
                    onClick={(e) => e.stopPropagation()}
                    className="flex-1 min-w-0"
                  >
                    <input
                      autoFocus
                      type="text"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={() => setRenamingPath(null)}
                      onKeyDown={(e) => { if (e.key === 'Escape') setRenamingPath(null); }}
                      className="bg-[#171922] border border-[var(--dp-accent)] text-xs px-1.5 py-0.5 rounded text-white focus:outline-none w-full font-mono"
                    />
                  </form>
                ) : (
                  <div className="flex items-center gap-1.5 min-w-0 truncate">
                    <span className={`text-[12px] truncate leading-tight ${
                      isSelected ? 'text-white font-medium' :
                      gitStatus === 'M' ? 'text-[var(--dp-git-modified)]' :
                      (gitStatus === 'A' || gitStatus === '??') ? 'text-[var(--dp-git-added)]' :
                      gitStatus === 'D' ? 'text-[var(--dp-git-deleted)]' :
                      'text-gray-400'
                    }`}>
                      {item.name}
                    </span>
                    {gitStatus && <GitBadge status={gitStatus} />}
                  </div>
                )}
              </div>

              {/* Hover action buttons */}
              {!isBeingRenamed && (
                <div className="opacity-0 group-hover:opacity-100 flex items-center gap-0.5 transition-opacity duration-100">
                  {item.is_dir && (
                    <>
                      <button
                        onClick={(e) => { e.stopPropagation(); setCreatingInPath(item.path); setCreatingType('file'); }}
                        className="p-0.5 rounded hover:bg-white/10 hover:text-white"
                        title="New File"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setCreatingInPath(item.path); setCreatingType('folder'); }}
                        className="p-0.5 rounded hover:bg-white/10 hover:text-white"
                        title="New Folder"
                      >
                        <FolderPlus className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); setRenamingPath(item.path); setRenameValue(item.name); }}
                    className="p-0.5 rounded hover:bg-white/10 hover:text-white"
                    title="Rename"
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                  <button
                    onClick={(e) => handleDeleteItem(item.path, e)}
                    className="p-0.5 rounded hover:bg-red-500/20 hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>

            {/* Expanded directory children */}
            {item.is_dir && isExpanded && (
              <div>
                {/* Inline create form */}
                {creatingType && creatingInPath === item.path && (
                  <form
                    onSubmit={handleCreateItem}
                    style={{ paddingLeft: `${(depth + 1) * 14 + 24}px` }}
                    className="py-1 pr-2 flex items-center gap-2"
                  >
                    {creatingType === 'folder'
                      ? <Folder className="w-4 h-4 text-yellow-500/80 shrink-0" />
                      : <FileIcon className="w-4 h-4 text-gray-400 shrink-0" />
                    }
                    <input
                      autoFocus
                      type="text"
                      value={newItemName}
                      onChange={(e) => setNewItemName(e.target.value)}
                      onBlur={() => setCreatingType(null)}
                      onKeyDown={(e) => { if (e.key === 'Escape') setCreatingType(null); }}
                      className="bg-[#171922] border border-[var(--dp-accent)] text-xs px-1.5 py-0.5 rounded text-white focus:outline-none w-full font-mono"
                      placeholder={creatingType === 'folder' ? 'Folder name...' : 'File name...'}
                    />
                  </form>
                )}

                {/* Directory children */}
                {dirContents[item.path] ? renderTree(dirContents[item.path], depth + 1) : (
                  loadingDir === item.path ? (
                    <div style={{ paddingLeft: `${(depth + 1) * 14 + 8}px` }} className="py-2">
                      <LoadingSpinner size={14} />
                    </div>
                  ) : null
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">
      {/* Explorer Header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] shrink-0 select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Explorer</span>
        {workspacePath && (
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => { setCreatingInPath(''); setCreatingType('file'); }}
              className="p-1 text-gray-400 hover:text-white cursor-pointer rounded hover:bg-white/10 transition-colors"
              title="New File at Root"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => { setCreatingInPath(''); setCreatingType('folder'); }}
              className="p-1 text-gray-400 hover:text-white cursor-pointer rounded hover:bg-white/10 transition-colors"
              title="New Folder at Root"
            >
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={collapseAll}
              className="p-1 text-gray-400 hover:text-white cursor-pointer rounded hover:bg-white/10 transition-colors"
              title="Collapse All"
            >
              <ChevronsDownUp className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={expandAll}
              className="p-1 text-gray-400 hover:text-white cursor-pointer rounded hover:bg-white/10 transition-colors"
              title="Expand All"
            >
              <ChevronsUpDown className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setShowHidden(!showHidden)}
              className={`p-1 cursor-pointer rounded hover:bg-white/10 transition-colors ${showHidden ? 'text-[var(--dp-accent)]' : 'text-gray-400 hover:text-white'}`}
              title={showHidden ? 'Hide Hidden Files' : 'Show Hidden Files'}
            >
              {showHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            </button>
          </div>
        )}
      </div>

      {/* Search Filter */}
      <div className="px-2 py-1.5 border-b border-[var(--dp-border)]">
        <input
          type="text"
          placeholder="Filter files..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          className="w-full px-2 py-1 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded text-xs text-[var(--dp-text-primary)] focus:outline-none focus:border-[var(--dp-border-focus)] transition-colors font-sans placeholder:text-gray-500"
        />
      </div>

      {/* Breadcrumb */}
      {renderBreadcrumb()}

      {/* File Tree */}
      {!workspacePath ? (
        <div className="flex-1 flex flex-col justify-center items-center px-4 py-8 text-center text-gray-500 select-none">
          <FolderOpen className="w-10 h-10 text-gray-600 mb-3" />
          <p className="text-xs font-semibold mb-1 text-gray-300">No Folder Opened</p>
          <p className="text-[10px] text-gray-500 mb-4 max-w-[180px] leading-relaxed">
            Open a workspace folder to view files and start building.
          </p>
          <button
            onClick={onOpenFolder}
            className="px-4 py-1.5 bg-[var(--dp-accent)] hover:bg-[var(--dp-accent-hover)] text-white text-xs font-medium rounded transition-colors w-full max-w-[140px] cursor-pointer"
          >
            Open Folder
          </button>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto py-0.5">
            {/* Root create form */}
            {creatingType && creatingInPath === '' && (
              <form onSubmit={handleCreateItem} className="px-3 py-1 flex items-center gap-1.5">
                {creatingType === 'folder'
                  ? <Folder className="w-3.5 h-3.5 text-yellow-500/80 shrink-0" />
                  : <FileIcon className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                }
                <input
                  autoFocus
                  type="text"
                  value={newItemName}
                  onChange={(e) => setNewItemName(e.target.value)}
                  onBlur={() => setCreatingType(null)}
                  onKeyDown={(e) => { if (e.key === 'Escape') setCreatingType(null); }}
                  className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-accent)] text-xs px-1.5 py-0.5 rounded text-white focus:outline-none w-full font-mono"
                  placeholder={creatingType === 'folder' ? 'Folder name...' : 'File name...'}
                />
              </form>
            )}

            {loadingDir === '' ? (
              <div className="flex items-center justify-center py-4"><LoadingSpinner size={20} /></div>
            ) : rootItems.length === 0 ? (
              <div className="px-3 py-8 text-center text-xs text-gray-500 font-sans">Workspace is empty</div>
            ) : (
              renderTree(rootItems)
            )}
          </div>

          {/* Workspace Insights */}
          {stats && (
            <div className="shrink-0 bg-[var(--dp-bg-tertiary)] select-none border-t border-[var(--dp-border)] font-sans">
              <div
                onClick={() => setIsStatsExpanded(!isStatsExpanded)}
                className="flex items-center justify-between px-3 py-1 hover:bg-white/5 cursor-pointer text-gray-400 hover:text-white transition-colors"
              >
                <span className="text-[9px] font-bold uppercase tracking-wider">Workspace Insights</span>
                {isStatsExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </div>

              {isStatsExpanded && (
                <div className="p-3 bg-[var(--dp-bg-secondary)] text-[10px] space-y-2 max-h-48 overflow-y-auto border-t border-[var(--dp-border)]">
                  <div className="grid grid-cols-2 gap-1.5 text-gray-400 font-mono">
                    <div className="p-1.5 bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded">
                      <div className="text-gray-500 text-[8px] uppercase font-bold">Files</div>
                      <div className="text-xs font-bold text-[var(--dp-accent)]">{stats.total_files}</div>
                    </div>
                    <div className="p-1.5 bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded">
                      <div className="text-gray-500 text-[8px] uppercase font-bold">Total LOC</div>
                      <div className="text-xs font-bold text-[var(--dp-accent)]">{stats.total_lines.toLocaleString()}</div>
                    </div>
                    {stats.git_commits > 0 && (
                      <div className="col-span-2 p-1.5 bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded flex justify-between items-center">
                        <span className="text-gray-500 text-[8px] uppercase font-bold">Git Commits</span>
                        <span className="text-xs font-bold text-[var(--dp-accent)] font-mono">{stats.git_commits}</span>
                      </div>
                    )}
                  </div>

                  {Object.keys(stats.languages).length > 0 && (
                    <div className="space-y-1">
                      <div className="text-gray-500 text-[8px] uppercase font-bold">Languages</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(stats.languages).map(([lang, count]) => (
                          <span key={lang} className="px-1.5 py-0.5 rounded bg-[var(--dp-accent-dim)] text-[var(--dp-accent)] text-[9px] border border-[var(--dp-accent)]/10 font-medium font-mono">
                            {lang}: <span className="font-bold">{count}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={buildContextMenu(contextMenu.item)}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}
