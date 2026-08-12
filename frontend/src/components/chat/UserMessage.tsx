import React from 'react';
import { Paperclip, Image as ImageIcon, ExternalLink } from 'lucide-react';
import type { ChatMessage } from '../../types/chat';

interface UserMessageProps {
  msg: ChatMessage;
}

export const UserMessage: React.FC<UserMessageProps> = React.memo(({ msg }) => {
  const text = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content);
  const attachments = msg.attachedFiles || [];

  const isImageFile = (path: string) => {
    return /\.(png|jpg|jpeg|webp|gif|svg|bmp)$/i.test(path);
  };

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
        className="px-4 py-3 rounded-xl border max-w-full text-[13px] leading-relaxed whitespace-pre-wrap break-words flex flex-col gap-3"
        style={{
          background: '#1e1f24',
          color: '#e3e5e8',
          borderColor: 'rgba(255, 255, 255, 0.04)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.12)',
        }}
      >
        {text && <div>{text}</div>}

        {/* Uploaded Attachments & Images */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2.5 pt-2 border-t border-white/5">
            {attachments.map((attPath, idx) => {
              const filename = attPath.split(/[/\\]/).pop() || attPath;
              const isImg = isImageFile(attPath);
              const rawUrl = `/api/files/raw?path=${encodeURIComponent(attPath)}`;

              if (isImg) {
                return (
                  <div key={idx} className="group relative flex flex-col bg-black/40 border border-white/10 rounded-lg p-1.5 max-w-[260px] overflow-hidden">
                    <a href={rawUrl} target="_blank" rel="noreferrer" className="block relative overflow-hidden rounded">
                      <img
                        src={rawUrl}
                        alt={filename}
                        className="w-full max-h-[180px] object-contain rounded bg-zinc-950/60 group-hover:scale-[1.02] transition-transform duration-200"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                        }}
                      />
                    </a>
                    <div className="flex items-center justify-between px-1.5 py-1 text-[10.5px] text-zinc-400 font-mono">
                      <span className="truncate max-w-[170px] flex items-center gap-1" title={attPath}>
                        <ImageIcon className="w-3 h-3 text-purple-400 shrink-0" />
                        {filename}
                      </span>
                      <a
                        href={rawUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-purple-400 hover:text-purple-300 flex items-center gap-0.5"
                        title="Open image in new tab"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                );
              }

              return (
                <a
                  key={idx}
                  href={rawUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-xs text-zinc-300 transition-colors font-mono"
                  title={`Open ${attPath}`}
                >
                  <Paperclip className="w-3.5 h-3.5 text-purple-400 shrink-0" />
                  <span className="truncate max-w-[180px]">{filename}</span>
                  <ExternalLink className="w-3 h-3 text-zinc-500 hover:text-white" />
                </a>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
});

