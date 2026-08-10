import React, { useRef, useEffect } from 'react';
import type { ChatMessage, TaskMemoryData } from '../../types/chat';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { ProgressCard } from './ProgressCard';
import { TaskProgressPanel } from './TaskProgressPanel';
import { useEditor } from '../../core/editor/EditorContext';

interface MessageListProps {
  messages: ChatMessage[];
  onConfirmTool: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  onConfirmPortConflict?: (toolCallId: string, action: 'stop' | 'next_port' | 'cancel') => void;
  hunkDecisions: Record<string, Record<string, boolean>>;
  onToggleHunk: (msgId: string, hunkId: string, accepted: boolean) => void;
  renderMessageContent?: (content: string) => React.ReactNode;
  onRunCommand?: (command: string) => void;
  taskMemory?: TaskMemoryData | null;
  onContinue?: () => void;
  isGenerating?: boolean;
  onSuggest?: (text: string) => void;
}

// ── User Suggestion Tip Card ──
const EmptyState: React.FC<{ onSuggest: (text: string) => void }> = ({ onSuggest }) => (
  <div className="flex flex-col items-center justify-center h-full gap-5 px-8 py-12 select-none">
    <div className="text-center space-y-1.5 max-w-sm">
      <p className="text-[15px] font-bold text-zinc-100 font-sans">Ask DevPilot anything</p>
      <p className="text-[12.5px] leading-relaxed text-zinc-400 font-sans">
        Chat, plan, or let the Agent write code, execute shell commands, and run validation tests.
      </p>
    </div>
    <div className="flex flex-wrap justify-center gap-2 max-w-md mt-1">
      {[
        'Refactor active file',
        'Fix compiler warnings',
        'Write documentation guide',
        'Optimize execution loop',
      ].map((tip) => (
        <span
          key={tip}
          onClick={() => onSuggest(tip)}
          className="px-3 py-1.5 rounded-lg text-[11px] font-medium cursor-pointer transition-all bg-zinc-900 border border-zinc-800 text-zinc-300 hover:bg-zinc-800 hover:text-white hover:border-zinc-700/80 font-sans shadow-sm"
        >
          {tip}
        </span>
      ))}
    </div>
  </div>
);

// ── Conversation Turn Types ──
export interface UserTurn {
  kind: 'user';
  msg: ChatMessage;
}

export interface AiTurn {
  kind: 'ai';
  id: string;
  allMessages: ChatMessage[];
  assistantMessages: ChatMessage[];
  toolMessages: ChatMessage[];
  confirmMessages: ChatMessage[];
  isGenerating?: boolean;
}

export type ConversationTurn = UserTurn | AiTurn;

// Grouping consecutive messages between user prompts into cohesive AI turns
function groupIntoTurns(messages: ChatMessage[], isGeneratingGlobal?: boolean): ConversationTurn[] {
  const turns: ConversationTurn[] = [];
  let currentAiTurn: AiTurn | null = null;

  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    const messageId = m.id || `msg_${i}`;
    if (m.role === 'user') {
      if (currentAiTurn) {
        turns.push(currentAiTurn);
        currentAiTurn = null;
      }
      turns.push({ kind: 'user', msg: { ...m, id: messageId } });
    } else {
      if (!currentAiTurn) {
        currentAiTurn = {
          kind: 'ai',
          id: messageId,
          allMessages: [],
          assistantMessages: [],
          toolMessages: [],
          confirmMessages: [],
        };
      }
      const messageWithId = { ...m, id: messageId };
      currentAiTurn.allMessages.push(messageWithId);
      if (m.role === 'assistant') {
        if (m.isConfirmPending || m.isPermissionRequest || m.isPortConflictRequest || m.isCostConfirmationRequest) {
          currentAiTurn.confirmMessages.push(messageWithId);
        } else {
          currentAiTurn.assistantMessages.push(messageWithId);
        }
      } else if (m.role === 'tool') {
        currentAiTurn.toolMessages.push(messageWithId);
      } else {
        currentAiTurn.assistantMessages.push(messageWithId);
      }
    }
  }

  if (currentAiTurn) {
    currentAiTurn.isGenerating = isGeneratingGlobal;
    turns.push(currentAiTurn);
  }

  return turns;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  onConfirmTool,
  onConfirmPermission,
  onConfirmPortConflict,
  hunkDecisions,
  onToggleHunk,
  onRunCommand,
  taskMemory,
  onContinue,
  isGenerating,
  onSuggest,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { handleSelectFile } = useEditor();

  // Auto-scroll on new message append or stream updates
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  const handleSuggestionClick = (tip: string) => {
    if (onSuggest) {
      onSuggest(tip);
    }
  };

  if (messages.length === 0) return <EmptyState onSuggest={handleSuggestionClick} />;

  const turns = groupIntoTurns(messages, isGenerating);

  // Read status message from the active context if available
  const activeStatusMessage = isGenerating ? 'Executing agent workflow...' : null;

  return (
    <div
      className="flex-1 overflow-y-auto select-text font-sans scrollbar-thin"
      style={{
        padding: '16px 20px',
        background: '#151823', // Matches premium dark palette of AiWorkspace
      }}
    >
      <div className="mx-auto space-y-4 max-w-[840px]">
        {turns.map((turn) => {
          if (turn.kind === 'user') {
            return <UserMessage key={turn.msg.id} msg={turn.msg} />;
          }

          return (
            <AssistantMessage
              key={turn.id}
              turn={turn}
              onConfirmTool={onConfirmTool}
              onConfirmPermission={onConfirmPermission}
              onConfirmPortConflict={onConfirmPortConflict}
              hunkDecisions={hunkDecisions}
              onToggleHunk={onToggleHunk}
              onRunCommand={onRunCommand}
              onOpenFile={handleSelectFile}
              statusMessage={activeStatusMessage}
            />
          );
        })}

        {/* Streaming Progress indicators */}
        <ProgressCard statusMessage={activeStatusMessage} isGenerating={Boolean(isGenerating)} />

        {/* Task continuation board */}
        {taskMemory && (
          <div className="px-2 py-2">
            <TaskProgressPanel
              taskMemory={taskMemory}
              onContinue={onContinue}
              isGenerating={isGenerating}
            />
          </div>
        )}
        
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
export default MessageList;
