import React, { useState } from 'react';
import { Check, Copy, Loader2, Sparkles, ThumbsUp, ThumbsDown, AlertTriangle } from 'lucide-react';
import type { ChatMessage, DiffHunk } from '../../types/chat';
import { MarkdownRenderer } from './MarkdownRenderer';
import { FileChangeCard } from './FileChangeCard';
import { ConfirmDialog } from './ConfirmDialog';
import { DiffView } from './DiffView';
import { copyToClipboard } from '../../utils/clipboard';
import { useAI } from '../../core/ai/AIContext';
import { parseToolEvent } from './ReasoningTimeline';
import ThinkingState from './ThinkingState';
import ToolChips, { type ToolRow } from './ToolChips';

export interface AiTurn {
  kind: 'ai';
  id: string;
  allMessages: ChatMessage[];
  assistantMessages: ChatMessage[];
  toolMessages: ChatMessage[];
  confirmMessages: ChatMessage[];
  isGenerating?: boolean;
}

interface TimelineBlock {
  type: 'thinking' | 'tool' | 'text' | 'confirm' | 'running_tool' | 'grouped_tools';
  id: string;
  message?: ChatMessage;
  thinkingContent?: string;
  textContent?: string;
  toolInfo?: {
    action: string;
    substep?: string;
    detail?: string;
    resultText?: string;
    toolType: string;
    status: 'running' | 'success' | 'error';
    name: string;
  };
  tools?: TimelineBlock[];
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

const nameToToolType = (name: string): string => {
  const n = name.toLowerCase();
  if (n.includes('read'))   return 'file_read';
  if (n.includes('write') || n.includes('edit') || n.includes('patch')) return 'file_edit';
  if (n.includes('search') || n.includes('grep')) return 'search';
  if (n.includes('terminal') || n.includes('command') || n.includes('bash')) return 'terminal';
  if (n.includes('schedule') || n.includes('timer')) return 'schedule';
  return 'other';
};

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
  const [feedback, setFeedback] = useState<'liked' | 'disliked' | null>(null);

  const { liveToolCalls, taskMemory } = useAI();

  interface FileDiff {
    file: string;
    add: number;
    del: number;
  }

  const diffsList: FileDiff[] = [];
  const seenFiles = new Set<string>();

  if (taskMemory && taskMemory.files_written) {
    taskMemory.files_written.forEach((file) => {
      const filename = file.split('/').pop() || file;
      if (!seenFiles.has(filename)) {
        seenFiles.add(filename);
        const edits = taskMemory.file_edits?.[file];
        diffsList.push({
          file: filename,
          add: edits?.added ?? 0,
          del: edits?.removed ?? 0,
        });
      }
    });
  }

  (turn.allMessages || []).forEach((m) => {
    const diffData = m.confirmDiff || m.diff;
    if (diffData) {
      let path = '';
      if (m.confirmDiff) {
        path = m.confirmDiff.path;
      } else if (m.diff) {
        path = m.diff.filename;
      }

      if (path) {
        const filename = path.split(/[/\\]/).pop() || path;
        if (!seenFiles.has(filename)) {
          seenFiles.add(filename);
          let add = 0;
          let del = 0;
          if (diffData.hunks) {
            diffData.hunks.forEach((h: DiffHunk) => {
              if (h.type === 'add') add++;
              else if (h.type === 'remove') del++;
              else if (h.content) {
                h.content.split('\n').forEach((line: string) => {
                  if (line.startsWith('+')) add++;
                  else if (line.startsWith('-')) del++;
                });
              }
            });
          }
          diffsList.push({ file: filename, add, del });
        }
      }
    }
  });

  // Build the chronological sequence of blocks
  const blocks: TimelineBlock[] = [];
  
