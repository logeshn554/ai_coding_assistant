import React, { useState } from 'react';
import { Check, X, FileCode, ChevronDown, ChevronUp, Eye, Sparkles } from 'lucide-react';

interface FileChangesReviewBarProps {
  pendingFiles: string[];
  onApplyChanges: () => void;
  onDiscardChanges: () => void;
  onReviewFileDiff?: (filePath: string) => void;
}

export const FileChangesReviewBar: React.FC<FileChangesReviewBarProps> = ({
  pendingFiles,
  onApplyChanges,
  onDiscardChanges,
  onReviewFileDiff
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!pendingFiles || pendingFiles.length === 0) return null;

  return (
    <div className="w-full bg-gradient-to-r from-[#1A1B1E]/90 via-[#2B2D30]/80 to-zinc-900 border-b border-[#4C8DFF]/30 p-3 shadow-xl backdrop-blur-md transition-all animate-fadeIn z-30">
      <div className="flex items-center justify-between gap-3">
        {/* Left Side Info */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-[#3B7AE8]/20 border border-[#4C8DFF]/30 text-[#4C8DFF] shrink-0">
            <Sparkles className="w-4 h-4 animate-pulse" />
          </div>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white tracking-wide">
                Agent File Changes Pending Review
              </span>
              <span className="px-2 py-0.5 rounded-full bg-[#4C8DFF]/20 border border-[#4C8DFF]/30 text-[10px] font-mono text-[#4C8DFF] font-semibold">
                {pendingFiles.length} {pendingFiles.length === 1 ? 'file' : 'files'} modified
              </span>
            </div>
            <span className="text-[11px] text-zinc-300 truncate">
              The AI agent finished writing changes to your workspace. Apply changes to commit or discard to revert.
            </span>
          </div>
        </div>

        {/* Right Side Action Buttons */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-zinc-300 border border-white/10 transition-colors cursor-pointer"
            title="Toggle File List"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span className="hidden sm:inline font-medium">Files</span>
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          <button
            onClick={onDiscardChanges}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30 text-xs font-semibold transition-colors cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
            <span>Discard Changes</span>
          </button>

          <button
            onClick={onApplyChanges}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-all shadow-md shadow-emerald-950/50 cursor-pointer"
          >
            <Check className="w-4 h-4" />
            <span>Apply Changes</span>
          </button>
        </div>
      </div>

      {/* Expanded File List */}
      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-[#4C8DFF]/20 max-h-48 overflow-y-auto space-y-1.5 pr-1">
          {pendingFiles.map((file) => (
            <div
              key={file}
              className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-xs font-mono text-zinc-200 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-2 truncate">
                <FileCode className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0" />
                <span className="truncate">{file}</span>
              </div>
              {onReviewFileDiff && (
                <button
                  onClick={() => onReviewFileDiff(file)}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-[#3B7AE8]/20 hover:bg-[#3B7AE8]/30 text-[#4C8DFF] border border-[#4C8DFF]/30 text-[11px] font-sans font-medium cursor-pointer"
                >
                  <Eye className="w-3 h-3" />
                  <span>Review Diff</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
