import React from 'react';

interface DiffViewProps {
  hunk: any;
  idx: number;
  isAccepted: boolean;
  onToggleHunk: (accepted: boolean) => void;
}

export const DiffView: React.FC<DiffViewProps> = ({
  hunk,
  idx,
  isAccepted,
  onToggleHunk,
}) => {
  return (
    <div className="border border-white/5 bg-black/40 rounded-lg overflow-hidden text-[10px] my-2">
      <div className="flex items-center justify-between px-3 py-1.5 bg-white/3 border-b border-white/5 select-none font-sans">
        <span className="text-gray-400 font-semibold uppercase text-[8px] tracking-wider font-mono">Hunk #{idx + 1}</span>
        <div className="flex gap-1.5 text-[8px]">
          <button
            type="button"
            onClick={() => onToggleHunk(false)}
            className={`px-2 py-0.5 rounded transition-all font-bold cursor-pointer focus-visible:ring-1 focus-visible:ring-red-500 focus-visible:outline-none ${!isAccepted
              ? 'bg-red-500/20 text-red-400 border border-red-500/40 font-bold'
              : 'bg-white/5 text-gray-500 hover:text-gray-300'
              }`}
          >
            Reject
          </button>
          <button
            type="button"
            onClick={() => onToggleHunk(true)}
            className={`px-2 py-0.5 rounded transition-all font-bold cursor-pointer focus-visible:ring-1 focus-visible:ring-emerald-500 focus-visible:outline-none ${isAccepted
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-bold'
              : 'bg-white/5 text-gray-500 hover:text-gray-300'
              }`}
          >
            Accept
          </button>
        </div>
      </div>
      <div className="font-mono text-[9px] overflow-x-auto whitespace-pre p-2 bg-[#09090b] leading-tight select-text scrollbar-thin">
        {hunk.lines && hunk.lines.map((line: string, lineIdx: number) => {
          let lineClass = 'text-gray-400';
          if (line.startsWith('+')) lineClass = 'bg-emerald-500/10 text-emerald-400 px-1';
          else if (line.startsWith('-')) lineClass = 'bg-red-500/10 text-red-400 px-1';
          return (
            <div key={lineIdx} className={lineClass}>
              {line}
            </div>
          );
        })}
      </div>
    </div>
  );
};
