import React, { useState } from 'react';
import type { ChatMessage, ChatMode } from '../../types/chat';
import { AiCommandBar } from './AiCommandBar';
import { MessageList } from './MessageList';
import { useAI } from '../../core/ai/AIContext';

interface AiWorkspaceProps {
  messages: ChatMessage[];
  inputText: string;
  setInputText: (text: string) => void;
  onSendMessage: (attachedFiles?: string[], autoApply?: boolean) => void;
  isGenerating: boolean;
  onCancelGeneration: () => void;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  onConfirmTool?: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  statusMessage?: string;
  contextTokens?: number | null;
  contextPercentage?: number | null;
  activeSessionId?: string;
  onResumeSession?: (sessionId: string) => Promise<void>;
}

export const AiWorkspace: React.FC<AiWorkspaceProps> = ({
  messages,
  inputText,
  setInputText,
  onSendMessage,
  isGenerating,
  onCancelGeneration,
  mode,
  setMode,
  onConfirmTool,
  onConfirmPermission,
}) => {
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});

  const { onNewSession } = useAI();

  const handleToggleHunk = (msgId: string, hunkId: string, accepted: boolean) => {
    setHunkDecisions(prev => ({
      ...prev,
      [msgId]: { ...(prev[msgId] || {}), [hunkId]: accepted }
    }));
  };

  return (
    <div
      className="h-full flex flex-col font-sans select-none overflow-hidden"
      style={{ background: '#151823', borderLeft: '1px solid #2A3146' }}
    >
      {/* ── Top Navigation Bar ── */}
      <div className="px-3 py-2 shrink-0 border-b border-[#2A3146] bg-[#0E1016]">
        {/* Title Header */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider">
            AI Workspace
          </span>

          <button
            onClick={() => onNewSession()}
            className="text-[11px] font-medium text-white/80 hover:text-white bg-white/5 hover:bg-white/10 px-2 py-0.5 rounded transition-colors cursor-pointer border border-white/10"
            title="New AI Session"
          >
            + New
          </button>
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 min-h-0 relative overflow-hidden flex flex-col">
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            <MessageList
              messages={messages}
              onConfirmTool={onConfirmTool || (() => {})}
              onConfirmPermission={onConfirmPermission}
              hunkDecisions={hunkDecisions}
              onToggleHunk={handleToggleHunk}
            />
          </div>

          <div className="p-3 border-t border-[#2A3146] bg-[#151823]">
            <AiCommandBar
              inputText={inputText}
              setInputText={setInputText}
              onSend={(attachedFiles, autoApply) => onSendMessage(attachedFiles, autoApply)}
              isGenerating={isGenerating}
              onCancel={onCancelGeneration}
              mode={mode}
              setMode={setMode}
            />
          </div>
        </div>
      </div>
    </div>
  );
};


