/**
 * QuickOpen.tsx — Ctrl+P fuzzy file picker
 *
 * Opened via Ctrl+P. Fuzzy-searches workspace files using fuse.js.
 * Keyboard: ↑/↓ navigate, Enter opens, Esc closes.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import Fuse from 'fuse.js';
import { File, FileCode, FileText, FolderOpen, Search } from 'lucide-react';

interface QuickOpenProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenFile: (path: string) => void;
  recentFiles?: string[];
}

/** File extension → icon colour */
function FileIcon({ path }: { path: string }) {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  const colour =
    ext === 'ts' || ext === 'tsx' ? 'text-blue-400' :
    ext === 'js' || ext === 'jsx' ? 'text-yellow-400' :
    ext === 'py' ? 'text-green-400' :
    ext === 'css' || ext === 'scss' ? 'text-pink-400' :
    ext === 'json' ? 'text-orange-400' :
    ext === 'md' ? 'text-purple-300' :
    ext === 'html' ? 'text-red-400' :
    'text-gray-400';

  if (['ts', 'tsx', 'js', 'jsx'].includes(ext)) return <FileCode className={`w-3.5 h-3.5 shrink-0 ${colour}`} />;
  if (ext === 'py') return <FileText className={`w-3.5 h-3.5 shrink-0 ${colour}`} />;
  return <File className={`w-3.5 h-3.5 shrink-0 ${colour}`} />;
}

/** Highlight matching characters in the result string */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <span>{text}</span>;
  const lower = text.toLowerCase();
  const qLower = query.toLowerCase();
  const parts: React.ReactNode[] = [];
  let last = 0;
  let idx = lower.indexOf(qLower);
  if (idx !== -1) {
    parts.push(text.slice(last, idx));
    parts.push(
      <span key="hl" className="text-violet-300 font-semibold">
        {text.slice(idx, idx + query.length)}
      </span>
    );
    last = idx + query.length;
  }
  parts.push(text.slice(last));
  return <>{parts}</>;
}

const FUSE_OPTIONS = {
  includeScore: true,
  threshold: 0.45,
  keys: [
    { name: 'filename', weight: 0.7 },
    { name: 'path', weight: 0.3 },
  ],
};

type FileEntry = { path: string; filename: string };

export default function QuickOpen({ isOpen, onClose, onOpenFile, recentFiles = [] }: QuickOpenProps) {
  const [query, setQuery] = useState('');
  const [allFiles, setAllFiles] = useState<FileEntry[]>([]);
  const [results, setResults] = useState<FileEntry[]>([]);
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const fuseRef = useRef<Fuse<FileEntry> | null>(null);

  // Fetch file list when opened
  useEffect(() => {
    if (!isOpen) return;
    setQuery('');
    setSelected(0);
    setTimeout(() => inputRef.current?.focus(), 20);

    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/workspace/fuzzy-files?limit=2000');
        if (res.ok) {
          const data = await res.json();
          const entries: FileEntry[] = (data.files || []).map((p: string) => ({
            path: p,
            filename: p.split('/').pop() ?? p,
          }));
          setAllFiles(entries);
          fuseRef.current = new Fuse(entries, FUSE_OPTIONS);
          // Default: show recent files or first 20
          if (recentFiles.length) {
            const recentEntries = recentFiles
              .map((r) => entries.find((e) => e.path === r))
              .filter(Boolean) as FileEntry[];
            setResults(recentEntries.slice(0, 20));
          } else {
            setResults(entries.slice(0, 20));
          }
        }
      } catch {
        // Silently fail — no workspace open yet
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [isOpen]);

  // Run fuzzy search on query change
  useEffect(() => {
    if (!isOpen) return;
    if (!query.trim()) {
      // Show recent or first files
      if (recentFiles.length) {
        const recentEntries = recentFiles
          .map((r) => allFiles.find((e) => e.path === r))
          .filter(Boolean) as FileEntry[];
        setResults(recentEntries.slice(0, 20));
      } else {
        setResults(allFiles.slice(0, 20));
      }
      setSelected(0);
      return;
    }
    if (!fuseRef.current) return;
    const raw = fuseRef.current.search(query);
    setResults(raw.map((r) => r.item).slice(0, 50));
    setSelected(0);
  }, [query, allFiles, isOpen]);

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selected] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  const handleSelect = useCallback(
    (path: string) => {
      onOpenFile(path);
      onClose();
    },
    [onOpenFile, onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelected((s) => Math.min(s + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelected((s) => Math.max(s - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (results[selected]) handleSelect(results[selected].path);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    },
    [results, selected, handleSelect, onClose]
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-16 bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-[560px] max-w-[95vw] bg-[#1a1b26] border border-[#2d2f45] rounded-lg shadow-2xl shadow-black/60 overflow-hidden animate-in fade-in slide-in-from-top-3 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-b border-[#2d2f45] bg-[#13141f]">
          {loading ? (
            <FolderOpen className="w-4 h-4 text-violet-400 shrink-0 animate-pulse" />
          ) : (
            <Search className="w-4 h-4 text-violet-400 shrink-0" />
          )}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Go to file…"
            className="flex-1 bg-transparent text-sm text-white placeholder:text-gray-500 focus:outline-none font-mono"
            id="quick-open-input"
            autoComplete="off"
            spellCheck={false}
          />
          <span className="text-[10px] text-gray-600 bg-white/5 px-1.5 py-0.5 rounded font-mono shrink-0">
            ESC
          </span>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1 scrollbar-thin">
          {!loading && results.length === 0 && query && (
            <div className="px-4 py-5 text-sm text-gray-500 text-center italic">
              No files match "{query}"
            </div>
          )}
          {!loading && results.length === 0 && !query && (
            <div className="px-4 py-5 text-xs text-gray-600 text-center">
              No workspace open. Use File: Open Workspace Folder first.
            </div>
          )}
          {results.map((entry, idx) => {
            const isSelected = idx === selected;
            const dir = entry.path.includes('/')
              ? entry.path.slice(0, entry.path.lastIndexOf('/'))
              : '';
            return (
              <div
                key={entry.path}
                onClick={() => handleSelect(entry.path)}
                className={`flex items-center gap-2.5 px-3.5 py-1.5 cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-violet-600/20 border-l-2 border-violet-500'
                    : 'hover:bg-white/5 border-l-2 border-transparent'
                }`}
                onMouseEnter={() => setSelected(idx)}
                id={`quick-open-result-${idx}`}
              >
                <FileIcon path={entry.path} />
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-gray-200 font-medium font-mono truncate block">
                    <HighlightMatch text={entry.filename} query={query} />
                  </span>
                  {dir && (
                    <span className="text-[10px] text-gray-500 font-mono truncate block">
                      {dir}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer hint */}
        <div className="px-3.5 py-1.5 bg-[#13141f] border-t border-[#2d2f45] flex items-center gap-4 text-[10px] text-gray-600">
          <span><kbd className="bg-white/10 px-1 rounded">↑↓</kbd> navigate</span>
          <span><kbd className="bg-white/10 px-1 rounded">↵</kbd> open</span>
          <span><kbd className="bg-white/10 px-1 rounded">esc</kbd> close</span>
          {results.length > 0 && (
            <span className="ml-auto">{results.length} result{results.length !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
    </div>
  );
}
