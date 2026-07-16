import React from 'react';
import type { ChatMessage } from '../../types/chat';

interface ToolCallViewProps {
  msg: ChatMessage;
}

export const ToolCallView: React.FC<ToolCallViewProps> = ({ msg }) => {
  const renderContentString = (content: any): string => {
    if (content === null || content === undefined) return '';
    if (typeof content === 'string') return content;
    try {
      return JSON.stringify(content, null, 2);
    } catch {
      return String(content);
    }
  };

  const isSuccess = msg.status === 'success';

  return (
    <div className="flex gap-2 max-w-[95%] items-start select-text mb-3">
      <div className="w-5 h-5 rounded-sm bg-[#131313] border border-[#2d2d2d] text-gray-500 shrink-0 flex items-center justify-center text-[8px] font-bold font-mono select-none">
        TL
      </div>
      <div className="flex-1 max-w-[calc(100%-1.5rem)] border border-[#2d2d2d] bg-[#141414] p-2 space-y-1.5 text-[10px] font-mono select-text">
        <div className="flex items-center justify-between border-b border-[#2d2d2d] pb-1">
          <span className="font-semibold text-gray-300 truncate">Tool: {msg.name || 'unknown'}</span>
          <span className={`px-1.5 py-0.2 rounded-none text-[8px] font-bold ${
            isSuccess
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-red-500/10 text-red-400 border border-red-500/20'
          }`}>
            {isSuccess ? 'SUCCESS' : 'FAILED'}
          </span>
        </div>
        <details className="group">
          <summary className="cursor-pointer text-[9px] text-gray-500 hover:text-gray-300 select-none py-0.5 font-sans">
            View tool logs & output
          </summary>
          <pre className="mt-1 p-2 bg-[#1e1e1e] text-[9px] text-gray-400 max-h-36 overflow-y-auto whitespace-pre-wrap select-text border border-[#2d2d2d] scrollbar-thin">
            {renderContentString(msg.content)}
          </pre>
        </details>
      </div>
    </div>
  );
};
