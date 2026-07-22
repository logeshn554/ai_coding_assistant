import React, { useState } from 'react';
import { Wrench, ChevronDown, ChevronRight, CheckCircle2, XCircle } from 'lucide-react';
import type { ChatMessage, ToolCall } from '../../types/chat';

interface ToolCallViewProps {
  tool_calls?: ToolCall[];
  msg?: ChatMessage;
}

export const ToolCallView: React.FC<ToolCallViewProps> = ({ tool_calls, msg }) => {
  const [expandedIndex, setExpandedIndex] = useState<Record<number, boolean>>({});

  const toggleExpand = (idx: number) => {
    setExpandedIndex(prev => ({ ...prev, [idx]: !prev[idx] }));
  };

  // Convert single tool message into ToolCall format if needed
  const normalizedCalls: ToolCall[] = tool_calls || (msg ? [{
    name: msg.name || 'tool_execution',
    args: typeof msg.content === 'object' && msg.content !== null ? msg.content : {},
    result: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content, null, 2)
  }] : []);

  if (normalizedCalls.length === 0) return null;

  return (
    <div className="space-y-2 w-full my-2">
      {normalizedCalls.map((tc, idx) => {
        const isExpanded = expandedIndex[idx] ?? false;
        const hasResult = Boolean(tc.result);
        const isSuccess = msg?.status !== 'error';

        return (
          <div
            key={`${tc.name}-${idx}`}
            className="border-l-2 border-l-blue-500 bg-zinc-900/90 border border-zinc-800 rounded-r-lg p-2.5 font-mono text-[11px] shadow-sm"
          >
            {/* Tool Header */}
            <div className="flex items-center justify-between pb-1.5 border-b border-zinc-800/80">
              <div className="flex items-center gap-2">
                <Wrench className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                <span className="font-bold text-blue-300 text-[12px]">{tc.name}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {msg?.status && (
                  <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                    isSuccess ? 'bg-green-950 text-green-400 border border-green-800/50' : 'bg-red-950 text-red-400 border border-red-800/50'
                  }`}>
                    {isSuccess ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                    {isSuccess ? 'SUCCESS' : 'FAILED'}
                  </span>
                )}
              </div>
            </div>

            {/* Tool Key-Value Arguments */}
            {tc.args && Object.keys(tc.args).length > 0 && (
              <div className="mt-2 space-y-1 bg-zinc-950/60 p-2 rounded border border-zinc-800/60 text-[11px]">
                {Object.entries(tc.args).map(([k, v]) => (
                  <div key={k} className="flex items-start gap-2 overflow-x-auto scrollbar-none">
                    <span className="text-zinc-500 shrink-0 font-semibold">{k}:</span>
                    <span className="text-zinc-300 whitespace-pre-wrap break-all">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Tool Result Collapsible */}
            {hasResult && (
              <div className="mt-2 pt-1">
                <button
                  type="button"
                  onClick={() => toggleExpand(idx)}
                  className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-200 cursor-pointer font-sans"
                >
                  {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  <span>{isExpanded ? 'Hide Result' : 'View Result Output'}</span>
                </button>

                {isExpanded && (
                  <pre className="mt-1.5 p-2 bg-zinc-950 text-zinc-300 text-[10.5px] max-h-48 overflow-y-auto whitespace-pre-wrap select-text rounded border border-zinc-800 font-mono scrollbar-thin">
                    {tc.result}
                  </pre>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
