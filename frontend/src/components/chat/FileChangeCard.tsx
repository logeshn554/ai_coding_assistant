import React from 'react';
import { FileCode, Check, X, FolderOpen, GitBranch } from 'lucide-react';
import type { ChatMessage } from '../../types/chat';

interface FileChangeCardProps {
  filePath: string;
  filename: string;
  status: 'Created' | 'Modified';
  linesAdded?: number;
  linesRemoved?: number;
  isPending: boolean;
  isDiffActive: boolean;
  onToggleDiff: () => void;
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  hunkDecisions?: Record<string, boolean>;
  onOpenFile?: (path: string) => void;
  confirmMessage?: ChatMessage;
}

function getFileStyle(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'html': case 'htm':
      return { color: '#f05032', label: 'HTML' };
    case 'css': case 'scss':
      return { color: '#38bdf8', label: 'CSS' };
    case 'js': case 'jsx':
      return { color: '#eab308', label: 'JS' };
    case 'ts': case 'tsx':
      return { color: '#3178c6', label: 'TS' };
    case 'py':
      return { color: '#3776ab', label: 'Python' };
    default:
      return { color: '#aeb6c2', label: 'Code' };
  }
}

export const FileChangeCard: React.FC<FileChangeCardProps> = ({
  filePath,
  filename,
  status,
  linesAdded = 0,
  linesRemoved = 0,
  isPending,
  isDiffActive,
  onToggleDiff,
  onConfirmTool,
  hunkDecisions = {},
  onOpenFile,
  confirmMessage,
}) => {
  const fileStyle = getFileStyle(filename);

  const handleOpen = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onOpenFile) {
      onOpenFile(filePath);
    }
  };

  const handleAccept = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmMessage?.tool_call_id) {
      const decisions = { ...hunkDecisions };
      if (confirmMessage.confirmDiff?.hunks) {
        confirmMessage.confirmDiff.hunks.forEach((h: any) => {
          if (decisions[h.id] === undefined) {
            decisions[h.id] = true;
          }
        });
      }
      onConfirmTool(confirmMessage.tool_call_id, true, decisions);
    }
  };

  const handleReject = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmMessage?.tool_call_id) {
      onConfirmTool(confirmMessage.tool_call_id, false);
    }
  };

  return (
    <div
      className={`border rounded-xl p-3 bg-[#1e1f24]/50 flex flex-col justify-between transition-all duration-150 shadow-sm font-sans hover:bg-[#1e1f24] hover:border-zinc-700/60 min-h-[110px] ${
        isDiffActive ? 'border-blue-500/40 ring-1 ring-blue-500/20' : 'border-zinc-800/80'
      }`}
    >
      {/* File Info Header */}
      <div className="flex items-start gap-2.5 min-w-0">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border border-zinc-800"
          style={{ background: 'rgba(255,255,255,0.02)' }}
        >
          <FileCode className="w-4 h-4 shrink-0" style={{ color: fileStyle.color }} />
        </div>
        <div className="flex flex-col min-w-0">
          <span className="font-semibold text-zinc-200 text-[12.5px] truncate" title={filename}>
            {filename}
          </span>
          <span className="text-[10px] text-zinc-500 truncate" title={filePath}>
            {fileStyle.label}
          </span>
        </div>
      </div>

      {/* Stats/Status middle section */}
      <div className="flex items-center justify-between mt-2.5 mb-2 font-mono text-[10.5px]">
        <span
          className={`text-[9px] font-bold uppercase ${
            status === 'Created' ? 'text-green-400' : 'text-blue-400'
          }`}
        >
          {status}
        </span>
        {linesAdded > 0 || linesRemoved > 0 ? (
          <div className="flex items-center gap-1">
            {linesAdded > 0 && <span className="text-green-400">+{linesAdded}</span>}
            {linesRemoved > 0 && <span className="text-red-400">-{linesRemoved}</span>}
            <span className="text-zinc-600 font-sans">lines</span>
          </div>
        ) : (
          <span className="text-zinc-600 font-sans">modified</span>
        )}
      </div>

      {/* Action Buttons Footer */}
      <div className="flex flex-col gap-1.5 mt-auto">
        <div className="grid grid-cols-2 gap-1.5">
          {onOpenFile && (
            <button
              type="button"
              onClick={handleOpen}
              className="btn-interactive flex items-center justify-center gap-1 py-1 rounded-md text-[10.5px] font-semibold bg-zinc-900/50 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 cursor-pointer transition-colors"
            >
              <FolderOpen className="w-3.5 h-3.5 shrink-0" />
              <span>Open</span>
            </button>
          )}

          <button
            type="button"
            onClick={onToggleDiff}
            className={`btn-interactive flex items-center justify-center gap-1 py-1 rounded-md text-[10.5px] font-semibold border cursor-pointer transition-colors ${
              isDiffActive
                ? 'bg-blue-950/40 text-blue-300 border-blue-800/60'
                : 'bg-zinc-900/50 hover:bg-zinc-800 text-zinc-300 hover:text-white border-zinc-800'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5 shrink-0" />
            <span>Diff</span>
          </button>
        </div>

        {isPending && (
          <div className="grid grid-cols-2 gap-1.5 border-t border-zinc-800/80 pt-1.5 mt-1">
            <button
              type="button"
              onClick={handleReject}
              className="btn-interactive flex items-center justify-center gap-1 py-1 rounded-md text-[10.5px] font-semibold bg-red-950/20 hover:bg-red-950/50 text-red-400 hover:text-red-300 border border-red-900/20 cursor-pointer transition-colors"
            >
              <X className="w-3 h-3" />
              <span>Reject</span>
            </button>
            <button
              type="button"
              onClick={handleAccept}
              className="btn-interactive flex items-center justify-center gap-1 py-1 rounded-md text-[10.5px] font-semibold bg-green-950/20 hover:bg-green-950/50 text-green-400 hover:text-green-300 border border-green-900/20 cursor-pointer transition-colors"
            >
              <Check className="w-3 h-3" />
              <span>Accept</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
