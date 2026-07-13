import { useState, useEffect, useRef } from 'react';
import { Search, Loader2, FileText } from 'lucide-react';


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
    <div className="h-full flex flex-col bg-[#181818] text-[#cccccc] font-sans">
      
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-[#2d2d2d] bg-[#181818] shrink-0 flex items-center justify-between select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Search Codebase</span>
      </div>

      {/* Input */}
      <div className="p-2.5 border-b border-[#2d2d2d] bg-[#131313] shrink-0 flex flex-col gap-1.5 select-none">
        <div className={`relative flex items-center bg-[#1e1e1e] border px-2 py-1 gap-2 transition-colors rounded-none ${validationError ? 'border-amber-500/50' : 'border-[#2d2d2d] focus-within:border-[#8b5cf6]/50'}`}>
          <Search className="w-3.5 h-3.5 text-gray-500 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search text in workspace..."
            className="w-full bg-transparent text-xs text-white focus:outline-none placeholder:text-gray-650"
            autoFocus
          />
          {loading && <Loader2 className="w-3.5 h-3.5 text-violet-400 animate-spin shrink-0" />}
        </div>
        {validationError && (
          <span className="text-[9px] text-amber-400/90 font-medium px-1 font-sans">
            ⚠️ {validationError}
          </span>
        )}
      </div>

      {/* Results Feed */}
      <div className="flex-1 overflow-y-auto py-1.5 select-none">
        {debouncedQuery && results.length === 0 && !loading && (
          <div className="px-3 py-8 text-center text-xs text-gray-500 font-sans">
            No results found
          </div>
        )}
        
        {!debouncedQuery && (
          <div className="px-3 py-8 text-center text-xs text-gray-500 font-sans">
            Type query above to search files
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
                className="flex items-center gap-1.5 px-3 py-0.5 hover:bg-white/5 cursor-pointer text-gray-300 font-sans"
              >
                <FileText className="w-3.5 h-3.5 text-violet-400 shrink-0" />
                <span className="text-xs font-medium truncate" title={filePath}>{fileName}</span>
                <span className="text-[9px] text-gray-550 shrink-0 ml-auto bg-[#1e1e1e] border border-[#2d2d2d] px-1 py-0.2 rounded-none font-mono">
                  {fileMatches.length}
                </span>
              </div>
              
              {/* Matching Lines list */}
              <div className="mt-0.5">
                {fileMatches.map((match, idx) => (
                  <div
                    key={`${filePath}_line_${match.line}_${idx}`}
                    onClick={() => onSelectFile(match.path)}
                    className="flex items-start gap-2 py-0.5 pl-6 pr-3 hover:bg-white/10 cursor-pointer font-mono text-[9px]"
                  >
                    <span className="text-violet-405/85 w-6 text-right shrink-0 select-none">
                      {match.line}
                    </span>
                    <span className="text-gray-400 truncate whitespace-nowrap block select-text font-mono" title={match.content}>
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