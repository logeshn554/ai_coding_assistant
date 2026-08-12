import React, { useState } from 'react';
import { Database, Layers, Info } from 'lucide-react';

export interface ContextInspectorItem {
  file: string;
  score: number;
  source: string;
  reason: string;
}

interface ContextInspectorProps {
  tokensEstimate: number;
  items: ContextInspectorItem[];
}

export const ContextInspector: React.FC<ContextInspectorProps> = ({ tokensEstimate, items }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="context-inspector my-2 text-xs font-sans">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full p-2 bg-base-200 hover:bg-base-300 rounded border border-base-300"
      >
        <div className="flex items-center gap-2 text-base-content/80">
          <Database className="w-4 h-4 text-primary" />
          <span className="font-semibold">Context Engine Indicator</span>
          <span className="badge badge-xs badge-neutral">{items.length} files</span>
        </div>
        <div className="flex items-center gap-2 text-base-content/60 font-mono text-[11px]">
          <span>~{tokensEstimate} tokens</span>
          <Info className="w-3.5 h-3.5" />
        </div>
      </button>

      {isOpen && (
        <div className="mt-2 p-3 bg-base-100 rounded border border-base-300 space-y-2 shadow-inner">
          <h4 className="font-semibold text-xs text-base-content flex items-center gap-1.5 pb-1 border-b border-base-200">
            <Layers className="w-3.5 h-3.5 text-secondary" /> Context Provenance & Ranking
          </h4>

          {items.length === 0 ? (
            <div className="text-xs text-base-content/50 italic py-1">No context files retrieved yet.</div>
          ) : (
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {items.map((item, idx) => (
                <div key={idx} className="p-1.5 bg-base-200/60 rounded border border-base-300/50 flex justify-between items-center text-[11px]">
                  <div className="truncate max-w-[240px]">
                    <div className="font-mono font-medium truncate">{item.file}</div>
                    <div className="text-[10px] text-base-content/60">{item.reason}</div>
                  </div>

                  <div className="text-right">
                    <div className="badge badge-xs badge-primary font-mono">{item.score.toFixed(2)}</div>
                    <div className="text-[9px] text-base-content/50 uppercase tracking-wider">{item.source}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
