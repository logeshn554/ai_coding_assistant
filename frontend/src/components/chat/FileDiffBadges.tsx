import React from "react";

export type FileDiffItem = {
  file: string;
  add?: number;
  del?: number;
};

interface FileDiffBadgesProps {
  diffs: FileDiffItem[];
  className?: string;
}

export const FileDiffBadges: React.FC<FileDiffBadgesProps> = ({ diffs, className = "" }) => {
  if (!diffs || diffs.length === 0) return null;

  return (
    <div className={`mt-3 flex flex-wrap gap-2 animate-[fadeIn_150ms_ease-out] ${className}`}>
      {diffs.map((d, idx) => {
        const hasAdd = (d.add ?? 0) > 0;
        const hasDel = (d.del ?? 0) > 0;

        return (
          <div
            key={`${d.file}-${idx}`}
            className="inline-flex items-center gap-2 rounded-lg bg-[#1f2024] border border-zinc-800/80 px-3 py-1.5 font-mono text-[12px] text-zinc-200 shadow-sm transition-all hover:border-zinc-700/80 hover:bg-[#25262c]"
          >
            <span className="font-medium text-zinc-200">{d.file}</span>
            {hasAdd && (
              <span className="font-semibold text-emerald-400">
                +{d.add}
              </span>
            )}
            {hasDel && (
              <span className="font-semibold text-rose-400">
                -{d.del}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
};
