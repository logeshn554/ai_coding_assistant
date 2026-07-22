import React, { useState } from 'react';
import { Clock, ChevronRight } from 'lucide-react';

interface ThinkingPillProps {
  content: string;
  durationMs?: number;
}

export const ThinkingPill: React.FC<ThinkingPillProps> = ({ content, durationMs }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  // Format duration in seconds
  const formattedSeconds = durationMs ? (durationMs / 1000).toFixed(0) : '13';

  return (
    <div className="w-full my-2 font-sans select-none">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer shadow-sm"
      >
        <Clock className="w-3 h-3 text-zinc-400 shrink-0" />
        <span>Worked for {formattedSeconds}s</span>
        <ChevronRight
          className={`w-3 h-3 text-zinc-400 shrink-0 transition-transform duration-200 ${
            isExpanded ? 'rotate-90' : 'rotate-0'
          }`}
        />
      </button>

      {isExpanded && (
        <div className="mt-2 p-3 bg-zinc-950 border border-zinc-800 rounded-lg font-mono text-[11px] text-zinc-400 whitespace-pre-wrap select-text max-h-60 overflow-y-auto scrollbar-thin animate-slide-down">
          {content.trim()}
        </div>
      )}
    </div>
  );
};
