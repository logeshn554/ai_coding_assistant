import { useState, useEffect } from 'react';
import { Search, Loader2, FileText } from 'lucide-react';

interface SearchMatch {
  path: string;
  line: number;
  content: string;
}

interface SearchSidebarProps {
  onSelectFile: (path: string) => void;
}

import { useRef } from 'react';

export default function SearchSidebar({ onSelectFile }: SearchSidebarProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchMatch[]>([]);
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [validationError, setValidationError] = useState('');
  
  // In-memory query results cache
  const searchCacheRef = useRef<Record<string, SearchMatch[]>>({});

  // Debounce search input and validate whitespace
  useEffect(() => {
    if (query && !query.trim()) {
      setValidationError('Search query cannot be whitespace only.');
      return;
    }
    setValidationError('');
    
    const timer = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  // Run search when debounced query changes
  useEffect(() => {
    const runSearch = async () => {
      const trimmed = debouncedQuery.trim();
      if (!trimmed) {
        setResults([]);
        return;
      }

      // Check cache first
      if (searchCacheRef.current[trimmed]) {
        setResults(searchCacheRef.current[trimmed]);
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(`/api/files/search?query=${encodeURIComponent(trimmed)}`);
        if (res.ok) {
          const data = await res.json();
          searchCacheRef.current[trimmed] = data;
          setResults(data);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    runSearch();
  }, [debouncedQuery]);

  // Group results by file path
  const groupedResults = results.reduce<Record<string, SearchMatch[]>>((acc, match) => {
    if (!acc[match.path]) {
      acc[match.path] = [];
    }
    acc[match.path].push(match);
    return acc;
  }, {});

  return (
    <div className="h-full flex flex-col bg-[#0e1014] text-gray-300">
      
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 bg-[#111318] shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Search Codebase</span>
      </div>

      {/* Input */}
      <div className="p-3 border-b border-white/5 bg-[#0e1014] shrink-0 flex flex-col gap-1.5">
        <div className={`relative flex items-center bg-[#171922] border rounded px-2.5 py-1.5 gap-2 transition-colors ${validationError ? 'border-amber-500/50' : 'border-white/5 hover:border-white/10'}`}>
          <Search className="w-4 h-4 text-gray-500 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search text in workspace..."
            className="w-full bg-transparent text-xs text-white focus:outline-none"
            autoFocus
          />
          {loading && <Loader2 className="w-3.5 h-3.5 text-violet-400 animate-spin shrink-0" />}
        </div>
        {validationError && (
          <span className="text-[10px] text-amber-400/90 font-medium px-1 animate-pulse-subtle">
            ⚠️ {validationError}
          </span>
        )}
      </div>

      {/* Results Feed */}
      <div className="flex-1 overflow-y-auto py-2">
        {debouncedQuery && results.length === 0 && !loading && (
          <div className="px-4 py-8 text-center text-xs text-gray-600">
            No results found
          </div>
        )}
        
        {!debouncedQuery && (
          <div className="px-4 py-8 text-center text-xs text-gray-600">
            Type something above to search files
          </div>
        )}

        {Object.keys(groupedResults).map((filePath) => {
          const fileMatches = groupedResults[filePath];
          const fileName = filePath.split('/').pop() || filePath;
          
          return (
            <div key={filePath} className="mb-2">
              {/* File Title Bar */}
              <div 
                onClick={() => onSelectFile(filePath)}
                className="flex items-center gap-1.5 px-3 py-1 hover:bg-white/5 cursor-pointer text-gray-300"
              >
                <FileText className="w-3.5 h-3.5 text-violet-400 shrink-0" />
                <span className="text-xs font-medium truncate" title={filePath}>{fileName}</span>
                <span className="text-[10px] text-gray-500 shrink-0 ml-auto bg-white/5 px-1.5 py-0.2 rounded-full">
                  {fileMatches.length}
                </span>
              </div>
              
              {/* Matching Lines list */}
              <div className="mt-0.5">
                {fileMatches.map((match, idx) => (
                  <div
                    key={`${filePath}_line_${match.line}_${idx}`}
                    onClick={() => onSelectFile(match.path)}
                    className="flex items-start gap-3 py-1 pl-8 pr-3 hover:bg-white/10 cursor-pointer font-mono text-[10px] transition-colors"
                  >
                    <span className="text-violet-400/80 w-6 text-right shrink-0 select-none">
                      {match.line}
                    </span>
                    <span className="text-gray-400 truncate whitespace-nowrap block" title={match.content}>
                      {match.content}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

    </div>
  );
}
