import React from 'react';
import { Eye, EyeOff } from 'lucide-react';

interface SearchBarProps {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  showHidden: boolean;
  setShowHidden: (show: boolean) => void;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  searchTerm,
  setSearchTerm,
  showHidden,
  setShowHidden,
}) => {
  return (
    <div className="flex items-center gap-1 mt-2">
      <div className="relative flex-1">
        <input
          type="text"
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          placeholder="Filter files..."
          className="w-full bg-[#1e2330] text-gray-200 placeholder-gray-500 text-[11px] px-2 py-1 rounded border border-[#2a3142] focus:border-[#4C8DFF] focus:outline-none transition-colors"
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white text-[10px] cursor-pointer"
          >
            ×
          </button>
        )}
      </div>
      <button
        onClick={() => setShowHidden(!showHidden)}
        title={showHidden ? 'Hide dotfiles & build dirs' : 'Show dotfiles & build dirs'}
        className={`p-1 rounded cursor-pointer transition-colors ${
          showHidden
            ? 'bg-[#4C8DFF]/20 text-[#4C8DFF] border border-[#4C8DFF]/30'
            : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
        }`}
      >
        {showHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
};
