import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

interface ThinkingPillProps {
  content: string;
  durationMs?: number;
}

export const ThinkingPill: React.FC<ThinkingPillProps> = ({ content, durationMs }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const secs = durationMs ? (durationMs / 1000).toFixed(0) : '13';

  return (
    <div className="w-full my-2 font-sans select-none">
      {/* Toggle Pill */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-medium transition-all duration-200 cursor-pointer hover:scale-[1.02]"
        style={{
          background: isExpanded ? 'rgba(124,106,240,0.12)' : 'rgba(255,255,255,0.04)',
          color: isExpanded ? '#a78bfa' : '#757c87',
          border: isExpanded ? '1px solid rgba(124,106,240,0.2)' : '1px solid rgba(255,255,255,0.06)',
          fontFamily: 'Inter, sans-serif',
        }}
      >
        {/* Animated spark dot */}
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: isExpanded ? '#a78bfa' : '#757c87' }}
        />
        <span>Thought for {secs}s</span>
        <ChevronDown
          className="w-3 h-3 shrink-0 transition-transform duration-200"
          style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
        />
      </button>

      {/* Expanded thinking content */}
      {isExpanded && (
        <div
          className="mt-2 p-4 rounded-2xl select-text overflow-y-auto"
          style={{
            background: 'rgba(124,106,240,0.04)',
            border: '1px solid rgba(124,106,240,0.1)',
            maxHeight: '260px',
            scrollbarWidth: 'thin',
            scrollbarColor: 'rgba(255,255,255,0.08) transparent',
            animation: 'slide-in-up 0.18s ease-out',
          }}
        >
          <pre
            className="text-[12px] leading-relaxed whitespace-pre-wrap"
            style={{
              color: '#aeb6c2',
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            }}
          >
            {content.trim()}
          </pre>
        </div>
      )}
    </div>
  );
};
