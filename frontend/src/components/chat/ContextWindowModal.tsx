import React from 'react';
import { X, AlertTriangle, Cpu, Scissors, PlusCircle, Trash2 } from 'lucide-react';

interface ContextWindowModalProps {
  isOpen: boolean;
  onClose: () => void;
  usedTokens: number;
  totalContextWindow: number;
  systemTokens?: number;
  conversationTokens?: number;
  currentMessageTokens?: number;
  toolTokens?: number;
  modelName?: string;
  onCompress?: () => void;
  onNewChat?: () => void;
  onRemoveOldMessages?: () => void;
}

export const ContextWindowModal: React.FC<ContextWindowModalProps> = ({
  isOpen,
  onClose,
  usedTokens,
  totalContextWindow,
  systemTokens = 2100,
  conversationTokens = 35400,
  currentMessageTokens = 4500,
  toolTokens = 0,
  modelName = "Active Model",
  onCompress,
  onNewChat,
  onRemoveOldMessages,
}) => {
  if (!isOpen) return null;

  const hasLimit = typeof totalContextWindow === 'number' && totalContextWindow > 0;
  const availableTokens = hasLimit ? Math.max(0, totalContextWindow - usedTokens) : null;
  const usagePercentage = hasLimit ? Math.min(100, Math.round((usedTokens / totalContextWindow) * 100)) : null;

  // Determine warning status level
  let statusColor = "text-emerald-400";
  let progressBg = "bg-emerald-500";
  let statusText = "Normal Usage";
  if (usagePercentage === null) {
    statusColor = "text-zinc-400";
    statusText = "Context window unavailable";
  } else if (usagePercentage >= 95) {
    statusColor = "text-red-400";
    progressBg = "bg-red-500";
    statusText = "Automatic Compression Recommended";
  } else if (usagePercentage >= 90) {
    statusColor = "text-amber-400";
    progressBg = "bg-amber-500";
    statusText = "Context Nearly Full";
  } else if (usagePercentage >= 80) {
    statusColor = "text-yellow-400";
    progressBg = "bg-yellow-500";
    statusText = "Context Getting Large";
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-xs p-4 animate-[fadeIn_150ms_ease-out]">
      <div className="w-full max-w-sm bg-[#181a20] border border-white/10 rounded-2xl shadow-2xl overflow-hidden font-sans text-zinc-200 select-none">
        
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-white/5 bg-[#1f222a]">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-purple-400" />
            <span className="font-bold text-sm tracking-wide text-zinc-100">Context Window</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 space-y-4 text-xs">
          {/* Active Model Indicator */}
          <div className="flex items-center justify-between text-[11px] font-mono text-zinc-400 bg-white/[0.03] px-3 py-1.5 rounded-lg border border-white/5">
            <span>Model:</span>
            <span className="font-bold text-purple-300">{modelName}</span>
          </div>

          {/* Used & Available Tokens */}
          <div className="grid grid-cols-2 gap-2 text-center">
            <div className="p-3 bg-white/[0.02] border border-white/5 rounded-xl">
              <span className="text-[10.5px] uppercase font-bold text-zinc-400 block mb-1">Used</span>
              <span className="text-base font-black font-mono text-white">{usedTokens.toLocaleString()}</span>
              <span className="text-[10px] text-zinc-500 block">tokens</span>
            </div>
            <div className="p-3 bg-white/[0.02] border border-white/5 rounded-xl">
              <span className="text-[10.5px] uppercase font-bold text-zinc-400 block mb-1">Available</span>
              <span className="text-base font-black font-mono text-emerald-400">
                {availableTokens !== null ? availableTokens.toLocaleString() : 'N/A'}
              </span>
              <span className="text-[10px] text-zinc-500 block">tokens</span>
            </div>
          </div>

          {/* Progress Bar & Status */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-zinc-400">Total Limit</span>
              <span className="text-zinc-200 font-bold">
                {hasLimit ? totalContextWindow.toLocaleString() : 'Unavailable'}
              </span>
            </div>
            <div className="w-full h-2.5 bg-zinc-800 rounded-full overflow-hidden p-0.5 border border-white/5">
              <div
                className={`h-full rounded-full transition-all duration-300 ${progressBg}`}
                style={{ width: `${usagePercentage ?? 0}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[10.5px] pt-0.5">
              <span className={`font-semibold flex items-center gap-1 ${statusColor}`}>
                {usagePercentage !== null && usagePercentage >= 80 && <AlertTriangle className="w-3 h-3 shrink-0" />}
                {statusText}
              </span>
              <span className="font-bold font-mono text-zinc-300">
                {usagePercentage !== null ? `${usagePercentage}%` : '?%'}
              </span>
            </div>
          </div>

          {/* Token Breakdown Table */}
          <div className="border border-white/5 rounded-xl bg-black/20 p-3 space-y-2 font-mono text-[11.5px]">
            <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider font-sans mb-1">
              Token Breakdown
            </div>
            <div className="flex items-center justify-between py-1 border-b border-white/5">
              <span className="text-zinc-400">System Prompt</span>
              <span className="text-zinc-200 font-semibold">{systemTokens.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-white/5">
              <span className="text-zinc-400">Conversation</span>
              <span className="text-zinc-200 font-semibold">{conversationTokens.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-white/5">
              <span className="text-zinc-400">Current Message</span>
              <span className="text-zinc-200 font-semibold">{currentMessageTokens.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-zinc-400">Tools & Schemas</span>
              <span className="text-zinc-200 font-semibold">{toolTokens.toLocaleString()}</span>
            </div>
          </div>

          {/* Context Management Actions */}
          <div className="space-y-1.5 pt-1">
            <button
              onClick={onCompress}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 rounded-xl text-xs text-purple-200 font-semibold transition-colors cursor-pointer"
            >
              <Scissors className="w-3.5 h-3.5 text-purple-400" />
              <span>Compress Conversation</span>
            </button>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={onNewChat}
                className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[11px] text-zinc-300 font-medium transition-colors cursor-pointer"
              >
                <PlusCircle className="w-3.5 h-3.5 text-emerald-400" />
                <span>Start New Chat</span>
              </button>
              <button
                onClick={onRemoveOldMessages}
                className="flex items-center justify-center gap-1.5 py-1.5 px-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[11px] text-zinc-300 font-medium transition-colors cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5 text-amber-400" />
                <span>Trim Old Messages</span>
              </button>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
