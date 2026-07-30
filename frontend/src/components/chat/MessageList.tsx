import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../types/chat';
import { Check, User, Copy } from 'lucide-react';
import { ConfirmDialog } from './ConfirmDialog';
import { DiffView } from './DiffView';
import { ThinkingPill } from './ThinkingPill';
import { CodeBlock } from './CodeBlock';
import { ReasoningTimeline, toolMessagesToTimelineRows } from './ReasoningTimeline';

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

// â”€â”€ Premium Status Pill â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const StatusPill: React.FC<{ elapsed_ms?: number; cost_usd?: number; agents_used?: number }> = ({
  elapsed_ms, cost_usd, agents_used
}) => {
  const parts: string[] = [];
  if (cost_usd !== undefined) parts.push(`$${cost_usd.toFixed(4)}`);
  if (agents_used !== undefined) parts.push(`${agents_used} agent${agents_used === 1 ? '' : 's'}`);
  const secs = elapsed_ms !== undefined ? (elapsed_ms / 1000).toFixed(1) : null;

  if (!secs && parts.length === 0) return null;
  return (
    <div className="flex items-center gap-2 mt-3 pt-2.5" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
      {secs && (
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
          style={{
            background: 'rgba(34,197,94,0.08)',
            color: '#22c55e',
            border: '1px solid rgba(34,197,94,0.15)',
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#22c55e]" />
          Completed in {secs}s
        </span>
      )}
      {parts.map((p, i) => (
        <span key={i} className="text-[11px]" style={{ color: '#757c87' }}>{p}</span>
      ))}
    </div>
  );
};

// â”€â”€ Thinking Steps Execution Flow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const ExecutionFlow: React.FC<{ steps: string[] }> = ({ steps }) => (
  <div
    className="w-full rounded-2xl p-4 mb-3 space-y-2"
    style={{ background: '#17191f', border: '1px solid rgba(255,255,255,0.04)' }}
  >
    <div className="flex items-center gap-2 mb-3">
      <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: '#757c87' }}>
        Execution Flow
      </span>
    </div>
    <div className="space-y-1.5 pl-1">
      {steps.map((step, i) => {
        const isDone = step.startsWith('âœ“');
        const text = isDone ? step.substring(1).trim() : step;
        return (
          <div key={i} className="flex items-center gap-2.5">
            {isDone ? (
              <span className="w-4 h-4 rounded-full flex items-center justify-center shrink-0" style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.25)' }}>
                <Check className="w-2.5 h-2.5" style={{ color: '#22c55e' }} />
              </span>
            ) : (
              <span className="w-4 h-4 rounded-full flex items-center justify-center shrink-0 animate-pulse" style={{ background: 'rgba(79,140,255,0.1)', border: '1px solid rgba(79,140,255,0.3)' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-[#4f8cff]" />
              </span>
            )}
            <span className={`text-[12px] leading-snug ${isDone ? 'line-through' : 'font-medium'}`} style={{ color: isDone ? '#757c87' : '#aeb6c2' }}>
              {text}
            </span>
          </div>
        );
      })}
    </div>
  </div>
);

// â”€â”€ Empty State â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const EmptyState: React.FC = () => (
  <div className="flex flex-col items-center justify-center h-full gap-5 px-8 py-12 select-none">
    <div className="text-center space-y-1.5 max-w-xs">
      <p className="text-[14px] font-semibold text-white/90">Ask DevPilot anything</p>
      <p className="text-[12px] leading-relaxed text-[var(--dp-text-muted)]">
        Chat, plan, or let the Agent autonomously write code, run commands, and manage your project.
      </p>
    </div>
    {/* Suggestion chips */}
    <div className="flex flex-wrap justify-center gap-2 max-w-sm mt-1">
      {[
        'Refactor active file',
        'Fix failing tests',
        'Write documentation',
        'Optimize performance',
      ].map((tip) => (
        <span
          key={tip}
          className="px-2.5 py-1 rounded text-[11px] font-medium cursor-pointer transition-colors bg-white/5 hover:bg-white/10 text-white/70 hover:text-white border border-white/10"
        >
          {tip}
        </span>
      ))}
    </div>
  </div>
);

