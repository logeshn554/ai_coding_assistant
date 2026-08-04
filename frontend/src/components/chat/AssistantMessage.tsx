import React, { useState } from 'react';
import { Check, Copy, Loader2, Sparkles, ChevronRight, FileText, ThumbsUp, ThumbsDown } from 'lucide-react';
import type { ChatMessage, DiffHunk } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ActivityPanel } from './ActivityPanel';
import { FileChangeCard } from './FileChangeCard';
import { ConfirmDialog } from './ConfirmDialog';
import { DiffView } from './DiffView';
import { copyToClipboard } from '../../utils/clipboard';

export interface AiTurn {
  kind: 'ai';
  id: string;
  assistantMessages: ChatMessage[];
  toolMessages: ChatMessage[];
  confirmMessages: ChatMessage[];
  isGenerating?: boolean;
}

interface AssistantMessageProps {
  turn: AiTurn;
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  hunkDecisions: Record<string, Record<string, boolean>>;
  onToggleHunk: (msgId: string, hunkId: string, accepted: boolean) => void;
  onRunCommand?: (command: string) => void;
  onOpenFile?: (path: string) => void;
  statusMessage: string | null;
}

const AssistantMessageComponent: React.FC<AssistantMessageProps> = ({
  turn,
  onConfirmTool,
  onConfirmPermission,
  onConfirmPortConflict,
  hunkDecisions,
  onToggleHunk,
  onRunCommand,
  onOpenFile,
  statusMessage,
}) => {
  const [copied, setCopied] = useState(false);
  const [activeDiffPath, setActiveDiffPath] = useState<string | null>(null);
  const [showFilesList, setShowFilesList] = useState(true);
  const [feedback, setFeedback] = useState<'liked' | 'disliked' | null>(null);

  // Find the primary assistant message containing text content
  const textMessage = turn.assistantMessages.find((m: ChatMessage) => m.content && !m.isConfirmPending) || turn.assistantMessages[0];
  const rawContent = textMessage?.content;
  const elapsed = textMessage?.elapsed_ms;
  
  // Extract and strip thinking tags if present
  const processContent = (raw: any): { visible: string; thinkingContent: string | null } => {
    if (!raw) return { visible: '', thinkingContent: null };
    const str = typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2);
    const match = str.match(/<thinking>([\s\S]*?)<\/thinking>/);
    const thinkingContent = match ? match[1] : null;
    const visible = str.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
    return { visible, thinkingContent };
  };

  const { visible } = processContent(rawContent);

  // Split visible content into main features list and final Summary block if present
  let contentPart = visible;
  let summaryPart: string | null = null;

  const summaryRegex = /(?:^|\n)(?:##|###)?\s*Summary\s*\n([\s\S]*)$/i;
  const summaryMatch = visible.match(summaryRegex);
  if (summaryMatch) {
    summaryPart = summaryMatch[1].trim();
    contentPart = visible.replace(summaryRegex, '').trim();
  }

  // Extract metadata from the main assistant message
  const cost = textMessage?.cost_usd;
  const agentsCount = textMessage?.agents_used;

  // Extract file changes from turn messages
  const fileChangesMap: Record<string, any> = {};

  // 1. Scan confirmMessages (pending diffs)
  turn.confirmMessages.forEach((m: ChatMessage) => {
    if (m.confirmDiff) {
      const path = m.confirmDiff.path;
      const filename = path.split(/[/\\]/).pop() || path;
      const proposedContent = m.confirmDiff.proposed || '';
      const originalContent = m.confirmDiff.original || '';
      const isNew = !originalContent;
      
      let addCount = 0;
      let removeCount = 0;
      if (m.confirmDiff.hunks) {
        m.confirmDiff.hunks.forEach((h: DiffHunk) => {
          if (h.type === 'add') addCount++;
          else if (h.type === 'remove') removeCount++;
          else if (h.content) {
            h.content.split('\n').forEach(line => {
              if (line.startsWith('+')) addCount++;
              else if (line.startsWith('-')) removeCount++;
            });
          }
        });
      } else {
        addCount = proposedContent.split('\n').length;
      }

      fileChangesMap[path] = {
        filePath: path,
        filename,
        status: isNew ? 'Created' : 'Modified',
        linesAdded: addCount,
        linesRemoved: removeCount,
        confirmMessage: m,
      };
    }
  });

  // 2. Scan completed toolMessages for write/edit files
  turn.toolMessages.forEach((m: ChatMessage) => {
    const name = m.name || '';
    if (name.includes('write_file') || name.includes('edit_file') || name.includes('replace_file')) {
      let path = '';
      try {
        const contentStr = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
        const params = JSON.parse(contentStr);
        path = params.TargetFile || params.path || params.AbsolutePath || '';
      } catch {
        // Fallback parse path from parameters
        const match = m.name?.match(/TargetFile='([^']+)'/);
        if (match) path = match[1];
      }

      if (path && !fileChangesMap[path]) {
        const filename = path.split(/[/\\]/).pop() || path;
        const isNew = name.includes('write_file');
        fileChangesMap[path] = {
          filePath: path,
          filename,
          status: isNew ? 'Created' : 'Modified',
          completedToolMessage: m,
        };
      }
    }
  });

  // 3. Scan assistant messages for static diff outputs
  turn.assistantMessages.forEach((m: ChatMessage) => {
    if (m.diff) {
      const path = m.diff.filename;
      if (path && !fileChangesMap[path]) {
        const filename = path.split(/[/\\]/).pop() || path;
        let addCount = 0;
        let removeCount = 0;
        m.diff.hunks.forEach((h: DiffHunk) => {
          if (h.type === 'add') addCount++;
          else if (h.type === 'remove') removeCount++;
          else if (h.content) {
            h.content.split('\n').forEach(line => {
              if (line.startsWith('+')) addCount++;
              else if (line.startsWith('-')) removeCount++;
            });
          }
        });

        fileChangesMap[path] = {
          filePath: path,
          filename,
          status: 'Modified' as const,
          linesAdded: addCount,
          linesRemoved: removeCount,
          completedToolMessage: m,
        };
      }
    }
  });

  const fileChangesList = Object.values(fileChangesMap);

  // Calculate total additions/deletions across all files
  let totalAdded = 0;
  let totalRemoved = 0;
  fileChangesList.forEach((file: any) => {
    totalAdded += file.linesAdded || 0;
    totalRemoved += file.linesRemoved || 0;
  });

  // Separate non-file confirmations (e.g. commands permission, port conflicts)
  const nonFileConfirmations = turn.confirmMessages.filter((m: ChatMessage) => !m.confirmDiff);

  const handleCopy = () => {
    if (contentPart) {
      copyToClipboard(contentPart);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const isExecuting = turn.isGenerating;

  const activeFileChange: any = fileChangesList.find((f: any) => f.filePath === activeDiffPath);
  const activeDiffMessage = activeFileChange?.confirmMessage || activeFileChange?.completedToolMessage;
  
  const [messageTime] = useState(() => {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  });

  return (
    <div className="flex flex-col gap-3.5 mb-6 select-text animate-[fadeIn_150ms_ease-out] font-sans">
      {/* AI Assistant Header Row */}
      <div className="flex items-center justify-between select-none">
        <div className="flex items-center gap-2.5">
          {/* Circular Sparkles Avatar */}
          <div
            className="w-6.5 h-6.5 rounded-full flex items-center justify-center shrink-0 border border-blue-500/35 text-blue-400 shadow-sm"
            style={{
              background: 'linear-gradient(135deg, rgba(76, 141, 255, 0.15) 0%, rgba(30, 41, 59, 0.3) 100%)',
            }}
          >
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <span className="font-bold text-[12.5px] text-zinc-100 tracking-wide">
            DevPilot AI
          </span>
        </div>

        {/* Status indicator badge */}
        <div className="flex items-center gap-2 shrink-0">
          {isExecuting ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-blue-950/30 text-blue-400 border border-blue-900/25">
              <Loader2 className="w-2.5 h-2.5 animate-spin" />
              <span>{statusMessage || 'Generating'}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider bg-emerald-950/20 text-emerald-400 border border-emerald-900/20">
              <span>✓ Completed</span>
              {elapsed !== undefined && (
                <span className="text-[8.5px] font-mono text-zinc-500 lowercase ml-1">
                  ({(elapsed / 1000).toFixed(1)}s)
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 min-w-0 space-y-3.5 pl-0">
        {/* Collapsible Activity panel */}
        <ActivityPanel toolMessages={turn.toolMessages} isGenerating={turn.isGenerating} />

        {/* Non-File Confirmations (Permissions / Port Conflicts) */}
        {nonFileConfirmations.map((m) => (
          <ConfirmDialog
            key={m.id}
            msg={m}
            onConfirmTool={onConfirmTool}
            onConfirmPermission={onConfirmPermission}
            onConfirmPortConflict={onConfirmPortConflict}
          />
        ))}

        {/* Main Text Markdown Response */}
        {contentPart && (
          <div
            className="rounded-xl relative group p-4 bg-[#1e1f24]/30 border border-zinc-800/20 hover:border-zinc-800/40 transition-colors"
            style={{
              boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
            }}
          >
            <MarkdownRenderer content={contentPart} onRunCommand={onRunCommand} />
          </div>
        )}

        {/* Visual Files Summary Review Pill */}
        {fileChangesList.length > 0 && (
          <div className="space-y-2.5 my-3.5">
            {/* Horizontal Pill bar */}
            <div
              onClick={() => setShowFilesList(!showFilesList)}
              className="flex items-center justify-between p-2.5 rounded-xl border border-zinc-800 bg-[#1a1a20]/90 text-[12px] font-medium text-zinc-300 hover:bg-[#1a1a20] cursor-pointer select-none transition-all duration-150 active:scale-[0.99] shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span className="text-zinc-400">
                  {fileChangesList.length} {fileChangesList.length === 1 ? 'file' : 'files'} changed
                </span>
                {(totalAdded > 0 || totalRemoved > 0) && (
                  <div className="flex items-center gap-1 font-mono font-bold text-[11px] shrink-0">
                    {totalAdded > 0 && <span className="text-green-500">+{totalAdded}</span>}
                    {totalRemoved > 0 && <span className="text-red-500">-{totalRemoved}</span>}
                  </div>
                )}
                <ChevronRight
                  className={`w-3.5 h-3.5 text-zinc-500 shrink-0 transform transition-transform duration-150 ${
                    showFilesList ? 'rotate-90 text-zinc-300' : ''
                  }`}
                />
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowFilesList(!showFilesList);
                }}
                className="btn-interactive flex items-center gap-1 px-2.5 py-1 rounded-md text-[10.5px] font-bold bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 shrink-0 cursor-pointer"
              >
                <FileText className="w-3 h-3 text-zinc-400" />
                <span>Review</span>
              </button>
            </div>

            {/* Grid of FileChangeCards */}
            {showFilesList && (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 animate-[slideDown_180ms_cubic-bezier(0.16,1,0.3,1)]">
                {fileChangesList.map((file: any) => (
                  <FileChangeCard
                    key={file.filePath}
                    filePath={file.filePath}
                    filename={file.filename}
                    status={file.status}
                    linesAdded={file.linesAdded}
                    linesRemoved={file.linesRemoved}
                    isPending={Boolean(file.confirmMessage)}
                    isDiffActive={activeDiffPath === file.filePath}
                    onToggleDiff={() => setActiveDiffPath(activeDiffPath === file.filePath ? null : file.filePath)}
                    onConfirmTool={onConfirmTool}
                    hunkDecisions={hunkDecisions[file.confirmMessage?.id || ''] || {}}
                    onOpenFile={onOpenFile}
                    confirmMessage={file.confirmMessage}
                  />
                ))}
              </div>
            )}

            {/* Dynamic Full-Width Diff Preview Block below the grid */}
            {activeDiffPath && activeDiffMessage && (
              <div className="border border-zinc-800 bg-[#0d0f14]/80 p-3.5 rounded-xl my-3 shadow-md animate-[fadeIn_150ms_ease-out]">
                <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-zinc-800 text-xs text-zinc-400 select-none">
                  <span className="font-semibold">
                    Diff Preview: <span className="font-mono text-blue-400">{activeFileChange.filename}</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveDiffPath(null)}
                    className="text-zinc-500 hover:text-zinc-300 font-semibold cursor-pointer"
                  >
                    Close Diff
                  </button>
                </div>
                {activeDiffMessage.confirmDiff?.hunks && activeDiffMessage.confirmDiff.hunks.length > 0 ? (
                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                    {activeDiffMessage.confirmDiff.hunks.map((hunk: any, idx: number) => (
                      <DiffView
                        key={hunk.id || idx}
                        hunk={hunk}
                        idx={idx}
                        isAccepted={hunkDecisions[activeDiffMessage.id || '']?.[hunk.id] ?? true}
                        onToggleHunk={(accepted) => onToggleHunk(activeDiffMessage.id || '', hunk.id, accepted)}
                      />
                    ))}
                  </div>
                ) : activeDiffMessage.confirmDiff ? (
                  <DiffView
                    filename={activeDiffMessage.confirmDiff.path}
                    hunks={activeDiffMessage.confirmDiff.hunks}
                  />
                ) : activeDiffMessage.diff ? (
                  <DiffView
                    filename={activeDiffMessage.diff.filename}
                    hunks={activeDiffMessage.diff.hunks}
                  />
                ) : null}
              </div>
            )}
          </div>
        )}

        {/* Separated Summary Card Block */}
        {summaryPart && (
          <div className="space-y-1.5 my-3">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-1">
              Summary
            </span>
            <div className="p-4 bg-[#1e1f24]/50 border border-zinc-850 rounded-xl text-[13px] leading-relaxed text-zinc-300">
              <MarkdownRenderer content={summaryPart} onRunCommand={onRunCommand} />
            </div>
          </div>
        )}

        {/* Feedback and Timestamp Footer */}
        {!isExecuting && (
          <div className="flex items-center justify-between text-zinc-500 text-[11px] select-none pt-2.5 font-sans border-t border-zinc-900/50 mt-1">
            <span className="font-medium text-zinc-600">{messageTime}</span>
            <div className="flex items-center gap-1.5">
              {/* Copy Message */}
              <button
                type="button"
                onClick={handleCopy}
                className="p-1 rounded hover:bg-zinc-900 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
                title="Copy response content"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>

              {/* Like Button */}
              <button
                type="button"
                onClick={() => setFeedback(feedback === 'liked' ? null : 'liked')}
                className={`p-1 rounded hover:bg-zinc-900 transition-colors cursor-pointer ${
                  feedback === 'liked' ? 'text-green-500 hover:text-green-400' : 'text-zinc-500 hover:text-zinc-300'
                }`}
                title="Helpful response"
              >
                <ThumbsUp className="w-3.5 h-3.5" />
              </button>

              {/* Dislike Button */}
              <button
                type="button"
                onClick={() => setFeedback(feedback === 'disliked' ? null : 'disliked')}
                className={`p-1 rounded hover:bg-zinc-900 transition-colors cursor-pointer ${
                  feedback === 'disliked' ? 'text-red-500 hover:text-red-450' : 'text-zinc-500 hover:text-zinc-300'
                }`}
                title="Not helpful response"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Turn Level Cost Metrics Footer */}
        {cost !== undefined && cost > 0 && (
          <div className="flex items-center gap-2 pt-1 select-none text-[10px] text-zinc-500 font-mono">
            <span>Cost: ${cost.toFixed(4)}</span>
            {agentsCount !== undefined && agentsCount > 0 && (
              <>
                <span>•</span>
                <span>Agents used: {agentsCount}</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export const AssistantMessage = React.memo(AssistantMessageComponent, (prev, next) => {
  return (
    prev.turn.id === next.turn.id &&
    prev.turn.isGenerating === next.turn.isGenerating &&
    prev.statusMessage === next.statusMessage &&
    prev.hunkDecisions === next.hunkDecisions &&
    prev.turn.assistantMessages.length === next.turn.assistantMessages.length &&
    prev.turn.toolMessages.length === next.turn.toolMessages.length &&
    prev.turn.confirmMessages.length === next.turn.confirmMessages.length &&
    prev.turn.assistantMessages.every((m: ChatMessage, i: number) => m.content === next.turn.assistantMessages[i].content) &&
    prev.turn.toolMessages.every((m: ChatMessage, i: number) => m.status === next.turn.toolMessages[i].status)
  );
});
