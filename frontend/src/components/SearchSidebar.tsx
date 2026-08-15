import { useState, useEffect } from 'react';
import {
  Search,
  Loader2,
  FileText,
  ChevronRight,
  ChevronDown,
  Replace,
  Check
} from 'lucide-react';
import { useDebounce } from '../hooks/useDebounce';

interface SearchMatch {
  path: string;
  line: number;
  content: string;
}

interface SearchSidebarProps {
  onSelectFile: (path: string) => void;
}

export default function SearchSidebar({ onSelectFile }: SearchSidebarProps) {
  const [query, setQuery] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [showReplace, setShowReplace] = useState(false);
  const [isCaseSensitive, setIsCaseSensitive] = useState(false);
  const [isWholeWord, setIsWholeWord] = useState(false);
  const [isRegex, setIsRegex] = useState(false);
  const [loading, setLoading] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [replaceStatus, setReplaceStatus] = useState<string | null>(null);
  const [results, setResults] = useState<SearchMatch[]>([]);
  const [collapsedFiles, setCollapsedFiles] = useState<Record<string, boolean>>({});

  const debouncedQuery = useDebounce(query, 250);

  const runSearch = async () => {
    const trimmed = debouncedQuery.trim();
    if (!trimmed) {
      setResults([]);
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams({
        query: trimmed,
        case_sensitive: String(isCaseSensitive),
        whole_word: String(isWholeWord),
        is_regex: String(isRegex)
      });
      const res = await fetch(`/api/files/search?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setResults(data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSearch();
  }, [debouncedQuery, isCaseSensitive, isWholeWord, isRegex]);

  const handleReplaceAll = async () => {
    if (!query.trim()) return;
    setReplacing(true);
    setReplaceStatus(null);
    try {
      const res = await fetch('/api/files/replace-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          replace_text: replaceText,
          case_sensitive: isCaseSensitive,
          whole_word: isWholeWord,
          is_regex: isRegex
        })
      });
      if (res.ok) {
        const data = await res.json();
        setReplaceStatus(`Replaced in ${data.modified_files} files (${data.total_replacements} occurrences)`);
        runSearch();
      }
    } catch (e) {
      console.error(e);
      setReplaceStatus('Replace failed');
    } finally {
      setReplacing(false);
      setTimeout(() => setReplaceStatus(null), 4000);
    }
  };

  const toggleFileCollapse = (path: string) => {
    setCollapsedFiles(prev => ({ ...prev, [path]: !prev[path] }));
  };

  // Group results by file path
  const groupedResults = results.reduce<Record<string, SearchMatch[]>>((acc, match) => {
    if (!acc[match.path]) {
      acc[match.path] = [];
    }
    acc[match.path].push(match);
    return acc;
  }, {});

  const totalMatches = results.length;
  const totalFiles = Object.keys(groupedResults).length;

  return (
    <div className="h-full flex flex-col bg-[#11131A] text-zinc-200 font-sans select-none border-r border-[#2A3146]">
      
      {/* Header */}
      <div className="px-3.5 py-2.5 border-b border-[#2A3146] bg-[#161922] shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Search className="w-4 h-4 text-[#4C8DFF]" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">Search & Replace</span>
        </div>
        <button
          onClick={() => setShowReplace(!showReplace)}
          className={`p-1 rounded-lg transition-colors cursor-pointer ${
            showReplace ? 'bg-purple-600/30 text-purple-300' : 'text-zinc-400 hover:text-white hover:bg-white/10'
          }`}
          title="Toggle Replace in Files"
        >
          <Replace className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Search & Replace Form Box */}
      <div className="p-2.5 border-b border-[#2A3146] bg-[#141620] shrink-0 flex flex-col gap-2">
        
        {/* Search Input */}
        <div className="flex items-center bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 focus-within:border-[#4C8DFF] transition-colors">
          <Search className="w-3.5 h-3.5 text-zinc-500 shrink-0 mr-2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search in codebase..."
            className="w-full bg-transparent text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none font-mono"
            autoFocus
          />
          {loading && <Loader2 className="w-3.5 h-3.5 text-[#4C8DFF] animate-spin shrink-0 ml-1" />}
          
          {/* Options Toggles */}
          <div className="flex items-center gap-0.5 ml-1.5 shrink-0">
            <button
              onClick={() => setIsCaseSensitive(!isCaseSensitive)}
              className={`p-1 rounded text-[11px] font-mono font-bold cursor-pointer transition-colors ${
                isCaseSensitive ? 'bg-[#4C8DFF]/30 text-[#4C8DFF] border border-[#4C8DFF]/40' : 'text-zinc-500 hover:text-zinc-300'
              }`}
              title="Match Case (Alt+C)"
            >
              Aa
            </button>
            <button
              onClick={() => setIsWholeWord(!isWholeWord)}
              className={`p-1 rounded text-[11px] font-mono font-bold cursor-pointer transition-colors ${
                isWholeWord ? 'bg-[#4C8DFF]/30 text-[#4C8DFF] border border-[#4C8DFF]/40' : 'text-zinc-500 hover:text-zinc-300'
              }`}
              title="Match Whole Word (Alt+W)"
            >
              \b
            </button>
            <button
              onClick={() => setIsRegex(!isRegex)}
              className={`p-1 rounded text-[11px] font-mono font-bold cursor-pointer transition-colors ${
                isRegex ? 'bg-[#4C8DFF]/30 text-[#4C8DFF] border border-[#4C8DFF]/40' : 'text-zinc-500 hover:text-zinc-300'
              }`}
              title="Use Regular Expression (Alt+R)"
            >
              .*
            </button>
          </div>
        </div>

        {/* Replace Input (Expandable) */}
        {showReplace && (
          <div className="flex items-center gap-1.5 animate-[fadeIn_150ms_ease-out]">
            <div className="flex-1 flex items-center bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 focus-within:border-purple-500 transition-colors">
              <Replace className="w-3.5 h-3.5 text-zinc-500 shrink-0 mr-2" />
              <input
                type="text"
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
                placeholder="Replace with..."
                className="w-full bg-transparent text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none font-mono"
              />
            </div>
            <button
              onClick={handleReplaceAll}
              disabled={replacing || !query.trim() || totalMatches === 0}
              className="px-2.5 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white rounded-xl text-xs font-bold shrink-0 cursor-pointer shadow-sm transition-all flex items-center gap-1"
              title="Replace All across matches"
            >
              {replacing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
              <span>All</span>
            </button>
          </div>
        )}

        {/* Status Toast */}
        {replaceStatus && (
          <div className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-500/30 px-2 py-1 rounded-lg">
            {replaceStatus}
          </div>
        )}

        {/* Matches summary badge */}
        {query.trim() && !loading && (
          <div className="flex items-center justify-between text-[10px] text-zinc-400 font-mono pt-0.5">
            <span>
              {totalMatches} {totalMatches === 1 ? 'match' : 'matches'} in {totalFiles} {totalFiles === 1 ? 'file' : 'files'}
            </span>
          </div>
        )}
      </div>

      {/* Results Tree */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading && results.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-zinc-500 space-y-2">
            <Loader2 className="w-5 h-5 text-[#4C8DFF] animate-spin" />
            <span className="text-xs">Searching codebase...</span>
          </div>
        ) : query.trim() && totalMatches === 0 && !loading ? (
          <div className="py-12 flex flex-col items-center justify-center text-zinc-500 space-y-1 text-xs">
            <span>No results found for &ldquo;{query}&rdquo;</span>
          </div>
        ) : (
          Object.entries(groupedResults).map(([filePath, matches]) => {
            const isCollapsed = collapsedFiles[filePath] ?? false;
            const fileName = filePath.split(/[/\\]/).pop() || filePath;

            return (
              <div key={filePath} className="border border-white/5 rounded-xl bg-white/[0.02] overflow-hidden">
                {/* File Header Row */}
                <div
                  onClick={() => toggleFileCollapse(filePath)}
                  className="flex items-center justify-between px-2.5 py-1.5 hover:bg-white/[0.05] cursor-pointer transition-colors select-none"
                >
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    {isCollapsed ? (
                      <ChevronRight className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    )}
                    <FileText className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0" />
                    <span className="text-xs font-semibold text-zinc-200 truncate">{fileName}</span>
                    <span className="text-[9px] text-zinc-500 font-mono truncate">{filePath}</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 bg-white/10 rounded-full text-zinc-300 ml-1.5 shrink-0">
                    {matches.length}
                  </span>
                </div>

                {/* Matches List */}
                {!isCollapsed && (
                  <div className="divide-y divide-white/5 border-t border-white/5 bg-black/20 font-mono text-[10.5px]">
                    {matches.map((match, idx) => (
                      <div
                        key={idx}
                        onClick={() => onSelectFile(match.path)}
                        className="flex items-start gap-2 px-3 py-1 hover:bg-[#4C8DFF]/15 hover:text-white cursor-pointer transition-colors text-zinc-300 group"
                      >
                        <span className="text-[#4C8DFF] shrink-0 text-[10px] w-6 text-right font-bold pt-0.5">
                          {match.line}
                        </span>
                        <span className="truncate flex-1 text-zinc-400 group-hover:text-zinc-200">
                          {match.content}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

    </div>
  );
}