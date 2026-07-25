import React, { useState, useRef, useEffect } from 'react';
import { Sparkles, Send, X, CornerDownLeft, Loader2, Code2, Check } from 'lucide-react';
import type { ChatMode } from '../../types/chat';

interface InlineChatPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  position: { top: number; left: number };
  lineNumber: number;
  selectedText: string;
  filePath: string;
  onApplyInlineEdit: (prompt: string, mode: ChatMode) => Promise<void>;
  /** Called when user clicks Accept to splice the AI suggestion into the editor */
  onAcceptEdit?: (suggestion: string) => void;
}

export const InlineChatPopover: React.FC<InlineChatPopoverProps> = ({
  isOpen,
  onClose,
  position,
  lineNumber,
  selectedText,
  filePath,
  onApplyInlineEdit,
  onAcceptEdit,
}) => {
  const [prompt, setPrompt] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedSuggestion, setStreamedSuggestion] = useState('');
  const [mode, setMode] = useState<ChatMode>('Agent');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setPrompt('');
      setIsExecuting(false);
      setIsStreaming(false);
      setStreamedSuggestion('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Stream response from /api/completions
  const streamSuggestion = async () => {
    if (!prompt.trim() || isStreaming) return;
    setIsStreaming(true);
    setStreamedSuggestion('');
    try {
      const systemPrompt = selectedText
        ? `You are a code editor assistant. Rewrite the following code selection per the instruction. Output ONLY the replacement code, no explanations, no markdown fences.\n\nSelection:\n${selectedText}\n\nInstruction: ${prompt}`
        : `You are a code editor assistant. Generate code at line ${lineNumber} in ${filePath} per the instruction. Output ONLY the code, no explanations.\n\nInstruction: ${prompt}`;

      const res = await fetch('/api/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prefix: systemPrompt,
          suffix: '',
          language: filePath.split('.').pop() || 'text',
          file_path: filePath,
          max_tokens: 512,
        }),
      });
      if (!res.ok) throw new Error('Completions request failed');
      const data = await res.json();
      setStreamedSuggestion((data.completion || '').trimEnd());
    } catch (err) {
      console.error('Inline chat stream error:', err);
      setStreamedSuggestion('// Error generating suggestion');
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!prompt.trim() || isExecuting) return;
    // Try quick stream first; if onAcceptEdit not available, fall back to chat
    if (onAcceptEdit) {
      await streamSuggestion();
    } else {
      setIsExecuting(true);
      try {
        await onApplyInlineEdit(prompt, mode);
        onClose();
      } catch (err) {
        console.error('Inline chat execution failed:', err);
      } finally {
        setIsExecuting(false);
      }
    }
  };

  const handleAccept = () => {
    if (onAcceptEdit && streamedSuggestion) {
      onAcceptEdit(streamedSuggestion);
    }
  };

  const filename = filePath.split(/[\\/]/).pop() || filePath;

  return (
    <div
      className="fixed z-50 w-[420px] overflow-hidden font-sans"
      style={{
        top: Math.max(80, position.top),
        left: Math.max(200, Math.min(window.innerWidth - 440, position.left)),
        background: 'var(--dp-bg-elevated)',
        border: '1px solid var(--dp-border-mid)',
        borderRadius: 'var(--dp-radius-lg)',
        boxShadow: 'var(--dp-shadow-float)',
        backdropFilter: 'blur(16px)',
      }}
    >
      {/* Header */}
      <div
        className="px-3 py-2 flex items-center justify-between"
        style={{ borderBottom: '1px solid var(--dp-border)', background: 'rgba(255,255,255,0.03)' }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-5 h-5 rounded-md flex items-center justify-center"
            style={{ background: 'var(--dp-accent-gradient)' }}
          >
            <Sparkles className="w-3 h-3 text-white" />
          </div>
          <span className="text-[11px] font-bold" style={{ color: 'var(--dp-text-bright)' }}>
            Inline AI Edit
          </span>
          <span
            className="text-[9px] font-mono px-1.5 py-0.5 rounded"
            style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--dp-text-muted)' }}
          >
            {filename}:{lineNumber}
          </span>
        </div>
        <button
          onClick={onClose}
          className="w-5 h-5 flex items-center justify-center rounded transition-colors cursor-pointer"
          style={{ color: 'var(--dp-text-muted)' }}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Selection indicator */}
      {selectedText && (
        <div
          className="px-3 py-1.5 flex items-center gap-1.5 text-[10px] font-mono truncate"
          style={{
            borderBottom: '1px solid var(--dp-border)',
            background: 'rgba(0,0,0,0.2)',
            color: 'var(--dp-text-muted)',
          }}
        >
          <Code2 className="w-3 h-3 shrink-0" style={{ color: 'var(--dp-accent)' }} />
          <span className="truncate">
            Selection: "{selectedText.trim().slice(0, 50)}{selectedText.length > 50 ? '…' : ''}"
          </span>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-2.5 flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Escape') onClose(); }}
          placeholder="Ask AI to edit, refactor, or generate code…"
          disabled={isExecuting || isStreaming}
          className="flex-1 text-[12px] px-3 py-1.5 rounded-lg outline-none transition-colors"
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid var(--dp-border)',
            color: 'var(--dp-text-bright)',
          }}
        />
        <button
          type="submit"
          disabled={!prompt.trim() || isExecuting || isStreaming}
          className="px-3 py-1.5 rounded-lg text-[11px] font-semibold flex items-center gap-1 transition-all shrink-0 cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--dp-accent)', color: '#fff' }}
        >
          {isStreaming
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <><Send className="w-3 h-3" /><CornerDownLeft className="w-2.5 h-2.5 opacity-60" /></>}
        </button>
      </form>

      {/* Streamed suggestion preview */}
      {streamedSuggestion && (
        <div style={{ borderTop: '1px solid var(--dp-border)' }}>
          <div
            className="px-3 py-1.5 text-[9px] font-bold uppercase tracking-widest flex items-center justify-between"
            style={{ background: 'rgba(0,0,0,0.15)', color: 'var(--dp-text-muted)' }}
          >
            <span>AI Suggestion</span>
            <button
              onClick={handleAccept}
              className="flex items-center gap-1 px-2 py-0.5 rounded font-semibold text-[9px] cursor-pointer transition-colors"
              style={{
                background: 'color-mix(in srgb, var(--dp-success) 14%, transparent)',
                color: 'var(--dp-success)',
                border: '1px solid color-mix(in srgb, var(--dp-success) 30%, transparent)',
              }}
            >
              <Check className="w-2.5 h-2.5" /> Accept
            </button>
          </div>
          <pre
            className="px-3 py-2 text-[10px] font-mono overflow-x-auto"
            style={{
              color: 'var(--dp-text-primary)',
              background: 'var(--dp-bg-primary)',
              maxHeight: '160px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {streamedSuggestion}
          </pre>
        </div>
      )}

      {/* Footer */}
      <div
        className="px-3 py-1.5 flex items-center justify-between text-[10px]"
        style={{ borderTop: '1px solid var(--dp-border)', background: 'rgba(0,0,0,0.1)' }}
      >
        <div className="flex items-center gap-1">
          {(['Agent', 'Ask', 'Plan'] as ChatMode[]).map(m => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className="px-2 py-0.5 rounded text-[9px] font-semibold transition-colors cursor-pointer"
              style={
                mode === m
                  ? { background: 'var(--dp-accent-dim)', color: 'var(--dp-accent)', border: '1px solid color-mix(in srgb, var(--dp-accent) 30%, transparent)' }
                  : { color: 'var(--dp-text-muted)' }
              }
            >
              {m}
            </button>
          ))}
        </div>
        <span style={{ color: 'var(--dp-text-muted)', fontSize: '9px' }}>Esc to close</span>
      </div>
    </div>
  );
};
