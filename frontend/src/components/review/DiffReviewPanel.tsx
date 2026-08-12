import React, { useState } from 'react';
import { Check, X, FileText, Wrench, Sparkles, CheckCheck } from 'lucide-react';

export interface DiffHunk {
  id: string;
  file: string;
  oldStart: number;
  newStart: number;
  lines: string[];
  category: 'implementation' | 'repair';
  accepted?: boolean;
}

interface DiffReviewPanelProps {
  filesChanged: string[];
  hunks: DiffHunk[];
  onAcceptHunk: (hunkId: string) => void;
  onRejectHunk: (hunkId: string) => void;
  onAcceptAll: () => void;
  onRejectAll: () => void;
}

export const DiffReviewPanel: React.FC<DiffReviewPanelProps> = ({
  filesChanged,
  hunks,
  onAcceptHunk,
  onRejectHunk,
  onAcceptAll,
  onRejectAll,
}) => {
  const [selectedFile, setSelectedFile] = useState<string>(filesChanged[0] || '');

  const filteredHunks = hunks.filter((h) => !selectedFile || h.file === selectedFile);
  const implHunks = filteredHunks.filter((h) => h.category === 'implementation');
  const repairHunks = filteredHunks.filter((h) => h.category === 'repair');

  return (
    <div className="diff-review-panel bg-base-200 border border-base-300 rounded-lg p-4 text-xs font-sans shadow-md">
      {/* Header Controls */}
      <div className="flex items-center justify-between pb-3 border-b border-base-300">
        <div>
          <h3 className="font-semibold text-sm flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-primary" /> Multi-File Change Review
          </h3>
          <p className="text-xs text-base-content/70">
            {filesChanged.length} files changed • {hunks.length} total hunks
          </p>
        </div>

        <div className="flex gap-2">
          <button onClick={onAcceptAll} className="btn btn-xs btn-success gap-1">
            <CheckCheck className="w-3.5 h-3.5" /> Accept All
          </button>
          <button onClick={onRejectAll} className="btn btn-xs btn-outline btn-error gap-1">
            <X className="w-3.5 h-3.5" /> Reject All
          </button>
        </div>
      </div>

      {/* File Selector Tabs */}
      <div className="flex border-b border-base-300 overflow-x-auto my-2 py-1 gap-1">
        {filesChanged.map((f) => (
          <button
            key={f}
            onClick={() => setSelectedFile(f)}
            className={`btn btn-xs ${selectedFile === f ? 'btn-neutral' : 'btn-ghost'} gap-1 font-mono text-[11px]`}
          >
            <FileText className="w-3 h-3" /> {f}
          </button>
        ))}
      </div>

      {/* Categorized Hunks (Implementation vs Repair) */}
      <div className="hunks-list space-y-3 mt-3 max-h-96 overflow-y-auto">
        {/* Implementation Hunks */}
        {implHunks.length > 0 && (
          <div>
            <h4 className="font-semibold text-xs text-info mb-1.5 flex items-center gap-1">
              <span>Implementation Changes</span> ({implHunks.length})
            </h4>
            {implHunks.map((hunk) => (
              <HunkItem key={hunk.id} hunk={hunk} onAccept={onAcceptHunk} onReject={onRejectHunk} />
            ))}
          </div>
        )}

        {/* Repair Hunks */}
        {repairHunks.length > 0 && (
          <div>
            <h4 className="font-semibold text-xs text-warning mb-1.5 flex items-center gap-1">
              <Wrench className="w-3 h-3" /> Self-Repair Fixes ({repairHunks.length})
            </h4>
            {repairHunks.map((hunk) => (
              <HunkItem key={hunk.id} hunk={hunk} onAccept={onAcceptHunk} onReject={onRejectHunk} />
            ))}
          </div>
        )}

        {filteredHunks.length === 0 && (
          <div className="text-center py-4 text-base-content/50 italic">No hunks to review for selected file.</div>
        )}
      </div>
    </div>
  );
};

const HunkItem: React.FC<{ hunk: DiffHunk; onAccept: (id: string) => void; onReject: (id: string) => void }> = ({
  hunk,
  onAccept,
  onReject,
}) => {
  return (
    <div className={`hunk-item border rounded p-2 my-1.5 bg-base-100 font-mono text-[11px] ${hunk.accepted === true ? 'border-success' : hunk.accepted === false ? 'border-error opacity-60' : 'border-base-300'}`}>
      <div className="flex justify-between items-center pb-1 text-[10px] text-base-content/70">
        <span>Hunk @@ -{hunk.oldStart} +{hunk.newStart} @@</span>
        <div className="flex gap-1 font-sans">
          <button onClick={() => onAccept(hunk.id)} className="btn btn-xs btn-ghost text-success px-1.5">
            <Check className="w-3 h-3" /> Accept
          </button>
          <button onClick={() => onReject(hunk.id)} className="btn btn-xs btn-ghost text-error px-1.5">
            <X className="w-3 h-3" /> Reject
          </button>
        </div>
      </div>

      <div className="diff-lines bg-base-300 p-1.5 rounded max-h-36 overflow-x-auto">
        {hunk.lines.map((line, idx) => {
          const isAdd = line.startsWith('+');
          const isDel = line.startsWith('-');
          return (
            <div
              key={idx}
              className={`leading-relaxed ${isAdd ? 'bg-success/20 text-success-content' : isDel ? 'bg-error/20 text-error-content' : 'text-base-content/80'}`}
            >
              {line}
            </div>
          );
        })}
      </div>
    </div>
  );
};
