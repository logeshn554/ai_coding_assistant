import React from 'react';
import type { ChatMessage } from '../../types/chat';
import { Sparkles, Check } from 'lucide-react';
import { ConfirmDialog } from './ConfirmDialog';
import { ToolCallView } from './ToolCallView';

interface MessageListProps {
  messages: ChatMessage[];
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  hunkDecisions: Record<string, Record<string, boolean>>;
  onToggleHunk: (msgId: string, hunkId: string, accepted: boolean) => void;
  renderMessageContent: (content: string) => React.ReactNode;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  onConfirmTool,
  onConfirmPermission,
  onConfirmPortConflict,
  hunkDecisions,
  onToggleHunk,
  renderMessageContent,
}) => {
  const renderContentString = (content: any): string => {
    if (content === null || content === undefined) return '';
    if (typeof content === 'string') return content;
    try {
      return JSON.stringify(content, null, 2);
    } catch {
      return String(content);
    }
  };

  return (
    <div className="space-y-3 select-text">
      {messages.map((msg) => {
        const isUser = msg.role === 'user';

        // 1. RENDER USER MESSAGE
        if (isUser) {
          return (
            <div key={msg.id} className="flex gap-2 max-w-[95%] items-start ml-auto flex-row-reverse select-text mb-4">
              <div className="w-5 h-5 rounded-sm bg-[#8b5cf6] text-white shrink-0 flex items-center justify-center text-[9px] font-bold select-none">
                U
              </div>
              <div className="flex flex-col items-end max-w-[calc(100%-1.5rem)]">
                <div className="p-2 bg-[#2a2a2b] border border-[#2d2d2d] text-xs text-white rounded-none leading-relaxed whitespace-pre-wrap select-text">
                  {renderMessageContent(renderContentString(msg.content).trim())}
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
          const hasThinking = msg.thinkingSteps && msg.thinkingSteps.length > 0;
          const hasContent = msg.content && typeof msg.content === 'string' && msg.content.trim() !== '';

          if (!hasThinking && !hasContent) return null;

          return (
            <div key={msg.id} className="flex gap-2.5 max-w-[95%] items-start select-text mb-4 animate-fade-in">
              <div className="w-6 h-6 rounded-md bg-[#8b5cf6]/10 border border-[#8b5cf6]/20 text-violet-400 shrink-0 flex items-center justify-center text-[10px] font-bold select-none shadow-sm shadow-violet-500/5">
                AI
              </div>
              <div className="flex flex-col items-start max-w-[calc(100%-1.75rem)] select-text w-full">
                {/* Progressive Thinking Steps */}
                {hasThinking && (
                  <div className="w-full bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)]/50 rounded-lg p-3 mb-2 space-y-2 select-none shadow-sm animate-slide-down">
                    <div className="flex items-center gap-2 text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                      <Sparkles className="w-3 h-3 text-violet-400 animate-pulse-subtle shrink-0" />
                      <span>Execution Flow</span>
                    </div>
                    <div className="space-y-1.5 pl-1">
                      {(msg.thinkingSteps || []).map((step: string, stepIdx: number) => {
                        const isCompleted = step.startsWith('✓');
                        const stepText = isCompleted ? step.substring(1).trim() : step;
                        return (
                          <div key={stepIdx} className="flex items-center gap-2 text-[11px] text-gray-300 animate-fade-in">
                            {isCompleted ? (
                              <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                            ) : (
                              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-ping shrink-0" />
                            )}
                            <span className={isCompleted ? 'text-gray-400 font-medium' : 'text-gray-200 font-semibold'}>
                              {stepText}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Actual Response Content */}
                {hasContent && (
                  <div className="p-3 bg-[#141414] border border-[#2d2d2d] text-xs text-gray-300 rounded-lg leading-relaxed whitespace-pre-wrap select-text w-full shadow-md font-sans">
                    {renderMessageContent(renderContentString(msg.content).trim())}
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
