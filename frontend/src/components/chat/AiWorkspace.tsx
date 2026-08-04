import React, { useState } from 'react';
import type { ChatMessage, ChatMode } from '../../types/chat';
import { Plus, Trash2, Info, X } from 'lucide-react';
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

  const { onNewSession, taskMemory, isGenerating: isGeneratingContext, handleSendMessage } = useAI();

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
      <div className="px-3.5 py-2.5 shrink-0 border-b border-[#2A3146] bg-[#0E1016] select-none">
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] font-bold text-zinc-300 uppercase tracking-wider">
            AI Assistant
          </span>

          <div className="flex items-center gap-2">
            {/* + New Chat Button */}
            <button
              onClick={() => onNewSession()}
              className="btn-interactive flex items-center gap-1 text-[10.5px] font-bold text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1 rounded-md transition-colors cursor-pointer border border-zinc-800/80"
              title="New AI Chat Session"
            >
              <Plus className="w-3 h-3 text-zinc-400" />
              <span>New Chat</span>
            </button>

            {/* Clear/Trash Button */}
            <button
              onClick={() => onNewSession()}
              className="btn-interactive p-1 rounded bg-transparent hover:bg-zinc-900 text-zinc-400 hover:text-red-400 transition-colors cursor-pointer"
              title="Clear Session History"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>

            {/* Info Button */}
            <button
              className="btn-interactive p-1 rounded bg-transparent hover:bg-zinc-900 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="AI Assistant Information"
            >
              <Info className="w-3.5 h-3.5" />
            </button>

            {/* Close/Hide Button */}
            <button
              className="btn-interactive p-1 rounded bg-transparent hover:bg-zinc-900 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Close AI Assistant Panel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
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
              taskMemory={taskMemory}
              onContinue={() => handleSendMessage('continue', 'Agent', true)}
              isGenerating={isGeneratingContext}
              onSuggest={setInputText}
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


