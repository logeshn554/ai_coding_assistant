import React from 'react';
import type { ChatMessage } from '../../types/chat';
import { DiffView } from './DiffView';

interface ConfirmDialogProps {
  msg: ChatMessage;
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  hunkDecisions: Record<string, boolean>;
  onToggleHunk: (hunkId: string, accepted: boolean) => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  msg,
  onConfirmTool,
  onConfirmPermission,
  onConfirmPortConflict,
  hunkDecisions,
  onToggleHunk,
}) => {
  const formatArgs = (args: any) => {
    try {
      if (typeof args === 'string') return args;
      return JSON.stringify(args, null, 2);
    } catch {
      return String(args);
    }
  };

  return (
    <div className="flex gap-2 max-w-[95%] items-start select-text mb-3">
      <div className="w-5 h-5 rounded-sm bg-[#8b5cf6]/20 border border-[#8b5cf6]/40 text-violet-400 shrink-0 flex items-center justify-center text-[9px] font-bold select-none">
        ?
      </div>
      <div className="flex-1 max-w-[calc(100%-1.5rem)] select-text">
        {/* Smart command permission requests */}
        {msg.isPermissionRequest && (
          <div className="border border-yellow-500/25 bg-[#25221a] p-3 space-y-2.5 font-sans text-xs">
            <div className="flex items-center justify-between border-b border-[#2d2d2d] pb-1.5 font-mono select-none">
              <span className="text-[10px] font-bold text-yellow-400">Security Guardrails</span>
              <span className="px-1 text-[8px] font-bold uppercase bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 animate-pulse">
                CONFIRMATION REQUIRED
              </span>
            </div>
            <div className="text-[10px] text-gray-300 space-y-2">
              <p>The agent is requesting permission to execute this shell command:</p>
              <pre className="bg-[#131313] p-2 border border-[#2d2d2d] font-mono text-[9px] select-all overflow-x-auto whitespace-pre-wrap">
                {msg.permissionCommand}
              </pre>
              {msg.permissionExplanation && (
                <p className="text-gray-400 italic">Reason: {msg.permissionExplanation}</p>
              )}
              <div className="grid grid-cols-3 gap-1 pt-1 font-sans select-none text-[9px]">
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmPermission?.(msg.tool_call_id, true, 'once', msg.permissionCommand || '')}
                  className="py-1.5 bg-[#8b5cf6] hover:bg-[#7c4dff] text-white font-bold cursor-pointer text-center rounded-none"
                >
                  Allow Once
                </button>
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmPermission?.(msg.tool_call_id, true, 'project', msg.permissionCommand || '')}
                  className="py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 font-semibold cursor-pointer text-center border border-[#2d2d2d] rounded-none"
                >
                  Allow Project
                </button>
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmPermission?.(msg.tool_call_id, false, 'once', '')}
                  className="py-1.5 bg-red-650/15 border border-red-500/20 text-red-400 font-bold cursor-pointer text-center rounded-none"
                >
                  Deny
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Port conflicts */}
        {msg.isPortConflictRequest && (
          <div className="border border-red-500/25 bg-[#241a1c] p-3 space-y-2.5 font-sans text-xs">
            <div className="flex items-center justify-between border-b border-[#2d2d2d] pb-1.5 font-mono select-none">
              <span className="text-[10px] font-bold text-red-400">Port Conflict Resolution</span>
            </div>
            <div className="text-[10px] text-gray-300 space-y-2">
              <p>Port <span className="font-bold text-red-450">{msg.portConflictPort}</span> is in use by <span className="font-bold text-red-450">{msg.portConflictProcessName}</span> (PID: {msg.portConflictPid}).</p>
              <div className="flex flex-col gap-1 pt-1 select-none font-sans">
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmPortConflict?.(msg.tool_call_id, 'stop')}
                  className="w-full py-1.5 bg-red-650 hover:bg-red-600 text-white font-bold cursor-pointer rounded-none"
                >
                  Stop Process (PID: {msg.portConflictPid})
                </button>
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmPortConflict?.(msg.tool_call_id, 'next_port')}
                  className="w-full py-1.5 bg-[#8b5cf6] hover:bg-[#7c4dff] text-white font-bold cursor-pointer rounded-none"
                >
                  Use Next Available Port
                </button>
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmPortConflict?.(msg.tool_call_id, 'cancel')}
                  className="w-full py-1.5 bg-white/5 hover:bg-white/10 text-gray-400 cursor-pointer rounded-none border border-[#2d2d2d]"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Proposed Diff Hunks */}
        {msg.confirmDiff && (
          <div className="border border-violet-500/25 bg-[#1b1c24] p-3 space-y-2.5 font-sans text-xs">
            <div className="flex items-center justify-between border-b border-[#2d2d2d] pb-1.5 font-mono select-none">
              <span className="text-[10px] font-bold text-violet-300">File Edit: edit_file</span>
              <span className="px-1 text-[8px] font-bold uppercase bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 animate-pulse">
                PENDING APPROVAL
              </span>
            </div>
            <div className="text-[10px] text-gray-300 space-y-1.5">
              <div className="bg-[#131313] p-1.5 border border-[#2d2d2d] font-mono text-[9px] truncate" title={msg.confirmDiff.path}>
                Path: {msg.confirmDiff.path.split('/').pop()} <span className="text-gray-500">({msg.confirmDiff.path})</span>
              </div>
              {msg.confirmDiff.hunks && msg.confirmDiff.hunks.length > 0 && (
                <div className="space-y-1.5">
                  {msg.confirmDiff.hunks.map((hunk: any, idx: number) => (
                    <DiffView
                      key={hunk.id}
                      hunk={hunk}
                      idx={idx}
                      isAccepted={hunkDecisions[hunk.id] ?? true}
                      onToggleHunk={(accepted) => onToggleHunk(hunk.id, accepted)}
                    />
                  ))}
                </div>
              )}
              <div className="flex gap-2 pt-1 font-sans select-none">
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
                  className="flex-1 py-1.5 bg-red-650/15 border border-red-500/20 text-red-400 font-bold rounded-none cursor-pointer"
                >
                  Reject All
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
                  className="flex-1 py-1.5 bg-[#8b5cf6] hover:bg-[#7c4dff] text-white font-bold rounded-none cursor-pointer"
                >
                  Accept All
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Other/Dangerous confirmations */}
        {!msg.isPermissionRequest && !msg.isPortConflictRequest && !msg.confirmDiff && (
          <div className="border border-red-500/25 bg-[#241a1a] p-3 space-y-2.5 font-sans text-xs">
            <div className="flex items-center justify-between border-b border-[#2d2d2d] pb-1.5 font-mono select-none">
              <span className="text-[10px] font-bold text-red-400">Dangerous command execution</span>
            </div>
            <div className="text-[10px] text-gray-300 space-y-2 font-mono">
              <pre className="bg-[#131313] p-2 border border-[#2d2d2d] whitespace-pre-wrap select-all text-[9px] text-gray-400 scrollbar-thin">
                {formatArgs(msg.confirmArgs)}
              </pre>
              <div className="flex gap-1.5 pt-1 font-sans select-none">
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, false)}
                  className="flex-1 py-1.5 bg-white/5 border border-[#2d2d2d] text-gray-300 hover:text-white font-bold cursor-pointer rounded-none"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => msg.tool_call_id && onConfirmTool(msg.tool_call_id, true)}
                  className="flex-1 py-1.5 bg-red-650 hover:bg-red-600 text-white font-bold cursor-pointer rounded-none"
                >
                  Run Command
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
