import React, { useState, useRef, useEffect } from 'react';
import { Sparkles, Send, X, CornerDownLeft, Loader2, Code2 } from 'lucide-react';
import type { ChatMode } from '../../types/chat';

interface InlineChatPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  position: { top: number; left: number };
  lineNumber: number;
  selectedText: string;
  filePath: string;
  onApplyInlineEdit: (prompt: string, mode: ChatMode) => Promise<void>;
}

export const InlineChatPopover: React.FC<InlineChatPopoverProps> = ({
  isOpen,
  onClose,
  position,
  lineNumber,
  selectedText,
  filePath,
  onApplyInlineEdit
}) => {
  const [prompt, setPrompt] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [mode, setMode] = useState<ChatMode>('Agent');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setPrompt('');
      setIsExecuting(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!prompt.trim() || isExecuting) return;

    setIsExecuting(true);
    try {
      await onApplyInlineEdit(prompt, mode);
      onClose();
    } catch (err) {
      console.error('Inline chat execution failed:', err);
    } finally {
      setIsExecuting(false);
    }
  };

  const filename = filePath.split(/[\\/]/).pop() || filePath;

  return (
    <div
      className="fixed z-50 w-96 rounded-xl border border-[var(--dp-border-mid)] shadow-[var(--dp-shadow-float)] overflow-hidden font-sans animate-scale-in"
      style={{
        top: Math.max(80, position.top),
        left: Math.max(200, Math.min(window.innerWidth - 420, position.left)),
        background: 'var(--dp-bg-elevated)',
        backdropFilter: 'blur(16px)',
      }}
    >
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--dp-border)] flex items-center justify-between bg-white/4">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-md bg-gradient-to-br from-[#7c6af0] to-[#4f8df5] flex items-center justify-center">
            <Sparkles className="w-3 h-3 text-white" />
          </div>
          <span className="text-[11px] font-bold text-[var(--dp-text-bright)]">Inline AI Edit</span>
          <span className="text-[9px] font-mono text-[var(--dp-text-muted)] bg-white/6 px-1.5 py-0.5 rounded">
            {filename}:{lineNumber}
          </span>
        </div>
        <button
          onClick={onClose}
          className="w-5 h-5 flex items-center justify-center rounded text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/8 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Selected text indicator */}
      {selectedText && (
        <div className="px-3 py-1.5 border-b border-[var(--dp-border)] bg-black/20 text-[10px] text-[var(--dp-text-muted)] flex items-center gap-1.5 font-mono truncate">
          <Code2 className="w-3 h-3 text-[var(--dp-accent)] shrink-0" />
          <span className="truncate">Selection: "{selectedText.trim().slice(0, 45)}..."</span>
        </div>
      )}

      {/* Input row */}
      <form onSubmit={handleSubmit} className="p-2.5 flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onClose();
          }}
          placeholder="Ask AI to edit, refactor, or generate code..."
          disabled={isExecuting}
          className="flex-1 bg-white/5 border border-[var(--dp-border)] focus:border-[var(--dp-accent)] text-[12px] text-[var(--dp-text-bright)] placeholder-[var(--dp-text-muted)] px-3 py-1.5 rounded-lg outline-none transition-colors"
        />

        <button
          type="submit"
          disabled={!prompt.trim() || isExecuting}
          className="px-3 py-1.5 rounded-lg bg-[var(--dp-accent)] text-white text-[11px] font-semibold flex items-center gap-1 hover:opacity-90 disabled:opacity-40 transition-all shrink-0 cursor-pointer"
        >
          {isExecuting ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <>
              <Send className="w-3 h-3" />
              <CornerDownLeft className="w-2.5 h-2.5 opacity-60" />
            </>
          )}
        </button>
      </form>

      {/* Mode pills footer */}
      <div className="px-3 py-1.5 border-t border-[var(--dp-border)] bg-black/10 flex items-center justify-between text-[10px]">
        <div className="flex items-center gap-1">
          {(['Agent', 'Ask', 'Plan'] as ChatMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`px-2 py-0.5 rounded text-[9px] font-semibold transition-colors cursor-pointer ${
                mode === m
                  ? 'bg-[var(--dp-accent-dim)] text-[var(--dp-accent)] border border-[var(--dp-accent)]/30'
                  : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)]'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
        <span className="text-[9px] text-[var(--dp-text-muted)]">Esc to close</span>
      </div>
    </div>
  );
};
