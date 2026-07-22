import React from 'react';
import { Check, ShieldAlert, AlertTriangle } from 'lucide-react';
import type { ChatMessage } from '../../types/chat';
import { DiffView } from './DiffView';

interface ConfirmDialogProps {
  msg: ChatMessage;
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  hunkDecisions?: Record<string, boolean>;
  onToggleHunk?: (hunkId: string, accepted: boolean) => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  msg,
  onConfirmTool,
  onConfirmPermission,
  onConfirmPortConflict,
  hunkDecisions = {},
  onToggleHunk,
}) => {
  const targetFilename = msg.confirmDiff?.path?.split('/').pop() || msg.confirmDiff?.path || 'file';

  return (
    <div className="w-full my-3 animate-slide-up select-text">
      {/* 1. File Diff Patch Approval */}
      {msg.confirmDiff && (
        <div className="border border-blue-500/40 bg-zinc-900 rounded-lg p-3.5 space-y-3 shadow-lg">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <span className="text-[13px] font-semibold text-zinc-100">
              Apply this change to <span className="font-mono text-blue-300">{targetFilename}</span>?
            </span>
            <span className="px-2 py-0.5 text-[10px] font-semibold uppercase bg-blue-950 text-blue-300 border border-blue-800/60 rounded-full">
              PATCH PENDING
            </span>
          </div>

          {msg.confirmDiff.hunks && msg.confirmDiff.hunks.length > 0 && (
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {msg.confirmDiff.hunks.map((hunk: any, idx: number) => (
                <DiffView
                  key={hunk.id || idx}
                  hunk={hunk}
                  idx={idx}
                  isAccepted={hunkDecisions[hunk.id] ?? true}
                  onToggleHunk={(accepted) => onToggleHunk?.(hunk.id, accepted)}
                />
              ))}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-1 font-sans select-none text-xs">
            <button
              type="button"
              onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
              className="px-3.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold rounded-md border border-zinc-700 cursor-pointer transition-colors"
            >
              Reject
            </button>
            <button
              type="button"
              onClick={() => {
                if (msg.tool_call_id) {
                  const decisions = { ...hunkDecisions };
                  if (msg.confirmDiff?.hunks) {
                    msg.confirmDiff.hunks.forEach((h: any) => {
                      if (decisions[h.id] === undefined) {
                        decisions[h.id] = true;
                      }
                    });
                  }
                  onConfirmTool(msg.tool_call_id, true, decisions);
                }
              }}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-md cursor-pointer transition-colors shadow-sm"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Apply</span>
            </button>
          </div>
        </div>
      )}

      {/* 2. Permission Requests */}
      {msg.isPermissionRequest && (
        <div className="border border-amber-500/40 bg-zinc-900 rounded-lg p-3.5 space-y-3 shadow-lg">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs">
              <ShieldAlert className="w-4 h-4" />
              <span>Security Permission Required</span>
            </div>
          </div>
          <div className="space-y-2 text-[12px] text-zinc-300">
            <p>The agent is requesting to run the following shell command:</p>
            <pre className="p-2.5 bg-zinc-950 rounded border border-zinc-800 font-mono text-[11px] select-all overflow-x-auto text-zinc-200">
              {msg.permissionCommand}
            </pre>
            {msg.permissionExplanation && (
              <p className="text-zinc-400 italic text-[11px]">Reason: {msg.permissionExplanation}</p>
            )}
            <div className="flex items-center gap-2 pt-1 font-sans text-xs">
              <button
                type="button"
                onClick={() => msg.tool_call_id && onConfirmPermission?.(msg.tool_call_id, true, 'once', msg.permissionCommand || '')}
                className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-md cursor-pointer text-center"
              >
                Allow Once
              </button>
              <button
                type="button"
                onClick={() => msg.tool_call_id && onConfirmPermission?.(msg.tool_call_id, true, 'project', msg.permissionCommand || '')}
                className="flex-1 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-semibold rounded-md border border-zinc-700 cursor-pointer text-center"
              >
                Allow Project
              </button>
              <button
                type="button"
                onClick={() => msg.tool_call_id && onConfirmPermission?.(msg.tool_call_id, false, 'once', '')}
                className="px-3 py-1.5 bg-red-950 hover:bg-red-900 text-red-300 font-semibold rounded-md border border-red-800 cursor-pointer text-center"
              >
                Deny
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3. Port Conflicts */}
      {msg.isPortConflictRequest && (
        <div className="border border-red-500/40 bg-zinc-900 rounded-lg p-3.5 space-y-3 shadow-lg">
          <div className="flex items-center gap-2 text-red-400 font-semibold text-xs border-b border-zinc-800 pb-2">
            <AlertTriangle className="w-4 h-4" />
            <span>Port Conflict Detected</span>
          </div>
          <div className="space-y-2 text-[12px] text-zinc-300">
            <p>
              Port <span className="font-mono text-red-400 font-bold">{msg.portConflictPort}</span> is in use by{' '}
              <span className="font-semibold">{msg.portConflictProcessName}</span> (PID: {msg.portConflictPid}).
            </p>
            <div className="flex flex-col gap-2 pt-1 font-sans text-xs">
              <button
                type="button"
                onClick={() => msg.tool_call_id && onConfirmPortConflict?.(msg.tool_call_id, 'stop')}
                className="w-full py-1.5 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-md cursor-pointer text-center"
              >
                Stop Process (PID: {msg.portConflictPid})
              </button>
              <button
                type="button"
                onClick={() => msg.tool_call_id && onConfirmPortConflict?.(msg.tool_call_id, 'next_port')}
                className="w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-md cursor-pointer text-center"
              >
                Use Next Available Port
              </button>
              <button
                type="button"
                onClick={() => msg.tool_call_id && onConfirmPortConflict?.(msg.tool_call_id, 'cancel')}
                className="w-full py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 rounded-md border border-zinc-700 cursor-pointer text-center"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Fallback Generic Confirmation */}
      {!msg.confirmDiff && !msg.isPermissionRequest && !msg.isPortConflictRequest && (
        <div className="border border-amber-500/40 bg-zinc-900 rounded-lg p-3.5 space-y-3 shadow-lg">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
            <span className="text-[12px] font-semibold text-zinc-100">Confirmation Required</span>
          </div>
          <pre className="p-2 bg-zinc-950 rounded border border-zinc-800 font-mono text-[11px] text-zinc-300 max-h-36 overflow-y-auto">
            {typeof msg.confirmArgs === 'string' ? msg.confirmArgs : JSON.stringify(msg.confirmArgs, null, 2)}
          </pre>
          <div className="flex items-center justify-end gap-2 font-sans text-xs">
            <button
              type="button"
              onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
              className="px-3.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold rounded-md border border-zinc-700 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, true)}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-md cursor-pointer"
            >
              Confirm
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
