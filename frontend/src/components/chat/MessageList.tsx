import React, { useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../types/chat';
import { Sparkles, Check, User } from 'lucide-react';
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

// ── Premium Status Pill ────────────────────────────────────────────────
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

// ── Thinking Steps Execution Flow ──────────────────────────────────────
const ExecutionFlow: React.FC<{ steps: string[] }> = ({ steps }) => (
  <div
    className="w-full rounded-2xl p-4 mb-3 space-y-2"
    style={{ background: '#17191f', border: '1px solid rgba(255,255,255,0.04)' }}
  >
    <div className="flex items-center gap-2 mb-3">
      <Sparkles className="w-3.5 h-3.5 shrink-0" style={{ color: '#4f8cff' }} />
      <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: '#757c87' }}>
        Execution Flow
      </span>
    </div>
    <div className="space-y-1.5 pl-1">
      {steps.map((step, i) => {
        const isDone = step.startsWith('✓');
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

// ── Premium Empty State ────────────────────────────────────────────────
const EmptyState: React.FC = () => (
  <div className="flex flex-col items-center justify-center h-full gap-6 px-8 py-12 select-none">
    {/* Glowing icon */}
    <div className="relative flex items-center justify-center">
      <div className="absolute w-24 h-24 rounded-full opacity-20 blur-2xl" style={{ background: 'radial-gradient(circle, #4f8cff 0%, transparent 70%)' }} />
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center relative" style={{ background: 'linear-gradient(135deg, #1a1d28 0%, #12151f 100%)', border: '1px solid rgba(79,140,255,0.15)', boxShadow: '0 0 30px rgba(79,140,255,0.1)' }}>
        <Sparkles className="w-6 h-6" style={{ color: '#4f8cff' }} />
      </div>
    </div>
    <div className="text-center space-y-2 max-w-xs">
      <p className="text-[15px] font-semibold" style={{ color: '#aeb6c2' }}>Ask DevPilot anything</p>
      <p className="text-[13px] leading-relaxed" style={{ color: '#757c87' }}>
        Chat, plan, or let the Agent autonomously write code, run commands, and manage your project.
      </p>
    </div>
    {/* Suggestion chips */}
    <div className="flex flex-wrap justify-center gap-2 max-w-sm">
      {[
        '✨ Refactor this file',
        '🐛 Fix the failing test',
        '📝 Write a README',
        '⚡ Optimize performance',
      ].map((tip) => (
        <span
          key={tip}
          className="px-3 py-1.5 rounded-full text-[11px] font-medium cursor-pointer transition-all duration-200 hover:scale-[1.03]"
          style={{ background: '#17191f', color: '#aeb6c2', border: '1px solid rgba(255,255,255,0.07)' }}
        >
          {tip}
        </span>
      ))}
    </div>
  </div>
);

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

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const processMessage = (raw: any): { visible: string; thinkingContent: string | null } => {
    if (raw === null || raw === undefined) return { visible: '', thinkingContent: null };
    const str = typeof raw === 'string' ? raw : JSON.stringify(raw, null, 2);
    const match = str.match(/<thinking>([\s\S]*?)<\/thinking>/);
    const thinkingContent = match ? match[1] : null;
    const visible = str.replace(/<thinking>[\s\S]*?<\/thinking>/g, '').trim();
    return { visible, thinkingContent };
  };

  if (messages.length === 0) return <EmptyState />;

  return (
    <div
      className="flex-1 overflow-y-auto select-text"
      style={{ padding: '24px 20px', scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.08) transparent' }}
    >
      {/* Centered content wrapper — max 840px */}
      <div className="mx-auto space-y-6" style={{ maxWidth: '840px' }}>
        {messages.map((msg) => {
          const isUser = msg.role === 'user';

          // ── 1. USER MESSAGE ───────────────────────────────────
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

          // ── 2. TOOL RESULT (role: tool) ───────────────────────
          if (msg.role === 'tool') {
            return (
              <div key={msg.id} className="animate-slide-up pl-3">
                <ToolCallView msg={msg} />
              </div>
            );
          }

          // ── 3. PENDING CONFIRMATION ───────────────────────────
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

          // ── 4. ASSISTANT RESPONSE ─────────────────────────────
          if (msg.role === 'assistant') {
            const { visible, thinkingContent } = processMessage(msg.content);
            const hasThinkingSteps = msg.thinkingSteps && msg.thinkingSteps.length > 0;
            const hasToolCalls = msg.tool_calls && msg.tool_calls.length > 0;
            const hasDiff = Boolean(msg.diff);

            if (!visible && !thinkingContent && !hasThinkingSteps && !hasToolCalls && !hasDiff) return null;

            return (
              <div key={msg.id} className="flex gap-3 items-start animate-slide-up">
                {/* AI Avatar */}
                <div
                  className="w-7 h-7 rounded-xl flex items-center justify-center shrink-0 mt-0.5"
                  style={{
                    background: 'linear-gradient(135deg, #2d2060 0%, #1a1540 100%)',
                    border: '1px solid rgba(124,106,240,0.25)',
                    boxShadow: '0 0 14px rgba(124,106,240,0.2)',
                  }}
                >
                  <Sparkles className="w-3.5 h-3.5" style={{ color: '#7c6af0' }} />
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

                  {/* ── Main Assistant Card ── */}
                  {visible && (
                    <div
                      className="rounded-2xl transition-all duration-200 group"
                      style={{
                        background: 'linear-gradient(160deg, #13151c 0%, #111318 100%)',
                        border: '1px solid rgba(255,255,255,0.05)',
                        boxShadow: '0 4px 24px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.03) inset',
                        padding: '20px 22px',
                      }}
                    >
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
                              {React.Children.map(children, (child) => (
                                <span className="flex items-start gap-2.5">
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

                      {/* Inline tool call cards (assistant function_call output) */}
                      {hasToolCalls && (
                        <div className="mt-3">
                          <ToolCallView tool_calls={msg.tool_calls} />
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

                  {/* If no visible text but has tools/diff still show them */}
                  {!visible && (hasToolCalls || hasDiff) && (
                    <div className="space-y-2">
                      {hasToolCalls && <ToolCallView tool_calls={msg.tool_calls} />}
                      {hasDiff && msg.diff && <DiffView filename={msg.diff.filename} hunks={msg.diff.hunks} />}
                    </div>
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
