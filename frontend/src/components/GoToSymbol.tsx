/**
 * GoToSymbol.tsx — Ctrl+Shift+O symbol picker
 *
 * Lists code symbols (classes, functions, interfaces, etc.) extracted from
 * the currently-active file by the backend /api/workspace/symbols endpoint.
 * Selecting a symbol calls `onRevealLine` so the editor can jump to it.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Box,
  Braces,
  Code,
  FunctionSquare,
  Hash,
  Loader2,
  Search,
  Type,
} from 'lucide-react';

export interface WorkspaceSymbol {
  name: string;
  kind: number;
  kindName: string;
  line: number;
  col: number;
  file?: string;
}

interface GoToSymbolProps {
  isOpen: boolean;
  onClose: () => void;
  activeFilePath: string | null;
  onRevealLine: (line: number, col?: number) => void;
  onOpenFile?: (filePath: string, line?: number) => void;
}

// LSP-compatible kind numbers → icon + colour
function SymbolIcon({ kindName }: { kindName: string }) {
  switch (kindName) {
    case 'class':
      return <Box className="w-3.5 h-3.5 text-yellow-400 shrink-0" />;
    case 'function':
      return <FunctionSquare className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
    case 'method':
      return <Code className="w-3.5 h-3.5 text-green-400 shrink-0" />;
    case 'interface':
      return <Type className="w-3.5 h-3.5 text-cyan-400 shrink-0" />;
    case 'type':
      return <Type className="w-3.5 h-3.5 text-pink-400 shrink-0" />;
    case 'variable':
      return <Hash className="w-3.5 h-3.5 text-orange-400 shrink-0" />;
    default:
      return <Braces className="w-3.5 h-3.5 text-violet-400 shrink-0" />;
  }
}

const KIND_LABEL: Record<string, string> = {
  class: 'C',
  function: 'F',
  method: 'M',
  interface: 'I',
  type: 'T',
  variable: 'V',
};

const KIND_COLOUR: Record<string, string> = {
  class: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/20',
  function: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  method: 'bg-green-500/15 text-green-400 border-green-500/20',
  interface: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
  type: 'bg-pink-500/15 text-pink-400 border-pink-500/20',
  variable: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
};

export default function GoToSymbol({
  isOpen,
  onClose,
  activeFilePath,
  onRevealLine,
  onOpenFile,
}: GoToSymbolProps) {
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<'file' | 'global'>('file');
  const [symbols, setSymbols] = useState<WorkspaceSymbol[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Load symbols when opened, mode changes, or file changes
  useEffect(() => {
    if (!isOpen) return;
    setSelected(0);
    setLoading(true);
    setTimeout(() => inputRef.current?.focus(), 20);

    const url = scope === 'global'
      ? `/api/workspace/global-symbols?q=${encodeURIComponent(query.trim())}`
      : activeFilePath
      ? `/api/workspace/symbols?path=${encodeURIComponent(activeFilePath)}`
      : null;

    if (!url) {
      setSymbols([]);
      setLoading(false);
      return;
    }

    fetch(url)
      .then((res) => res.json())
      .then((data) => setSymbols(data.symbols || []))
      .catch(() => setSymbols([]))
      .finally(() => setLoading(false));
  }, [isOpen, activeFilePath, scope, query]);

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.children[selected] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  const filtered = scope === 'file' && query.trim()
    ? symbols.filter((s) => s.name.toLowerCase().includes(query.toLowerCase()))
    : symbols;

  const handleSelect = useCallback(
    (sym: WorkspaceSymbol) => {
      if (sym.file && onOpenFile) {
        onOpenFile(sym.file, sym.line);
      } else {
        onRevealLine(sym.line, sym.col);
      }
      onClose();
    },
    [onRevealLine, onOpenFile, onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelected((s) => Math.min(s + 1, filtered.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelected((s) => Math.max(s - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filtered[selected]) handleSelect(filtered[selected]);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    },
    [filtered, selected, handleSelect, onClose]
  );

  if (!isOpen) return null;

  const fileName = activeFilePath?.split('/').pop() ?? activeFilePath ?? '';

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-16 bg-black/65 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-[560px] max-w-[95vw] bg-[#141522] border border-[#2d2f45] rounded-xl shadow-2xl shadow-black/80 overflow-hidden animate-in fade-in slide-in-from-top-3 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Mode Switcher & Search Input */}
        <div className="p-3 border-b border-[#2d2f45] bg-[#10111a] space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex bg-[#181926] border border-[#2d2f45] p-0.5 rounded-lg text-xs font-semibold">
              <button
                type="button"
                onClick={() => setScope('file')}
                className={`px-2.5 py-0.5 rounded-md transition-colors cursor-pointer ${
                  scope === 'file' ? 'bg-violet-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Current File Symbols
              </button>
              <button
                type="button"
                onClick={() => setScope('global')}
                className={`px-2.5 py-0.5 rounded-md transition-colors cursor-pointer ${
                  scope === 'global' ? 'bg-violet-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Global Workspace Symbols
              </button>
            </div>

            <span className="text-[10px] text-zinc-500 font-mono">
              {scope === 'file' ? 'Ctrl+Shift+O' : 'Ctrl+T'}
            </span>
          </div>

          <div className="flex items-center gap-2.5 px-3 py-1.5 bg-[#181926] border border-[#2d2f45] rounded-lg">
            {loading ? (
              <Loader2 className="w-4 h-4 text-violet-400 shrink-0 animate-spin" />
            ) : (
              <Search className="w-4 h-4 text-violet-400 shrink-0" />
            )}
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={scope === 'file' ? `Symbols in ${fileName || 'file'}...` : 'Search symbols across all workspace files...'}
              className="flex-1 bg-transparent text-xs text-white placeholder:text-zinc-600 focus:outline-none font-mono"
              id="goto-symbol-input"
              autoComplete="off"
              spellCheck={false}
            />
            <span className="text-[10px] text-zinc-500 bg-white/5 px-1.5 py-0.5 rounded font-mono shrink-0">
              ESC
            </span>
          </div>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1 scrollbar-thin">
          {!loading && scope === 'file' && !activeFilePath && (
            <div className="px-4 py-6 text-xs text-zinc-500 text-center italic">
              Open a file or switch to Global Workspace Symbols.
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <div className="px-4 py-6 text-xs text-zinc-500 text-center italic">
              {query ? `No symbols match "${query}"` : 'No symbols found.'}
            </div>
          )}
          {filtered.map((sym, idx) => {
            const isSelected = idx === selected;
            const kindLabel = KIND_LABEL[sym.kindName] ?? '?';
            const kindColour = KIND_COLOUR[sym.kindName] ?? 'bg-violet-500/15 text-violet-400 border-violet-500/20';
            return (
              <div
                key={`${sym.file || ''}-${sym.name}-${sym.line}-${idx}`}
                onClick={() => handleSelect(sym)}
                onMouseEnter={() => setSelected(idx)}
                className={`flex items-center gap-2.5 px-3.5 py-2 cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-violet-600/20 border-l-2 border-violet-500'
                    : 'hover:bg-white/5 border-l-2 border-transparent'
                }`}
                id={`goto-symbol-result-${idx}`}
              >
                <SymbolIcon kindName={sym.kindName} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-100 font-mono truncate font-semibold">
                    {sym.name}
                  </div>
                  {sym.file && (
                    <div className="text-[10px] text-zinc-500 font-mono truncate">
                      {sym.file}
                    </div>
                  )}
                </div>
                <span
                  className={`text-[9px] font-bold px-1.5 py-0.5 rounded border font-mono shrink-0 ${kindColour}`}
                >
                  {kindLabel}
                </span>
                <span className="text-[10px] text-zinc-500 font-mono shrink-0">
                  :{sym.line}
                </span>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-3.5 py-2 bg-[#10111a] border-t border-[#2d2f45] flex items-center gap-4 text-[10px] text-zinc-500">
          <span><kbd className="bg-white/10 px-1 rounded text-zinc-300">↑↓</kbd> navigate</span>
          <span><kbd className="bg-white/10 px-1 rounded text-zinc-300">↵</kbd> jump to symbol</span>
          <span><kbd className="bg-white/10 px-1 rounded text-zinc-300">esc</kbd> close</span>
          {filtered.length > 0 && (
            <span className="ml-auto text-zinc-400 font-mono">{filtered.length} symbol{filtered.length !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
    </div>
  );
}

