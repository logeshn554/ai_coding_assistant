import React from 'react';
import type { DiffHunk } from '../../types/chat';

interface DiffViewProps {
  filename?: string;
  hunks?: DiffHunk[];
  // Backward compatibility props for single hunk inline confirmation
  hunk?: any;
  idx?: number;
  isAccepted?: boolean;
  onToggleHunk?: (accepted: boolean) => void;
}

export const DiffView: React.FC<DiffViewProps> = ({
  filename,
  hunks,
  hunk,
  idx = 0,
  isAccepted = true,
  onToggleHunk,
}) => {
  // If single hunk object passed in, normalize to DiffHunk format
  const effectiveHunks: DiffHunk[] = hunks || (hunk ? [{
    type: 'context',
    content: hunk.lines ? hunk.lines.join('\n') : String(hunk.content || '')
  }] : []);

  // Compute addition and deletion counts
  let addCount = 0;
  let removeCount = 0;

  effectiveHunks.forEach(h => {
    if (h.type === 'add') addCount++;
    else if (h.type === 'remove') removeCount++;
    else if (h.content) {
      const lines = h.content.split('\n');
      lines.forEach(l => {
        if (l.startsWith('+')) addCount++;
        else if (l.startsWith('-')) removeCount++;
      });
    }
  });

  return (
    <div className="border border-zinc-800 bg-zinc-950 rounded-lg overflow-hidden text-[11.5px] font-mono my-2.5 shadow-sm">
      {/* Header Row */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-900 border-b border-zinc-800 select-none font-sans text-xs">
        <span className="text-zinc-200 font-semibold font-mono truncate max-w-[200px]" title={filename || `Hunk #${idx + 1}`}>
          {filename || `Hunk #${idx + 1}`}
        </span>
        <div className="flex items-center gap-2 font-mono text-[11px]">
          <span className="text-green-400 font-semibold">+{addCount}</span>
          <span className="text-red-400 font-semibold">-{removeCount}</span>

          {onToggleHunk && (
            <div className="flex items-center gap-1 ml-2 font-sans text-[10px]">
              <button
                type="button"
                onClick={() => onToggleHunk(false)}
                className={`px-2 py-0.5 rounded transition-colors font-semibold cursor-pointer ${
                  !isAccepted ? 'bg-red-950 text-red-300 border border-red-800/60' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Reject
              </button>
              <button
                type="button"
                onClick={() => onToggleHunk(true)}
                className={`px-2 py-0.5 rounded transition-colors font-semibold cursor-pointer ${
                  isAccepted ? 'bg-green-950 text-green-300 border border-green-800/60' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Accept
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Code Hunk Lines Container */}
      <div className="max-h-[240px] overflow-y-auto p-2 space-y-0.5 bg-zinc-950 select-text scrollbar-thin">
        {effectiveHunks.map((h, hIdx) => {
          const lines = h.content ? h.content.split('\n') : [];

          return (
            <div key={hIdx} className="space-y-0.5">
              {lines.map((line, lIdx) => {
                let bgClass = 'text-zinc-400';
                if (h.type === 'add' || line.startsWith('+')) {
                  bgClass = 'bg-green-950/60 text-green-300 px-1 rounded-sm';
                } else if (h.type === 'remove' || line.startsWith('-')) {
                  bgClass = 'bg-red-950/60 text-red-300 px-1 rounded-sm';
                }

                return (
                  <div key={lIdx} className={`${bgClass} whitespace-pre break-all`}>
                    {line}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
};
