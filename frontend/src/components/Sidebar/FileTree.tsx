import React, { useRef, useState, useEffect } from 'react';
import {
  Folder, FolderOpen, File as FileIcon, ChevronRight, ChevronDown
} from 'lucide-react';
import type { FileItem } from './types';

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
  lock: { color: '#776e6e', label: '🔒' },
  txt: { color: '#89898b', label: 'Tx' },
  log: { color: '#776e6e', label: '📋' },
  xml: { color: '#f36e1f', label: 'XM' },
  zip: { color: '#afb42b', label: '📦' },
  gz: { color: '#afb42b', label: '📦' },
  tar: { color: '#afb42b', label: '📦' },
};

function getFileIconElement(name: string, isDir: boolean, isExpanded: boolean) {
  if (isDir) {
    return isExpanded ? (
      <FolderOpen className="w-4 h-4 text-yellow-500/90 shrink-0" />
    ) : (
      <Folder className="w-4 h-4 text-yellow-500/80 shrink-0" />
    );
  }

  const lower = name.toLowerCase();
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

  return <FileIcon className="w-3.5 h-3.5 text-gray-400 shrink-0" />;
}

function GitBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; cls: string }> = {
    M: { label: 'M', cls: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20' },
    A: { label: 'A', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
    D: { label: 'D', cls: 'bg-red-500/15 text-red-400 border-red-500/20' },
    '??': { label: 'U', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/20' },
    R: { label: 'R', cls: 'bg-[#4C8DFF]/15 text-[#4C8DFF] border-[#4C8DFF]/20' },
  };
  const c = config[status] || config['??'];
  return (
    <span className={`text-[8px] font-bold px-1 py-px rounded border leading-none shrink-0 font-mono ${c.cls}`}>
      {c.label}
    </span>
  );
}

interface FileTreeProps {
  items: FileItem[];
  depth?: number;
  dirContents: Record<string, FileItem[]>;
  expandedPaths: Record<string, boolean>;
  selectedFilePath: string | null;
  loadingDir: string | null;
  renamingPath: string | null;
  renameValue: string;
  gitChanges?: Record<string, string>;
  searchTerm: string;
  showHidden: boolean;
  onToggleExpand: (path: string) => void;
  onSelectFile: (path: string, isCtrlKey: boolean) => void;
  selectedPaths: string[];
  onContextMenu: (e: React.MouseEvent, item: FileItem) => void;
  onRenameSubmit: (e: React.FormEvent, item: FileItem) => void;
  setRenameValue: (val: string) => void;
  setRenamingPath: (path: string | null) => void;
  onDragStart: (item: FileItem) => void;
  onDragOver: (e: React.DragEvent, path: string) => void;
  onDrop: (e: React.DragEvent, targetItem: FileItem) => void;
}

const HIDDEN_PATTERNS = [
  'node_modules', '__pycache__', '.git', '.venv', 'venv', '.mypy_cache',
  '.pytest_cache', '.next', 'dist', '.DS_Store', 'thumbs.db',
  '.env.local', '.vercel', '.turbo', '.cache'
];

interface FlatNode {
  item: FileItem;
  depth: number;
  is_dir: boolean;
  is_loading: boolean;
}

const ROW_HEIGHT = 24;
const OVERSCAN = 10;

export const FileTree: React.FC<FileTreeProps> = ({
  items,
  depth = 0,
  dirContents,
  expandedPaths,
  selectedFilePath,
  loadingDir,
  renamingPath,
  renameValue,
  gitChanges,
  searchTerm,
  showHidden,
  onToggleExpand,
  onSelectFile,
  selectedPaths,
  onContextMenu,
  onRenameSubmit,
  setRenameValue,
  setRenamingPath,
  onDragStart,
  onDragOver,
  onDrop,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(400);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scrollParent = container.parentElement;
    if (!scrollParent) return;

    const handleScroll = () => {
      setScrollTop(scrollParent.scrollTop);
    };

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.target === scrollParent) {
          setContainerHeight(entry.contentRect.height);
        }
      }
    });

    scrollParent.addEventListener('scroll', handleScroll, { passive: true });
    resizeObserver.observe(scrollParent);

    // Initial state
    setScrollTop(scrollParent.scrollTop);
    setContainerHeight(scrollParent.getBoundingClientRect().height);

    return () => {
      scrollParent.removeEventListener('scroll', handleScroll);
      resizeObserver.disconnect();
    };
  }, []);

  const buildFlatNodes = (currentItems: FileItem[], currentDepth: number): FlatNode[] => {
    const nodes: FlatNode[] = [];
    const filtered = currentItems.filter(item => {
      if (!showHidden && HIDDEN_PATTERNS.includes(item.name.toLowerCase())) {
        return false;
      }
      if (searchTerm) {
        return item.name.toLowerCase().includes(searchTerm.toLowerCase());
      }
      return true;
    });

    for (const item of filtered) {
      const isExpanded = Boolean(expandedPaths[item.path]);
      const isLoading = loadingDir === item.path;

      nodes.push({
        item,
        depth: currentDepth,
        is_dir: item.is_dir,
        is_loading: false
      });

      if (item.is_dir && isExpanded) {
        if (isLoading) {
          nodes.push({
            item: {
              name: 'Loading...',
              path: `${item.path}::loading`,
              is_dir: false
            },
            depth: currentDepth + 1,
            is_dir: false,
            is_loading: true
          });
        } else {
          const children = dirContents[item.path] || [];
          nodes.push(...buildFlatNodes(children, currentDepth + 1));
        }
      }
    }
    return nodes;
  };

  const flatNodes = buildFlatNodes(items, depth);
  const totalHeight = flatNodes.length * ROW_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(flatNodes.length, Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + OVERSCAN);

  const visibleNodes = flatNodes.slice(startIndex, endIndex);

  return (
    <div ref={containerRef} className="relative w-full select-none font-sans" style={{ height: `${totalHeight}px` }}>
      {visibleNodes.map((node, i) => {
        const actualIndex = startIndex + i;
        const item = node.item;

        if (node.is_loading) {
          return (
            <div
              key={item.path}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                transform: `translateY(${actualIndex * ROW_HEIGHT}px)`,
                height: `${ROW_HEIGHT}px`,
                paddingLeft: `${node.depth * 12 + 10}px`,
              }}
              className="text-[10px] text-gray-500 flex items-center gap-1"
            >
              <span>Loading...</span>
            </div>
          );
        }

        const isExpanded = Boolean(expandedPaths[item.path]);
        const isSelected = selectedFilePath === item.path || selectedPaths.includes(item.path);
        const gitStatus = gitChanges?.[item.path];
        const isRenaming = renamingPath === item.path;

        return (
          <div
            key={item.path}
            draggable
            onDragStart={() => onDragStart(item)}
            onDragOver={e => onDragOver(e, item.path)}
            onDrop={e => onDrop(e, item)}
            onClick={(e) => {
              if (item.is_dir) {
                if (e.ctrlKey || e.metaKey) {
                  onSelectFile(item.path, true);
                } else {
                  onToggleExpand(item.path);
                  onSelectFile(item.path, false);
                }
              } else {
                onSelectFile(item.path, e.ctrlKey || e.metaKey);
              }
            }}
            onContextMenu={e => onContextMenu(e, item)}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              transform: `translateY(${actualIndex * ROW_HEIGHT}px)`,
              height: `${ROW_HEIGHT}px`,
              paddingLeft: `${node.depth * 12 + 10}px`,
            }}
            className={`
              group flex items-center justify-between pr-2 text-[12px] cursor-pointer transition-colors
              ${isSelected ? 'bg-[#4C8DFF]/20 text-white font-semibold border-l-2 border-[#4C8DFF]' : 'text-gray-300 hover:bg-white/5 hover:text-white'}
            `}
          >
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              {item.is_dir ? (
                <span className="w-3.5 h-3.5 flex items-center justify-center text-gray-500 group-hover:text-gray-300">
                  {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                </span>
              ) : (
                <span className="w-3 h-3" />
              )}

              {getFileIconElement(item.name, item.is_dir, isExpanded)}

              {isRenaming ? (
                <form onSubmit={e => onRenameSubmit(e, item)} className="flex-1" onClick={e => e.stopPropagation()}>
                  <input
                    type="text"
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    autoFocus
                    onBlur={() => setRenamingPath(null)}
                    className="w-full bg-[#151823] text-white text-[11px] px-1 py-0 rounded border border-[#4C8DFF] focus:outline-none"
                  />
                </form>
              ) : (
                <span className="truncate leading-none">{item.name}</span>
              )}
            </div>

            {gitStatus && <GitBadge status={gitStatus} />}
          </div>
        );
      })}
    </div>
  );
};
