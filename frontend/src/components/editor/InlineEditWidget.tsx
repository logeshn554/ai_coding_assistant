import React, { useState } from 'react';
import { Sparkles, X, Check } from 'lucide-react';

interface InlineEditWidgetProps {
  filePath: string;
  selectedText: string;
  startLine: number;
  endLine: number;
  onSubmit: (prompt: string) => void;
  onCancel: () => void;
}

export const InlineEditWidget: React.FC<InlineEditWidgetProps> = ({
  filePath,
  selectedText,
  startLine,
  endLine,
  onSubmit,
  onCancel,
}) => {
  const [prompt, setPrompt] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && prompt.trim()) {
      e.preventDefault();
      onSubmit(prompt);
    }
  };

  return (
    <div className="inline-edit-widget p-3 rounded-lg bg-base-200 border border-primary/40 shadow-xl my-2 text-xs font-sans">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 font-semibold text-primary">
          <Sparkles className="w-4 h-4" />
          <span>Inline AI Edit</span>
          <span className="text-[10px] text-base-content/60 font-mono">
            {filePath}:{startLine}-{endLine}
          </span>
        </div>
        <button onClick={onCancel} className="btn btn-xs btn-ghost btn-circle">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="bg-base-300 p-2 rounded text-[11px] font-mono max-h-24 overflow-y-auto mb-2 text-base-content/70">
        {selectedText}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Describe edit (e.g. Add error handling and improve types)..."
          className="input input-xs input-bordered w-full"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        <button
          onClick={() => prompt.trim() && onSubmit(prompt)}
          className="btn btn-xs btn-primary gap-1"
          disabled={!prompt.trim()}
        >
          <Check className="w-3.5 h-3.5" /> Generate
        </button>
      </div>
    </div>
  );
};
