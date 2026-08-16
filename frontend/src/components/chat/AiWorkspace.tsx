import React, { useState } from 'react';
import type { ChatMessage, ChatMode } from '../../types/chat';
import { Plus, RotateCcw } from 'lucide-react';
import { AiCommandBar } from './AiCommandBar';
import { MessageList } from './MessageList';
import { useAI } from '../../core/ai/AIContext';
import { ContextWindowModal } from './ContextWindowModal';
import { ChatHistoryDrawer } from './ChatHistoryDrawer';


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
  contextTokens,
  contextPercentage,
  activeSessionId,
  onResumeSession,
}) => {
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});

  // Modals state
  const [isContextModalOpen, setIsContextModalOpen] = useState(false);
  const [isHistoryDrawerOpen, setIsHistoryDrawerOpen] = useState(false);
  const [activeModelName, setActiveModelName] = useState('Select Model');

  React.useEffect(() => {
    fetch('/api/providers/dashboard')
      .then((res) => res.ok ? res.json() : null)
      .then((data) => {
        if (data && data.providers && data.providers.length > 0) {
          const active = data.providers.find((p: any) => p.is_active) || data.providers[0];
          if (active && active.model_name) {
            setActiveModelName(active.model_name);
          }
        }
      })
      .catch(() => {});
  }, []);

  const { onNewSession, onDeleteSession, isGenerating: isGeneratingContext, handleSendMessage } = useAI();

  const handleToggleHunk = (msgId: string, hunkId: string, accepted: boolean) => {
    setHunkDecisions(prev => ({
      ...prev,
      [msgId]: { ...(prev[msgId] || {}), [hunkId]: accepted }
    }));
  };

  const usedT = contextTokens || (messages.length * 850);
  const totalWin = 196608;
  const pct = typeof contextPercentage === 'number' ? contextPercentage : Math.min(100, Math.round((usedT / totalWin) * 100));

  return (
    <div
      className="h-full flex flex-col font-sans select-none overflow-hidden"
      style={{ background: '#151823', borderLeft: '1px solid #2A3146' }}
    >
      {/* ── Top Chat Header ── */}
      <div className="px-3.5 py-2 shrink-0 border-b border-[#2A3146] bg-[#0E1016] select-none">
        <div className="flex items-center justify-between gap-2">
          
          {/* Left: Chat Title */}
          <div className="flex items-center gap-2 font-semibold text-xs text-zinc-300">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse shrink-0" />
            <span>DevPilot AI</span>
          </div>

          {/* Right Controls: History & New Chat */}
          <div className="flex items-center gap-2">
            {/* History Button */}
            <button
              onClick={() => setIsHistoryDrawerOpen(true)}
              className="flex items-center gap-1 text-xs font-semibold text-zinc-300 hover:text-white bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 rounded-xl border border-zinc-800 transition-colors cursor-pointer"
              title="View Chat History"
            >
              <RotateCcw className="w-3.5 h-3.5 text-purple-400" />
              <span>History</span>
            </button>

            {/* + New Chat Button */}
            <button
              onClick={() => onNewSession()}
              className="flex items-center gap-1 text-xs font-bold text-white bg-purple-600 hover:bg-purple-500 px-2.5 py-1.5 rounded-xl transition-all shadow-sm cursor-pointer"
              title="Start New Chat Session"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New</span>
            </button>
          </div>
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 min-h-0 relative overflow-hidden flex flex-col">
        <MessageList
          messages={messages}
          onConfirmTool={onConfirmTool || (() => {})}
          onConfirmPermission={onConfirmPermission}
          hunkDecisions={hunkDecisions}
          onToggleHunk={handleToggleHunk}
          isGenerating={isGeneratingContext}
          onSuggest={setInputText}
        />

        {/* Command Bar Input with Context Symbol near Send button */}
        <div className="p-3 pt-0 shrink-0">
          <AiCommandBar
            inputText={inputText}
            setInputText={setInputText}
            onSend={(attachedFiles, autoApply) => onSendMessage(attachedFiles, autoApply)}
            isGenerating={isGenerating}
            onCancel={onCancelGeneration}
            mode={mode}
            setMode={setMode}
            onOpenContextModal={() => setIsContextModalOpen(true)}
            contextPercentage={pct}
          />
        </div>
      </div>

      {/* Modals & Drawers */}
      <ContextWindowModal
        isOpen={isContextModalOpen}
        onClose={() => setIsContextModalOpen(false)}
        usedTokens={usedT}
        totalContextWindow={totalWin}
        modelName={activeModelName}
        onCompress={() => {
          setIsContextModalOpen(false);
          handleSendMessage("Please compress and summarize our chat context to retain key requirements.", "Agent", true);
        }}
        onNewChat={() => {
          setIsContextModalOpen(false);
          onNewSession();
        }}
      />

      <ChatHistoryDrawer
        isOpen={isHistoryDrawerOpen}
        onClose={() => setIsHistoryDrawerOpen(false)}
        activeSessionId={activeSessionId}
        onSelectSession={(sId) => {
          if (onResumeSession) onResumeSession(sId);
        }}
        onNewSession={onNewSession}
        onDeleteSession={(sId) => {
          onDeleteSession(sId);
        }}
      />


    </div>
  );
};