  (turn.allMessages || []).forEach((m, idx) => {
    const messageId = m.id || `msg_${idx}`;
    if (m.role === 'tool') {
      const name = m.name || 'action';
      const contentStr = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
      const parsed = parseToolEvent(
        name,
        nameToToolType(name),
        contentStr,
        contentStr,
        m.status || 'success'
      );
      
      blocks.push({
        type: 'tool',
        id: messageId,
        message: m,
        toolInfo: {
          action: parsed.action,
          substep: parsed.substep,
          detail: parsed.detail,
          resultText: parsed.resultText,
          toolType: parsed.toolType,
          status: (m.status === 'error' ? 'error' : 'success') as 'success' | 'error',
          name: name,
        }
      });
    } else if (m.role === 'assistant') {
      // 1. Thinking
      let thinking = '';
      const stepsText = (m.thinkingSteps && m.thinkingSteps.length > 0) 
        ? m.thinkingSteps.join('\n') 
        : '';
      const blocksText = (m.thinking_blocks && Array.isArray(m.thinking_blocks))
        ? m.thinking_blocks.map((b: any) => b.thinking || b.data || '').filter(Boolean).join('\n')
        : '';
      
      let tagsText = '';
      if (typeof m.content === 'string') {
        const match = m.content.match(/<thinking>([\s\S]*?)<\/thinking>/);
        if (match) {
          tagsText = match[1];
        }
      }

      thinking = [stepsText, blocksText, tagsText].filter(Boolean).join('\n\n');
      
      if (thinking.trim()) {
        blocks.push({
          type: 'thinking',
          id: `${messageId}_thinking`,
          message: m,
          thinkingContent: thinking,
        });
      }
      
      // 2. Confirmations
      if (m.isConfirmPending || m.isPermissionRequest || m.isPortConflictRequest || m.isCostConfirmationRequest) {
        blocks.push({
          type: 'confirm',
          id: `${messageId}_confirm`,
          message: m,
        });
      } else {
        // 3. Main response text
        let textContent = '';
        if (typeof m.content === 'string') {
          textContent = m.content.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
        } else if (m.content && typeof m.content === 'object') {
          if (!('tool_calls' in m.content) && !('role' in m.content)) {
            textContent = JSON.stringify(m.content);
          }
        }

        const isRawJsonDump =
          textContent.startsWith('[{"id":"chatcmpl-tool') ||
          textContent.startsWith('{"content":"","tool_calls":') ||
          (textContent.startsWith('[{"') && textContent.includes('"tool_calls"')) ||
          (textContent.startsWith('{"') && textContent.includes('"tool_calls"'));

        if (textContent && !isRawJsonDump) {
          blocks.push({
            type: 'text',
            id: `${messageId}_text`,
            message: m,
            textContent: textContent,
          });
        }
      }
    }
  });

  // Append currently running tools from websocket liveToolCalls
  if (turn.isGenerating && liveToolCalls) {
    liveToolCalls.forEach((t) => {
      if (t.status === 'running') {
        const exists = blocks.some(b => b.type === 'tool' && b.message?.tool_call_id === t.id);
        if (!exists) {
          blocks.push({
            type: 'running_tool',
            id: t.id,
            toolInfo: {
              action: t.name || 'Running tool...',
              substep: t.params?.path || '',
              toolType: t.tool,
              status: 'running',
              name: t.name || '',
            }
          });
        }
      }
    });
  }

  // Post-process blocks to merge consecutive tool and running_tool blocks
  const groupedBlocks: TimelineBlock[] = [];
  let currentToolGroup: TimelineBlock[] = [];

  const flushToolGroup = () => {
    if (currentToolGroup.length > 0) {
      if (currentToolGroup.length === 1) {
        groupedBlocks.push(currentToolGroup[0]);
      } else {
        groupedBlocks.push({
          type: 'grouped_tools',
          id: `grouped_tools_${currentToolGroup[0].id}`,
          tools: [...currentToolGroup],
        });
      }
      currentToolGroup = [];
    }
  };

  blocks.forEach((block) => {
    if (block.type === 'tool' || block.type === 'running_tool') {
      currentToolGroup.push(block);
    } else {
      flushToolGroup();
      groupedBlocks.push(block);
    }
  });
  flushToolGroup();

  // Extract metadata / elapsed
  const textMessage = turn.assistantMessages.find((m: ChatMessage) => m.content && !m.isConfirmPending) || turn.assistantMessages[0];
  const elapsed = textMessage?.elapsed_ms;
  const cost = textMessage?.cost_usd;
  const agentsCount = textMessage?.agents_used;