// â”€â”€ Group messages into render units â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Rules:
//   â€¢ Consecutive tool messages between two non-tool messages form ONE group.
//   â€¢ Assistant messages are NEVER merged â€” each is its own unit.
//   â€¢ The order is strictly preserved so thinkingâ†’toolsâ†’thinkingâ†’tools
//     renders top-to-bottom as it arrived (not batched at the end).
interface ToolGroup {
  kind: 'tool_group';
  id: string;
  toolMessages: ChatMessage[];
}
interface SingleMsg {
  kind: 'msg';
  msg: ChatMessage;
}
type RenderUnit = ToolGroup | SingleMsg;

function groupMessages(messages: ChatMessage[]): RenderUnit[] {
  const units: RenderUnit[] = [];
  let i = 0;
  while (i < messages.length) {
    const m = messages[i];
    if (m.role === 'tool') {
      // Gather THIS cluster of consecutive tool messages only
      const batch: ChatMessage[] = [];
      while (i < messages.length && messages[i].role === 'tool') {
        batch.push(messages[i]);
        i++;
      }
      units.push({ kind: 'tool_group', id: batch[0].id, toolMessages: batch });
    } else {
      units.push({ kind: 'msg', msg: m });
      i++;
    }
  }
  return units;
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  // Auto-scroll whenever messages change (new content or new message)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const processMessage = (raw: any): { visible: string; thinkingContent: string | null } => {
    if (raw === null || raw === undefined) return { visible: '', thinkingContent: null };
    const str = typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2);
    const match = str.match(/<thinking>([\s\S]*?)<\/thinking>/);
    const thinkingContent = match ? match[1] : null;
    const visible = str.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
    return { visible, thinkingContent };
  };

  if (messages.length === 0) return <EmptyState />;

  const units = groupMessages(messages);

  return (
    <div
      className="flex-1 overflow-y-auto select-text"
      style={{ padding: '24px 20px', scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.08) transparent' }}
    >
      {/* Centered content wrapper â€” max 840px */}
      <div className="mx-auto space-y-3" style={{ maxWidth: '840px' }}>
        {units.map((unit) => {
          // â”€â”€ TOOL GROUP â†’ ReasoningTimeline (inline, in order) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
          if (unit.kind === 'tool_group') {
            const rows = toolMessagesToTimelineRows(unit.toolMessages);
            return (
              <div key={unit.id} className="animate-slide-up pl-9">
                <ReasoningTimeline rows={rows} isGenerating={false} />
              </div>
            );
          }

          const msg = unit.msg;
          const isUser = msg.role === 'user';

          // â”€â”€ 1. USER MESSAGE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
          if (isUser) {
            const text = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
            return (
              <div key={msg.id} className="flex justify-end animate-slide-up">
                <div className="flex gap-3 items-end max-w-[76%]">
                  <div
                    className="px-4 py-3 rounded-2xl rounded-br-sm text-[14px] leading-relaxed whitespace-pre-wrap break-words select-text"
                    style={{
                      background: 'linear-gradient(135deg, #1e2a4a 0%, #192240 100%)',
                      color: '#dde3f0',
                      border: '1px solid rgba(79,140,255,0.18)',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                    }}
                  >
                    {text}
                  </div>
                  {/* User Avatar */}
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mb-0.5"
                    style={{ background: 'linear-gradient(135deg, #3b6fcf 0%, #1e40af 100%)', boxShadow: '0 0 12px rgba(59,111,207,0.3)' }}
                  >
                    <User className="w-3.5 h-3.5 text-white" />
                  </div>
                </div>
              </div>
            );
          }

          // role === 'tool' handled above in tool_group â€” never reached here.

          // â”€â”€ 2. PENDING CONFIRMATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
          if (msg.isConfirmPending || (msg.role === 'assistant' && msg.isConfirmPending)) {
            return (
              <div key={msg.id} className="animate-slide-up">
                <ConfirmDialog
                  msg={msg}
                  onConfirmTool={onConfirmTool}
                  onConfirmPermission={onConfirmPermission}
                  onConfirmPortConflict={onConfirmPortConflict}
                  hunkDecisions={hunkDecisions[msg.id] || {}}
                  onToggleHunk={(hunkId, accepted) => onToggleHunk(msg.id, hunkId, accepted)}
                />
              </div>
            );
          }

          // â”€â”€ 3. ASSISTANT RESPONSE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
          if (msg.role === 'assistant') {
            const { visible, thinkingContent } = processMessage(msg.content);
            const hasThinkingSteps = msg.thinkingSteps && msg.thinkingSteps.length > 0;
            const hasToolCalls = msg.tool_calls && msg.tool_calls.length > 0;
            const hasDiff = Boolean(msg.diff);

            if (!visible && !thinkingContent && !hasThinkingSteps && !hasToolCalls && !hasDiff) return null;

            return (
              <div key={msg.id} className="flex gap-3 items-start animate-slide-up">
                {/* AI Avatar */}
                <div className="w-6 h-6 rounded flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-bold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20">
                  AI
                </div>

                <div className="flex-1 min-w-0 space-y-2">
                  {/* Thinking pill (collapsed <thinking> block) */}
                  {thinkingContent && (
                    <ThinkingPill content={thinkingContent} durationMs={msg.elapsed_ms} />
                  )}

                  {/* Execution flow steps */}
                  {hasThinkingSteps && (
                    <ExecutionFlow steps={msg.thinkingSteps || []} />
                  )}

                  {/* â”€â”€ Main Assistant Card â”€â”€ */}
                  {visible && (
                    <div
                      className="rounded-2xl transition-all duration-200 group relative"
                      style={{
                        background: 'linear-gradient(160deg, #13151c 0%, #111318 100%)',
                        border: '1px solid rgba(255,255,255,0.05)',
                        boxShadow: '0 4px 24px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.03) inset',
                        padding: '20px 22px',
                        position: 'relative'
                      }}
                    >
                      {/* Copy Message Button */}
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(visible);
                          setCopiedMsgId(msg.id);
                          setTimeout(() => setCopiedMsgId(null), 1800);
                        }}
                        title="Copy message"
                        className="absolute top-3 right-3 flex items-center justify-center p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-150 cursor-pointer"
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.08)',
                          color: copiedMsgId === msg.id ? '#22c55e' : '#757c87',
                          zIndex: 10
                        }}
                      >
                        {copiedMsgId === msg.id ? (
                          <Check className="w-3.5 h-3.5" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>

                      {/* Subtle radial gradient glow on hover */}
                      <div
                        className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
                        style={{ background: 'radial-gradient(ellipse at 15% 0%, rgba(79,140,255,0.04) 0%, transparent 65%)' }}
                      />

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
                          p: ({ children }) => (
                            <p className="mb-3 last:mb-0 leading-[1.75]" style={{ fontSize: '14.5px', color: '#c8cfd9' }}>
                              {children}
                            </p>
                          ),
                          strong: ({ children }) => (
                            <strong className="font-semibold" style={{ color: '#e8ecf2' }}>{children}</strong>
                          ),
                          em: ({ children }) => (
                            <em style={{ color: '#aeb6c2', fontStyle: 'italic' }}>{children}</em>
                          ),
                          h1: ({ children }) => (
                            <h1 className="font-semibold mt-5 mb-3 pb-2" style={{ fontSize: '18px', color: '#edf0f5', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                              {children}
                            </h1>
                          ),
                          h2: ({ children }) => (
                            <h2 className="font-semibold mt-4 mb-2" style={{ fontSize: '16px', color: '#e2e7ef' }}>
                              {children}
                            </h2>
                          ),
                          h3: ({ children }) => (
                            <h3 className="font-semibold mt-3 mb-1.5" style={{ fontSize: '14px', color: '#d4dae5' }}>
                              {children}
                            </h3>
                          ),
                          ul: ({ children }) => (
                            <ul className="my-2.5 space-y-1.5 pl-0" style={{ listStyle: 'none' }}>
                              {React.Children.map(children, (child, i) => (
                                <span key={i} className="flex items-start gap-2.5">
                                  <span className="mt-[7px] w-1.5 h-1.5 rounded-full shrink-0" style={{ background: '#4f8cff', opacity: 0.7 }} />
                                  {child}
                                </span>
                              ))}
                            </ul>
                          ),
                          ol: ({ children }) => (
                            <ol className="my-2.5 pl-5 space-y-1.5" style={{ color: '#c8cfd9', listStyleType: 'decimal', fontSize: '14.5px' }}>
                              {children}
                            </ol>
                          ),
                          li: ({ children }) => (
                            <li className="leading-relaxed" style={{ color: '#c8cfd9', fontSize: '14.5px' }}>
                              {children}
                            </li>
                          ),
                          blockquote: ({ children }) => (
                            <blockquote
                              className="my-3 py-2 pl-4"
                              style={{
                                borderLeft: '2px solid rgba(79,140,255,0.4)',
                                background: 'rgba(79,140,255,0.04)',
                                borderRadius: '0 8px 8px 0',
                                color: '#aeb6c2',
                                fontStyle: 'italic',
                              }}
                            >
                              {children}
                            </blockquote>
                          ),
                          hr: () => (
                            <hr className="my-4" style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.06)' }} />
                          ),
                          a: ({ href, children }) => (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline underline-offset-2 transition-colors hover:opacity-80"
                              style={{ color: '#4f8cff', textDecorationColor: 'rgba(79,140,255,0.4)' }}
                            >
                              {children}
                            </a>
                          ),
                          table: ({ children }) => (
                            <div className="overflow-x-auto my-3 rounded-xl" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
                              <table className="w-full text-[13px]" style={{ color: '#c8cfd9', borderCollapse: 'collapse' }}>
                                {children}
                              </table>
                            </div>
                          ),
                          th: ({ children }) => (
                            <th className="text-left px-3 py-2 text-[11px] font-bold uppercase tracking-wider" style={{ color: '#757c87', background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                              {children}
                            </th>
                          ),
                          td: ({ children }) => (
                            <td className="px-3 py-2" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                              {children}
                            </td>
                          ),
                        }}
                      >
                        {visible}
                      </ReactMarkdown>

                      {/* Inline tool call count â€” only shown when there is no separate tool group below */}
                      {hasToolCalls && (
                        <div className="mt-2 text-[11px]" style={{ color: '#4B5563', fontFamily: 'Inter, sans-serif' }}>
                          {msg.tool_calls!.length} tool call{msg.tool_calls!.length > 1 ? 's' : ''} executed
                        </div>
                      )}

                      {/* Inline diff */}
                      {hasDiff && msg.diff && (
                        <div className="mt-3">
                          <DiffView filename={msg.diff.filename} hunks={msg.diff.hunks} />
                        </div>
                      )}

                      {/* Status pill footer */}
                      <StatusPill elapsed_ms={msg.elapsed_ms} cost_usd={msg.cost_usd} agents_used={msg.agents_used} />
                    </div>
                  )}

                  {/* If no visible text but has diff, show it standalone */}
                  {!visible && hasDiff && msg.diff && (
                    <DiffView filename={msg.diff.filename} hunks={msg.diff.hunks} />
                  )}
                </div>
              </div>
            );
          }

          return null;
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
