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
}

interface GoToSymbolProps {
  isOpen: boolean;
  onClose: () => void;
  activeFilePath: string | null;
  onRevealLine: (line: number, col?: number) => void;
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
}: GoToSymbolProps) {
  const [query, setQuery] = useState('');
  const [symbols, setSymbols] = useState<WorkspaceSymbol[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Load symbols when opened or file changes
  useEffect(() => {
    if (!isOpen || !activeFilePath) return;
    setQuery('');
    setSelected(0);
    setSymbols([]);
    setLoading(true);
    setTimeout(() => inputRef.current?.focus(), 20);

    fetch(`/api/workspace/symbols?path=${encodeURIComponent(activeFilePath)}`)
      .then((res) => res.json())
      .then((data) => setSymbols(data.symbols || []))
      .catch(() => setSymbols([]))
      .finally(() => setLoading(false));
  }, [isOpen, activeFilePath]);

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.children[selected] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  const filtered = query.trim()
    ? symbols.filter((s) => s.name.toLowerCase().includes(query.toLowerCase()))
    : symbols;

  const handleSelect = useCallback(
    (sym: WorkspaceSymbol) => {
      onRevealLine(sym.line, sym.col);
      onClose();
    },
    [onRevealLine, onClose]
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
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-16 bg-black/60 backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-[520px] max-w-[95vw] bg-[#1a1b26] border border-[#2d2f45] rounded-lg shadow-2xl shadow-black/60 overflow-hidden animate-in fade-in slide-in-from-top-3 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-b border-[#2d2f45] bg-[#13141f]">
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
            placeholder={`Symbols in ${fileName}…`}
            className="flex-1 bg-transparent text-sm text-white placeholder:text-gray-500 focus:outline-none font-mono"
            id="goto-symbol-input"
            autoComplete="off"
            spellCheck={false}
          />
          <span className="text-[10px] text-gray-600 bg-white/5 px-1.5 py-0.5 rounded font-mono shrink-0">
            ESC
          </span>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1 scrollbar-thin">
          {!loading && !activeFilePath && (
            <div className="px-4 py-5 text-sm text-gray-500 text-center italic">
              Open a file to browse its symbols.
            </div>
          )}
          {!loading && activeFilePath && filtered.length === 0 && (
            <div className="px-4 py-5 text-sm text-gray-500 text-center italic">
              {query ? `No symbols match "${query}"` : 'No symbols found in this file.'}
            </div>
          )}
          {filtered.map((sym, idx) => {
            const isSelected = idx === selected;
            const kindLabel = KIND_LABEL[sym.kindName] ?? '?';
            const kindColour = KIND_COLOUR[sym.kindName] ?? 'bg-violet-500/15 text-violet-400 border-violet-500/20';
            return (
              <div
                key={`${sym.name}-${sym.line}`}
                onClick={() => handleSelect(sym)}
                onMouseEnter={() => setSelected(idx)}
                className={`flex items-center gap-2.5 px-3.5 py-1.5 cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-violet-600/20 border-l-2 border-violet-500'
                    : 'hover:bg-white/5 border-l-2 border-transparent'
                }`}
                id={`goto-symbol-result-${idx}`}
              >
                <SymbolIcon kindName={sym.kindName} />
                <span className="flex-1 text-sm text-gray-200 font-mono truncate">
                  {sym.name}
                </span>
                <span
                  className={`text-[9px] font-bold px-1 py-0.5 rounded border font-mono shrink-0 ${kindColour}`}
                >
                  {kindLabel}
                </span>
                <span className="text-[10px] text-gray-600 font-mono shrink-0">
                  :{sym.line}
                </span>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-3.5 py-1.5 bg-[#13141f] border-t border-[#2d2f45] flex items-center gap-4 text-[10px] text-gray-600">
          <span><kbd className="bg-white/10 px-1 rounded">↑↓</kbd> navigate</span>
          <span><kbd className="bg-white/10 px-1 rounded">↵</kbd> jump</span>
          <span><kbd className="bg-white/10 px-1 rounded">esc</kbd> close</span>
          {filtered.length > 0 && (
            <span className="ml-auto">{filtered.length} symbol{filtered.length !== 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
    </div>
  );
}
