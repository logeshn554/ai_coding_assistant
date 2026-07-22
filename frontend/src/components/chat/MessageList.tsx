import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../types/chat';
import { Sparkles, Check, Bot, User } from 'lucide-react';
import { ConfirmDialog } from './ConfirmDialog';
import { ToolCallView } from './ToolCallView';
import { DiffView } from './DiffView';
import { ThinkingPill } from './ThinkingPill';
import { CodeBlock } from './CodeBlock';

interface MessageListProps {
  messages: ChatMessage[];
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  hunkDecisions: Record<string, Record<string, boolean>>;
  onToggleHunk: (msgId: string, hunkId: string, accepted: boolean) => void;
  renderMessageContent?: (content: string) => React.ReactNode;
  onRunCommand?: (command: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  onConfirmTool,
  onConfirmPermission,
  onConfirmPortConflict,
  hunkDecisions,
  onToggleHunk,
  onRunCommand,
}) => {
  // Helper to extract <thinking> blocks and visible response text
  const processMessage = (raw: any): { visible: string; thinkingContent: string | null } => {
    if (raw === null || raw === undefined) return { visible: '', thinkingContent: null };
    const strContent = typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2);

    const thinkingMatch = strContent.match(/<thinking>([\s\S]*?)<\/thinking>/);
    const thinkingContent = thinkingMatch ? thinkingMatch[1] : null;

    const visible = strContent.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
    return { visible, thinkingContent };
  };

  const formatCostTag = (msg: ChatMessage) => {
    const parts: string[] = [];
    if (msg.cost_usd !== undefined) {
      parts.push(`$${msg.cost_usd.toFixed(4)}`);
    }
    if (msg.agents_used !== undefined) {
      parts.push(`${msg.agents_used} agent${msg.agents_used === 1 ? '' : 's'}`);
    }
    if (msg.elapsed_ms !== undefined) {
      parts.push(`${(msg.elapsed_ms / 1000).toFixed(1)}s elapsed`);
    }
    return parts.length > 0 ? parts.join(' · ') : null;
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 select-text font-sans bg-zinc-950">
      {messages.map((msg) => {
        const isUser = msg.role === 'user';

        // 1. RENDER USER MESSAGE BUBBLE - NO TRUNCATION (max-w-[72%], break-words)
        if (isUser) {
          const userText = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
          return (
            <div key={msg.id} className="flex gap-2.5 max-w-[72%] items-start ml-auto flex-row-reverse select-text mb-4 animate-slide-up">
              <div className="w-7 h-7 rounded-md bg-blue-600 text-white shrink-0 flex items-center justify-center font-bold select-none shadow-sm">
                <User className="w-4 h-4" />
              </div>
              <div className="flex flex-col items-end w-full min-w-0">
                <div className="p-3 bg-blue-950/80 border border-blue-800/60 text-[13.5px] text-zinc-100 rounded-[10px] leading-relaxed whitespace-pre-wrap break-words select-text shadow-sm w-full">
                  {userText}
                </div>
              </div>
            </div>
          );
        }

        // 2. RENDER COMPLETED TOOL RESULTS INLINE
        if (msg.role === 'tool') {
          return <ToolCallView key={msg.id} msg={msg} />;
        }

        // 3. RENDER PENDING CONFIRMATIONS / DIALOGS INLINE
        if (msg.isConfirmPending || (msg.role === 'assistant' && msg.isConfirmPending)) {
          return (
            <ConfirmDialog
              key={msg.id}
              msg={msg}
              onConfirmTool={onConfirmTool}
              onConfirmPermission={onConfirmPermission}
              onConfirmPortConflict={onConfirmPortConflict}
              hunkDecisions={hunkDecisions[msg.id] || {}}
              onToggleHunk={(hunkId, accepted) => onToggleHunk(msg.id, hunkId, accepted)}
            />
          );
        }

        // 4. RENDER STANDARD ASSISTANT RESPONSE
        if (msg.role === 'assistant') {
          const { visible, thinkingContent } = processMessage(msg.content);
          const hasThinkingSteps = msg.thinkingSteps && msg.thinkingSteps.length > 0;
          const hasToolCalls = msg.tool_calls && msg.tool_calls.length > 0;
          const hasDiff = Boolean(msg.diff);
          const costTagStr = formatCostTag(msg);

          if (!visible && !thinkingContent && !hasThinkingSteps && !hasToolCalls && !hasDiff) return null;

          return (
            <div key={msg.id} className="flex gap-2.5 max-w-[95%] items-start select-text mb-4 animate-slide-up">
              {/* Avatar */}
              <div className="w-7 h-7 rounded-md bg-zinc-900 border border-zinc-800 text-blue-400 shrink-0 flex items-center justify-center font-bold select-none shadow-sm">
                <Bot className="w-4 h-4" />
              </div>

              <div className="flex flex-col items-start max-w-[calc(100%-2.25rem)] select-text w-full min-w-0">
                {/* Collapsible <thinking> Block Pill */}
                {thinkingContent && (
                  <ThinkingPill content={thinkingContent} durationMs={msg.elapsed_ms} />
                )}

                {/* Progressive Thinking Steps */}
                {hasThinkingSteps && (
                  <div className="w-full bg-zinc-900/90 border border-zinc-800/80 rounded-lg p-2.5 mb-2 space-y-1.5 select-none shadow-sm">
                    <div className="flex items-center gap-1.5 text-[11px] text-zinc-400 uppercase tracking-wider font-semibold">
                      <Sparkles className="w-3.5 h-3.5 text-blue-400 animate-pulse shrink-0" />
                      <span>Execution Flow</span>
                    </div>
                    <div className="space-y-1 pl-1">
                      {(msg.thinkingSteps || []).map((step: string, stepIdx: number) => {
                        const isCompleted = step.startsWith('✓');
                        const stepText = isCompleted ? step.substring(1).trim() : step;
                        return (
                          <div key={stepIdx} className="flex items-center gap-2 text-[11px] text-zinc-300">
                            {isCompleted ? (
                              <Check className="w-3 h-3 text-green-400 shrink-0" />
                            ) : (
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping shrink-0" />
                            )}
                            <span className={isCompleted ? 'text-zinc-400 font-medium' : 'text-zinc-200 font-semibold'}>
                              {stepText}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Main AI Bubble Container */}
                {visible && (
                  <div className="p-3.5 bg-zinc-900 border border-zinc-800 text-[13.5px] text-zinc-200 rounded-[10px] leading-relaxed select-text w-full shadow-md font-sans space-y-2 break-words overflow-hidden">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code: ({ className, children, ...props }) => {
                          const isInline = !className && !String(children).includes('\n');
                          return (
                            <CodeBlock
                              inline={isInline}
                              className={className}
                              onRunCommand={onRunCommand}
                              {...props}
                            >
                              {children}
                            </CodeBlock>
                          );
                        },
                        strong: ({ children }) => (
                          <strong className="font-semibold text-zinc-100">{children}</strong>
                        ),
                        p: ({ children }) => (
                          <p className="mb-2 leading-relaxed text-zinc-200">{children}</p>
                        ),
                        h1: ({ children }) => (
                          <h1 className="text-[16px] font-bold text-zinc-100 mt-3 mb-1.5 border-b border-zinc-800 pb-1">{children}</h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-[15px] font-semibold text-zinc-100 mt-3 mb-1">{children}</h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-[14px] font-semibold text-zinc-100 mt-2 mb-1">{children}</h3>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc pl-5 my-2 space-y-1 text-zinc-200">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal pl-5 my-2 space-y-1 text-zinc-200">{children}</ol>
                        ),
                        li: ({ children }) => (
                          <li className="text-zinc-200">{children}</li>
                        )
                      }}
                    >
                      {visible}
                    </ReactMarkdown>

                    {/* Inline Tool Call Cards */}
                    {hasToolCalls && <ToolCallView tool_calls={msg.tool_calls} />}

                    {/* Inline Diff Card */}
                    {hasDiff && msg.diff && (
                      <DiffView filename={msg.diff.filename} hunks={msg.diff.hunks} />
                    )}
                  </div>
                )}

                {/* Per-message Cost & Agent Tag Footer */}
                {costTagStr && (
                  <div className="mt-1 pl-1 text-[11px] font-mono text-zinc-500">
                    {costTagStr}
                  </div>
                )}
              </div>
            </div>
          );
        }

        return null;
      })}
    </div>
  );
};