  const handleCopy = () => {
    const allText = blocks
      .filter(b => b.type === 'text' && b.textContent)
      .map(b => b.textContent)
      .join('\n\n');
    if (allText) {
      copyToClipboard(allText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const isExecuting = turn.isGenerating;

  const [messageTime] = useState(() => {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  });

  const mapBlockToToolRow = (block: TimelineBlock): ToolRow => {
    const t = block.toolInfo?.toolType || '';
    let icon = 'think';
    if (t === 'file_read') icon = 'read';
    else if (t === 'file_edit' || t === 'file_write') icon = 'write';
    else if (t === 'terminal') icon = 'run';
    else if (t === 'search') icon = 'search';

    const rawAction = block.toolInfo?.name || block.toolInfo?.action || 'Tool call';
    const cleanLabel = rawAction.replace(/^Processing\s+/i, '').replace(/\.\.\.$/, '');
    const chip = block.toolInfo?.substep || block.toolInfo?.detail || 'Execution';
    const detailText = block.toolInfo?.detail || block.toolInfo?.resultText || 'Completed execution';

    return {
      icon,
      label: cleanLabel.charAt(0).toUpperCase() + cleanLabel.slice(1),
      chip,
      mono: true,
      detailMono: true,
      detail: [{ text: detailText }],
    };
  };

  const renderInlineFileChangeCard = (block: TimelineBlock, isPending: boolean = false) => {
    const m = block.message;
    if (!m) return null;
    
    const name = m.name || '';
    const isWriteOrEdit = name.includes('write_file') || name.includes('edit_file') || name.includes('replace_file') || m.confirmDiff;
    
    if (!isWriteOrEdit) return null;
    
    let path = '';
    let status: 'Created' | 'Modified' = name.includes('write_file') ? 'Created' : 'Modified';
    
    if (m.confirmDiff) {
      path = m.confirmDiff.path;
      status = !m.confirmDiff.original ? 'Created' : 'Modified';
    } else {
      try {
        const contentStr = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
        const params = JSON.parse(contentStr);
        path = params.TargetFile || params.path || params.AbsolutePath || '';
      } catch {
        const match = m.name?.match(/TargetFile='([^']+)'/);
        if (match) path = match[1];
      }
    }
    
    if (!path) return null;
    const filename = path.split(/[/\\]/).pop() || path;
    const isDiffActive = activeDiffPath === path;
    
    let addCount = 0;
    let removeCount = 0;
    const diffData = m.confirmDiff || m.diff;
    if (diffData) {
      if (diffData.hunks) {
        diffData.hunks.forEach((h: DiffHunk) => {
          if (h.type === 'add') addCount++;
          else if (h.type === 'remove') removeCount++;
          else if (h.content) {
            h.content.split('\n').forEach((line: string) => {
              if (line.startsWith('+')) addCount++;
              else if (line.startsWith('-')) removeCount++;
            });
          }
        });
      }
    }

    return (
      <div className="my-2 space-y-2 select-text">
        <div className="max-w-xl">
          <FileChangeCard
            filePath={path}
            filename={filename}
            status={status}
            linesAdded={addCount || undefined}
            linesRemoved={removeCount || undefined}
            isPending={isPending}
            isDiffActive={isDiffActive}
            onToggleDiff={() => setActiveDiffPath(isDiffActive ? null : path)}
            onConfirmTool={onConfirmTool}
            hunkDecisions={hunkDecisions[m.id || ''] || {}}
            onOpenFile={onOpenFile}
            confirmMessage={isPending ? m : undefined}
          />
        </div>
        
        {isDiffActive && (
          <div className="border border-zinc-800 bg-[#0d0f14]/80 p-3.5 rounded-xl my-2 shadow-md animate-[fadeIn_150ms_ease-out]">
            <div className="flex items-center justify-between mb-2 pb-1.5 border-b border-zinc-800 text-xs text-zinc-400 select-none">
              <span className="font-semibold">
                Diff Preview: <span className="font-mono text-blue-400">{filename}</span>
              </span>
              <button
                type="button"
                onClick={() => setActiveDiffPath(null)}
                className="text-zinc-500 hover:text-zinc-300 font-semibold cursor-pointer"
              >
                Close Diff
              </button>
            </div>
            {diffData?.hunks && diffData.hunks.length > 0 ? (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {diffData.hunks.map((hunk: any, idx: number) => (
                  <DiffView
                    key={hunk.id || idx}
                    hunk={hunk}
                    idx={idx}
                    isAccepted={hunkDecisions[m.id || '']?.[hunk.id] ?? true}
                    onToggleHunk={(accepted) => onToggleHunk(m.id || '', hunk.id, accepted)}
                  />
                ))}
              </div>
            ) : m.confirmDiff ? (
              <DiffView
                filename={m.confirmDiff.path}
                hunks={m.confirmDiff.hunks}
              />
            ) : m.diff ? (
              <DiffView
                filename={m.diff.filename}
                hunks={m.diff.hunks}
              />
            ) : null}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-3.5 mb-6 select-text animate-[fadeIn_150ms_ease-out] font-sans">
      {/* AI Assistant Header Row */}
      <div className="flex items-center justify-between select-none">
        <div className="flex items-center gap-2.5">
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

      {/* Chronological Steps Flow Timeline */}
      <div className="flex-1 min-w-0">
        <div className="space-y-1 py-1">
          {groupedBlocks.map((block) => (
            <div key={block.id} className="relative group">
              {/* Block Contents */}
              <div className="min-w-0">
                {/* 1. Thinking block */}
                {block.type === 'thinking' && (
                  <div className="select-none animate-[fadeIn_120ms_ease-out]">
                    <ThinkingState
                      variant={
                        block.thinkingContent && block.thinkingContent.includes('\n')
                          ? 'Steps'
                          : 'Reasoning'
                      }
                      customRows={
                        block.thinkingContent
                          ? block.thinkingContent
                              .split(/\n+/)
                              .map((line: string) => line.replace(/^[-*•\d.]+\s*/, '').trim())
                              .filter(Boolean)
                              .map((primary: string) => ({ primary }))
                          : undefined
                      }
                      activeLabel="Thinking"
                      doneLabel={`Thought for ${elapsed ? (elapsed / 1000).toFixed(0) : '4'} seconds`}
                      isWorking={isExecuting}
                    />
                  </div>
                )}

                {/* Grouped tools block */}
                {block.type === 'grouped_tools' && (
                  <div className="select-none animate-[fadeIn_120ms_ease-out] my-1">
                    <ToolChips
                      customRows={block.tools!.map(t => mapBlockToToolRow(t))}
                      customDiffs={diffsList}
                      messagesCount={block.tools!.length}
                      initialExpanded={false}
                    />
                    {block.tools!.map(t => renderInlineFileChangeCard(t))}
                  </div>
                )}

                {/* 2. Tool block */}
                {block.type === 'tool' && (
                  <div className="select-none animate-[fadeIn_120ms_ease-out] my-1">
                    <ToolChips
                      customRows={[mapBlockToToolRow(block)]}
                      customDiffs={diffsList}
                      headerLabel={`1 tool call: ${mapBlockToToolRow(block).label}`}
                      messagesCount={1}
                      initialExpanded={false}
                    />
                    {renderInlineFileChangeCard(block)}
                  </div>
                )}

                {/* 3. Running tool block */}
                {block.type === 'running_tool' && (
                  <div className="select-none animate-[fadeIn_120ms_ease-out] my-1">
                    <ToolChips
                      customRows={[mapBlockToToolRow(block)]}
                      customDiffs={diffsList}
                      headerLabel={`Running: ${mapBlockToToolRow(block).label}`}
                      messagesCount={1}
                      initialExpanded={true}
                    />
                  </div>
                )}

                {/* 4. Confirm block */}
                {block.type === 'confirm' && (
                  <div className="space-y-3 animate-[fadeIn_120ms_ease-out]">
                    <div className="flex items-center gap-2 text-xs font-bold text-orange-400 uppercase tracking-wider select-none">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      <span>Requires User Review</span>
                    </div>
                    {(!block.message?.confirmDiff) ? (
                      <ConfirmDialog
                        key={block.message?.id}
                        msg={block.message!}
                        onConfirmTool={onConfirmTool}
                        onConfirmPermission={onConfirmPermission}
                        onConfirmPortConflict={onConfirmPortConflict}
                      />
                    ) : (
                      renderInlineFileChangeCard(block, true)
                    )}
                  </div>
                )}

                {/* 5. Text response block */}
                {block.type === 'text' && (
                  <div className="rounded-xl relative group p-4 bg-[#1e1f24]/30 border border-zinc-800/20 hover:border-zinc-800/40 transition-colors shadow-sm animate-[fadeIn_150ms_ease-out] select-text">
                    <MarkdownRenderer content={block.textContent!} onRunCommand={onRunCommand} />
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Feedback and Timestamp Footer */}
        {!isExecuting && (
          <div className="flex items-center justify-between text-zinc-500 text-[11px] select-none pt-2.5 font-sans border-t border-zinc-900/50 mt-4 pl-3">
            <span className="font-medium text-zinc-600">{messageTime}</span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={handleCopy}
                className="p-1 rounded hover:bg-zinc-900 text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer"
                title="Copy response content"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>

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
          <div className="flex items-center gap-2 pt-1 select-none text-[10px] text-zinc-500 font-mono pl-3">
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
    prev.turn.allMessages?.length === next.turn.allMessages?.length &&
    prev.turn.assistantMessages.length === next.turn.assistantMessages.length &&
    prev.turn.toolMessages.length === next.turn.toolMessages.length &&
    prev.turn.confirmMessages.length === next.turn.confirmMessages.length &&
    prev.turn.assistantMessages.every((m: ChatMessage, i: number) => m.content === next.turn.assistantMessages[i].content) &&
    prev.turn.toolMessages.every((m: ChatMessage, i: number) => m.status === next.turn.toolMessages[i].status)
  );
});
