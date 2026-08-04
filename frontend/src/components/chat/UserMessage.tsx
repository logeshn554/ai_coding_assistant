import React from 'react';
import type { ChatMessage } from '../../types/chat';

interface UserMessageProps {
  msg: ChatMessage;
}

export const UserMessage: React.FC<UserMessageProps> = React.memo(({ msg }) => {
  const text = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);

  return (
    <div className="flex flex-col gap-2 mb-5 select-text animate-[fadeIn_150ms_ease-out] font-sans">
      {/* User Header */}
      <div className="flex items-center gap-2.5 select-none">
        {/* Purple 'Y' Avatar */}
        <div
          className="w-6.5 h-6.5 rounded-full flex items-center justify-center shrink-0 border border-violet-500/35 text-[11px] font-black text-white shadow-sm"
          style={{
            background: 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)',
          }}
        >
          Y
        </div>
        <span className="font-bold text-[12.5px] text-zinc-100 tracking-wide">
          You
        </span>
      </div>

      {/* User Message Bubble */}
      <div
        className="px-4 py-3 rounded-xl border max-w-full text-[13px] leading-relaxed whitespace-pre-wrap break-words"
        style={{
          background: '#1e1f24',
          color: '#e3e5e8',
          borderColor: 'rgba(255, 255, 255, 0.04)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.12)',
        }}
      >
        {text}
      </div>
    </div>
  );
});
