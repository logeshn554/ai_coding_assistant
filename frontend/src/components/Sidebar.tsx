import React, { useState, useEffect } from 'react';
import { Folder, FolderOpen, File, FileCode, Plus, FolderPlus, Trash2, ChevronRight, ChevronDown, Terminal } from 'lucide-react';

interface FileItem {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

interface SidebarProps {
  onSelectFile: (path: string) => void;
  selectedFilePath: string | null;
  refreshTrigger: number;
  workspacePath: string;
  onOpenFolder: () => void;
  gitChanges?: Record<string, string>;
}

export default function Sidebar({ onSelectFile, selectedFilePath, refreshTrigger, workspacePath, onOpenFolder, gitChanges }: SidebarProps) {
  const [rootItems, setRootItems] = useState<FileItem[]>([]);
  const [dirContents, setDirContents] = useState<Record<string, FileItem[]>>({});
  const [expandedPaths, setExpandedPaths] = useState<Record<string, boolean>>({});

  const [stats, setStats] = useState<{
    total_files: number;
    total_lines: number;
    languages: Record<string, number>;
    git_commits: number;
  } | null>(null);
  const [isStatsExpanded, setIsStatsExpanded] = useState(false);

  const fetchStats = async () => {
    if (!workspacePath) return;
    try {
      const res = await fetch('/api/workspace/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchStats();
  }, [workspacePath, refreshTrigger]);


  // States for new item creation
  const [creatingType, setCreatingType] = useState<'file' | 'folder' | null>(null);
  const [creatingInPath, setCreatingInPath] = useState<string>(''); // empty means root
  const [newItemName, setNewItemName] = useState<string>('');

  const loadDirectory = async (relPath: string = "") => {
    try {
      const res = await fetch(`/api/files?path=${encodeURIComponent(relPath)}`);
      const items = await res.json();
      if (relPath === "") {
        setRootItems(items);
      } else {
        setDirContents(prev => ({ ...prev, [relPath]: items }));
      }
    } catch (e) {
      console.error(`Error loading directory ${relPath}:`, e);
    }
  };

  useEffect(() => {
    if (!workspacePath) {
      setRootItems([]);
      return;
    }
    loadDirectory("");
    // Re-load any expanded directories to reflect changes
    Object.keys(expandedPaths).forEach(path => {
      if (expandedPaths[path]) {
        loadDirectory(path);
      }
    });
  }, [refreshTrigger, workspacePath]);

  const handleToggleFolder = async (path: string) => {
    const isExpanded = !!expandedPaths[path];
    if (!isExpanded) {
      // Load contents before expanding
      await loadDirectory(path);
      setExpandedPaths(prev => ({ ...prev, [path]: true }));
    } else {
      setExpandedPaths(prev => ({ ...prev, [path]: false }));
    }
  };

  const handleCreateItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim()) return;

    const relPath = creatingInPath 
      ? `${creatingInPath}/${newItemName.trim()}`
      : newItemName.trim();

    try {
      const res = await fetch('/api/files/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: relPath,
          is_dir: creatingType === 'folder'
        })
      });
      if (res.ok) {
        // Refresh the parent directory
        await loadDirectory(creatingInPath);
        if (creatingInPath) {
          setExpandedPaths(prev => ({ ...prev, [creatingInPath]: true }));
        }
        setNewItemName('');
        setCreatingType(null);
      } else {
        const err = await res.json();
        alert('Error creating item: ' + err.detail);
      }
    } catch (e) {
      alert('Error creating item: ' + e);
    }
  };

  const handleDeleteItem = async (path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete '${path}'?`)) return;

    try {
      const res = await fetch('/api/files/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      if (res.ok) {
        // Find parent path
        const lastSlash = path.lastIndexOf('/');
        const parentPath = lastSlash === -1 ? "" : path.substring(0, lastSlash);
        await loadDirectory(parentPath);
      } else {
        const err = await res.json();
        alert('Error deleting item: ' + err.detail);
      }
    } catch (e) {
      alert('Error deleting item: ' + e);
    }
  };

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'py':
        return <FileCode className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'ts':
      case 'tsx':
        return <FileCode className="w-4 h-4 text-sky-400 shrink-0" />;
      case 'js':
      case 'jsx':
        return <FileCode className="w-4 h-4 text-amber-400 shrink-0" />;
      case 'json':
        return <FileCode className="w-4 h-4 text-yellow-400 shrink-0" />;
      case 'css':
      case 'html':
        return <FileCode className="w-4 h-4 text-orange-400 shrink-0" />;
      case 'md':
        return <FileCode className="w-4 h-4 text-indigo-400 shrink-0" />;
      case 'bat':
      case 'sh':
        return <Terminal className="w-4 h-4 text-rose-400 shrink-0" />;
      default:
        return <File className="w-4 h-4 text-gray-400 shrink-0" />;
    }
  };

  const renderTree = (items: FileItem[], depth = 0) => {
    return (
      <div className="flex flex-col">
        {items.map(item => {
          const isExpanded = !!expandedPaths[item.path];
          const isSelected = selectedFilePath === item.path;
          
          return (
            <div key={item.path} className="flex flex-col">
              {/* Row */}
              <div
                onClick={() => {
                  if (item.is_dir) {
                    handleToggleFolder(item.path);
                  } else {
                    onSelectFile(item.path);
                  }
                }}
                style={{ paddingLeft: `${depth * 12 + 8}px` }}
                className={`group flex items-center justify-between py-1.5 pr-2 cursor-pointer transition-all hover:bg-white/5 border-l-2 ${
                  isSelected 
                    ? 'bg-violet-600/10 border-violet-500 text-white font-medium' 
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 select-none">
                  {item.is_dir ? (
                    <>
                      {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-gray-500" /> : <ChevronRight className="w-3.5 h-3.5 text-gray-500" />}
                      {isExpanded ? <FolderOpen className="w-4 h-4 text-yellow-500/80 shrink-0" /> : <Folder className="w-4 h-4 text-yellow-500/80 shrink-0" />}
                    </>
                  ) : (
                    <>
                      <span className="w-3.5" /> {/* spacer to align with folders */}
                      {getFileIcon(item.name)}
                    </>
                  )}
                  {(() => {
                    const gitStatus = gitChanges ? gitChanges[item.path] : undefined;
                    const statusColor = gitStatus === 'M' 
                      ? 'text-yellow-500 font-semibold' 
                      : (gitStatus === 'A' || gitStatus === '??') 
                        ? 'text-emerald-500 font-semibold' 
                        : 'text-gray-400 hover:text-gray-200';
                    return (
                      <div className="flex items-center gap-1.5 min-w-0 truncate">
                        <span className={`text-xs truncate ${isSelected ? 'text-white font-medium' : statusColor}`}>{item.name}</span>
                        {gitStatus && (
                          <span className={`text-[8px] font-bold px-1 rounded shrink-0 leading-normal ${
                            gitStatus === 'M' ? 'bg-yellow-500/10 text-yellow-500' : 'bg-emerald-500/10 text-emerald-500'
                          }`}>
                            {gitStatus === '??' ? 'U' : gitStatus}
                          </span>
                        )}
                      </div>
                    );
                  })()}
                </div>
                
                {/* Actions */}
                <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1">
                  {item.is_dir && (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setCreatingInPath(item.path);
                          setCreatingType('file');
                        }}
                        className="p-0.5 rounded hover:bg-white/10 hover:text-white"
                        title="New File"
                      >
                        <Plus className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setCreatingInPath(item.path);
                          setCreatingType('folder');
                        }}
                        className="p-0.5 rounded hover:bg-white/10 hover:text-white"
                        title="New Folder"
                      >
                        <FolderPlus className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                  <button
                    onClick={(e) => handleDeleteItem(item.path, e)}
                    className="p-0.5 rounded hover:bg-red-500/20 hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Children (if expanded dir) */}
              {item.is_dir && isExpanded && dirContents[item.path] && (
                <div>
                  {/* Inline creation input if creating inside this folder */}
                  {creatingType && creatingInPath === item.path && (
                    <form
                      onSubmit={handleCreateItem}
                      style={{ paddingLeft: `${(depth + 1) * 12 + 20}px` }}
                      className="py-1 pr-2 flex items-center gap-2"
                    >
                      {creatingType === 'folder' ? <Folder className="w-4 h-4 text-yellow-500/80 shrink-0" /> : <File className="w-4 h-4 text-gray-400 shrink-0" />}
                      <input
                        autoFocus
                        type="text"
                        value={newItemName}
                        onChange={(e) => setNewItemName(e.target.value)}
                        onBlur={() => setCreatingType(null)}
                        className="bg-[#171922] border border-violet-500 text-xs px-1.5 py-0.5 rounded text-white focus:outline-none w-full"
                        placeholder={creatingType === 'folder' ? "Folder name..." : "File name..."}
                      />
                    </form>
                  )}
                  {renderTree(dirContents[item.path], depth + 1)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col bg-[#0e1014] text-gray-300 select-none">
      {/* Sidebar Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-[#111318]">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Workspace</span>
        {workspacePath && (
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => {
                setCreatingInPath("");
                setCreatingType('file');
              }}
              className="p-1 rounded hover:bg-white/5 hover:text-white"
              title="New File at Root"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                setCreatingInPath("");
                setCreatingType('folder');
              }}
              className="p-1 rounded hover:bg-white/5 hover:text-white"
              title="New Folder at Root"
            >
              <FolderPlus className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Directory Tree */}
      {!workspacePath ? (
        <div className="flex-1 flex flex-col justify-center items-center px-4 py-8 text-center text-gray-400 select-none">
          <FolderOpen className="w-12 h-12 text-violet-500/30 mb-3" />
          <p className="text-xs font-semibold mb-1 text-gray-300">No Folder Opened</p>
          <p className="text-[10px] text-gray-500 mb-4 max-w-[180px] leading-relaxed">
            Open a workspace folder to view files and start building.
          </p>
          <button
            onClick={onOpenFolder}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-medium shadow-md transition-colors w-full max-w-[140px]"
          >
            Open Folder
          </button>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto py-2">
            {creatingType && creatingInPath === "" && (
              <form
                onSubmit={handleCreateItem}
                className="px-4 py-1 flex items-center gap-2"
              >
                {creatingType === 'folder' ? <Folder className="w-4 h-4 text-yellow-500/80 shrink-0" /> : <File className="w-4 h-4 text-gray-400 shrink-0" />}
                <input
                  autoFocus
                  type="text"
                  value={newItemName}
                  onChange={(e) => setNewItemName(e.target.value)}
                  onBlur={() => setCreatingType(null)}
                  className="bg-[#171922] border border-violet-500 text-xs px-1.5 py-0.5 rounded text-white focus:outline-none w-full"
                  placeholder={creatingType === 'folder' ? "Folder name..." : "File name..."}
                />
              </form>
            )}
            {rootItems.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-gray-650">
                Workspace is empty
              </div>
            ) : (
              renderTree(rootItems)
            )}
          </div>

          {/* Workspace statistics section */}
          {stats && (
            <div className="shrink-0 bg-[#0c0d11] select-none border-t border-white/5 font-sans">
              <div 
                onClick={() => setIsStatsExpanded(!isStatsExpanded)}
                className="flex items-center justify-between px-4 py-2 hover:bg-white/5 cursor-pointer text-gray-405 hover:text-white"
              >
                <span className="text-[10px] font-bold uppercase tracking-wider">Workspace Insights</span>
                {isStatsExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </div>
              
              {isStatsExpanded && (
                <div className="p-3.5 bg-black/15 text-[10px] space-y-2.5 max-h-48 overflow-y-auto border-t border-white/5">
                  <div className="grid grid-cols-2 gap-2 text-gray-400 font-mono">
                    <div className="p-1.5 bg-white/2 rounded border border-white/5">
                      <div className="text-gray-500 text-[8px] uppercase font-bold">Files</div>
                      <div className="text-xs font-bold text-violet-400">{stats.total_files}</div>
                    </div>
                    <div className="p-1.5 bg-white/2 rounded border border-white/5">
                      <div className="text-gray-500 text-[8px] uppercase font-bold">Total LOC</div>
                      <div className="text-xs font-bold text-violet-400">{stats.total_lines}</div>
                    </div>
                    {stats.git_commits > 0 && (
                      <div className="col-span-2 p-1.5 bg-white/2 rounded border border-white/5 flex justify-between items-center">
                        <span className="text-gray-500 text-[8px] uppercase font-bold">Git Commits</span>
                        <span className="text-xs font-bold text-violet-400 font-mono">{stats.git_commits}</span>
                      </div>
                    )}
                  </div>

                  {Object.keys(stats.languages).length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-gray-500 text-[8px] uppercase font-bold">Languages breakdown</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(stats.languages).map(([lang, count]) => (
                          <span key={lang} className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 text-[9px] border border-violet-500/10 font-medium">
                            {lang}: <span className="font-bold font-mono">{count}</span>
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
    </div>
  );
}
