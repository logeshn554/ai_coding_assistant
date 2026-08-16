import React, { useState, useRef, useEffect } from 'react';
import {
  Send, Square, FileText, Folder, Terminal,
  GitBranch, Code2, Layers, ChevronRight, AtSign,
  Paperclip, FolderPlus, Image as ImageIcon, X
} from 'lucide-react';
import type { SlashCommand, ContextMention, ChatMode } from '../../types/chat';

const SLASH_COMMANDS: SlashCommand[] = [
  { name: '/plan',      description: 'Generate a step-by-step implementation plan',    example: '/plan Add authentication system' },
  { name: '/goal',      description: 'Autonomous goal mode. Solves complex tasks continuously.', example: '/goal Build complete user auth with JWT' },
  { name: '/grill-me',  description: 'Interactive planning interview to resolve design decisions', example: '/grill-me Clarify database schema' },
  { name: '/learn',     description: 'Extract workspace patterns into Agent Memory & KIs', example: '/learn Save code convention rules' },
  { name: '/schedule',  description: 'Set background timers or recurring monitors',      example: '/schedule Check build every 5 min' },
  { name: '/build',     description: 'Run build and verify for type errors',           example: '/build' },
  { name: '/fix',       description: 'Diagnose and fix runtime or lint errors',        example: '/fix Fix broken login state' },
  { name: '/refactor',  description: 'Refactor code for performance and cleanliness',  example: '/refactor Clean up state hooks' },
  { name: '/test',      description: 'Generate unit tests for active file',            example: '/test Create tests for auth.ts' },
  { name: '/document',  description: 'Generate JSDoc comments and documentation',      example: '/document Add docs to api handler' },
  { name: '/review',    description: 'Perform security & code quality review',         example: '/review Scan workspace for bugs' },
  { name: '/explain',   description: 'Explain active selection or file logic',         example: '/explain How does routing work?' },
];

const CONTEXT_MENTIONS: ContextMention[] = [
  { name: '@file',      type: 'file',      description: 'Reference a specific file' },
  { name: '@folder',    type: 'folder',    description: 'Reference a folder directory' },
  { name: '@terminal',  type: 'terminal',  description: 'Attach recent terminal output' },
  { name: '@git',       type: 'git',       description: 'Attach git diff & changes' },
  { name: '@selection', type: 'selection', description: 'Attach highlighted editor selection' },
  { name: '@workspace', type: 'workspace', description: 'Attach global workspace context' },
];

export interface AttachmentItem {
  name: string;
  path: string;
  type: 'image' | 'file' | 'folder';
  previewUrl?: string;
}

interface AiCommandBarProps {
  inputText: string;
  setInputText: (text: string) => void;
  onSend: (attachedFiles?: string[], autoApply?: boolean) => void;
  isGenerating: boolean;
  onCancel: () => void;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  onOpenContextModal?: () => void;
  contextPercentage?: number;
}

export const AiCommandBar: React.FC<AiCommandBarProps> = ({
  inputText,
  setInputText,
  onSend,
  isGenerating,
  onCancel,
  mode,
  onOpenContextModal,
  contextPercentage = 0,
}) => {
  const [autoApply, setAutoApply] = useState(true);
  const [showSlashMenu, setShowSlashMenu]     = useState(false);
  const [showMentionMenu, setShowMentionMenu] = useState(false);
  const [selectedIndex, setSelectedIndex]     = useState(0);
  const [workspaceFiles, setWorkspaceFiles]   = useState<string[]>([]);
  const [mentionFilter, setMentionFilter]     = useState('');

  // Calculate Context Circle styling for Symbol near Send Button
  const pct = typeof contextPercentage === 'number' ? contextPercentage : 0;
  let circleColor = "border-emerald-400 text-emerald-400";
  if (pct >= 95) circleColor = "border-red-400 text-red-400 animate-pulse";
  else if (pct >= 90) circleColor = "border-amber-400 text-amber-400";
  else if (pct >= 80) circleColor = "border-yellow-400 text-yellow-400";

  // Attachment state for images, files, and folders
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Fetch flat workspace files on mount
  useEffect(() => {
    fetch('/api/files/flat')
      .then(res => res.json())
      .then(data => {
        if (data.files && Array.isArray(data.files)) {
          setWorkspaceFiles(data.files);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const lastWord = inputText.split(/\s+/).pop() || '';
    if (lastWord.startsWith('/')) {
      setShowSlashMenu(true); setShowMentionMenu(false); setSelectedIndex(0);
    } else if (lastWord.startsWith('@')) {
      const query = lastWord.slice(1).toLowerCase();
      setMentionFilter(query);
      setShowMentionMenu(true); setShowSlashMenu(false); setSelectedIndex(0);
    } else {
      setShowSlashMenu(false); setShowMentionMenu(false);
    }
  }, [inputText]);

  // Combine static context mentions + real workspace files
  const fileMentions: ContextMention[] = workspaceFiles
    .filter(f => !mentionFilter || f.toLowerCase().includes(mentionFilter))
    .slice(0, 15)
    .map(f => ({
      name: `@${f}`,
      type: 'file' as const,
      description: f,
    }));

  const filteredStaticMentions = CONTEXT_MENTIONS.filter(
    m => !mentionFilter || m.name.toLowerCase().includes(`@${mentionFilter}`)
  );

  const activeMentions = mentionFilter && fileMentions.length > 0
    ? fileMentions
    : [...filteredStaticMentions, ...fileMentions.slice(0, 10)];

  // Helper to upload a file / image / folder item to /api/files/upload
  const uploadSingleFile = async (file: File): Promise<AttachmentItem | null> => {
    try {
      const formData = new FormData();
      formData.append('file', file, file.name);

      const res = await fetch('/api/files/upload', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        const isImage = file.type.startsWith('image/') || /\.(png|jpe?g|webp|gif|bmp|svg)$/i.test(file.name);
        const isFolder = (file as any).webkitRelativePath && (file as any).webkitRelativePath.includes('/');
        const previewUrl = isImage ? URL.createObjectURL(file) : undefined;

        return {
          name: file.name,
          path: data.path || data.rel_path || file.name,
          type: isImage ? 'image' : isFolder ? 'folder' : 'file',
          previewUrl,
        };
      }
    } catch (err) {
      console.error('Failed to upload file attachment:', err);
    }
    return null;
  };

  const handleProcessFiles = async (files: FileList | File[]) => {
    setIsUploading(true);
    const fileArray = Array.from(files);
    const uploadedItems: AttachmentItem[] = [];

    for (const file of fileArray) {
      const item = await uploadSingleFile(file);
      if (item) uploadedItems.push(item);
    }

    if (uploadedItems.length > 0) {
      setAttachments(prev => [...prev, ...uploadedItems]);
    }
    setIsUploading(false);
  };

  // Clipboard Paste Image / File Handler
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const clipboardItems = e.clipboardData.items;
    const filesToUpload: File[] = [];

    if (clipboardItems) {
      for (let i = 0; i < clipboardItems.length; i++) {
        const item = clipboardItems[i];
        if (item.type.indexOf('image') !== -1 || item.kind === 'file') {
          const blob = item.getAsFile();
          if (blob) {
            filesToUpload.push(blob);
          }
        }
      }
    }

    if (filesToUpload.length > 0) {
      e.preventDefault();
      handleProcessFiles(filesToUpload);
    }
  };

  // Drag and Drop Handler
  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleProcessFiles(e.dataTransfer.files);
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const menuOpen = showSlashMenu || showMentionMenu;
    const menuLen  = showSlashMenu ? SLASH_COMMANDS.length : activeMentions.length;

    if (menuOpen && menuLen > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(p => (p + 1) % menuLen); return; }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setSelectedIndex(p => (p - 1 + menuLen) % menuLen); return; }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (showSlashMenu) insertSlashCommand(SLASH_COMMANDS[selectedIndex]);
        else insertMention(activeMentions[selectedIndex]);
        return;
      }
      if (e.key === 'Escape') { setShowSlashMenu(false); setShowMentionMenu(false); return; }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isGenerating) {
        onCancel();
      } else if (inputText.trim() || attachments.length > 0) {
        handleTriggerSend();
      }
    }
  };

  const handleTriggerSend = () => {
    const attachedPaths = attachments.map(a => a.path);
    onSend(attachedPaths.length > 0 ? attachedPaths : undefined, autoApply);
    setAttachments([]);
  };

  const insertSlashCommand = (cmd: SlashCommand) => {
    const words = inputText.split(/\s+/);
    words.pop();
    const prefix = words.length > 0 ? words.join(' ') + ' ' : '';
    setInputText(prefix + cmd.name + ' ');
    setShowSlashMenu(false);
    inputRef.current?.focus();
  };

  const insertMention = (mention: ContextMention) => {
    const words = inputText.split(/\s+/);
    words.pop();
    const prefix = words.length > 0 ? words.join(' ') + ' ' : '';
    setInputText(prefix + mention.name + ' ');
    setShowMentionMenu(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative w-full" onDragOver={(e) => e.preventDefault()} onDrop={handleDrop}>
      {/* Hidden File Input Elements */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => e.target.files && handleProcessFiles(e.target.files)}
        multiple
        className="hidden"
      />
      <input
        type="file"
        ref={folderInputRef}
        onChange={(e) => e.target.files && handleProcessFiles(e.target.files)}
        {...({ webkitdirectory: '', directory: '' } as any)}
        multiple
        className="hidden"
      />

      {/* Slash Command Autocomplete Menu */}
      {showSlashMenu && (
        <div className="absolute bottom-full left-0 mb-2 w-full z-50 rounded-xl bg-[var(--dp-bg-elevated)] border border-[var(--dp-border-mid)] shadow-2xl overflow-hidden font-sans">
          <div className="px-3 py-1.5 border-b border-white/5 bg-white/5 flex items-center justify-between text-[10px] text-[var(--dp-text-muted)] uppercase tracking-wider font-semibold">
            <span>Slash Commands</span>
            <span>↑↓ Navigate • ↵ Select</span>
          </div>
          <div className="max-h-48 overflow-y-auto p-1 space-y-0.5">
            {SLASH_COMMANDS.map((cmd, idx) => (
              <div
                key={cmd.name}
                onClick={() => insertSlashCommand(cmd)}
                className={`flex items-center justify-between px-3 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                  idx === selectedIndex ? 'bg-[var(--dp-accent)]/20 text-white font-medium' : 'text-[var(--dp-text-secondary)] hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[var(--dp-accent)] font-semibold">{cmd.name}</span>
                  <span className="text-[var(--dp-text-muted)] text-[11px]">{cmd.description}</span>
                </div>
                <ChevronRight className="w-3 h-3 text-[var(--dp-text-muted)] shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Context Mention (@) Menu */}
      {showMentionMenu && (
        <div className="absolute bottom-full left-0 mb-2 w-full z-50 rounded-xl bg-[var(--dp-bg-elevated)] border border-[var(--dp-border-mid)] shadow-2xl overflow-hidden font-sans">
          <div className="px-3 py-1.5 border-b border-white/5 bg-white/5 flex items-center justify-between text-[10px] text-[var(--dp-text-muted)] uppercase tracking-wider font-semibold">
            <span>Context Mentions</span>
            <span>↑↓ Navigate • ↵ Select</span>
          </div>
          <div className="max-h-48 overflow-y-auto p-1 space-y-0.5">
            {activeMentions.length === 0 ? (
              <div className="px-3 py-2 text-xs text-[var(--dp-text-muted)]">No matching files or context</div>
            ) : (
              activeMentions.map((mention, idx) => (
                <div
                  key={mention.name}
                  onClick={() => insertMention(mention)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                    idx === selectedIndex ? 'bg-[var(--dp-accent)]/20 text-white font-medium' : 'text-[var(--dp-text-secondary)] hover:bg-white/5'
                  }`}
                >
                  {mention.type === 'file'      && <FileText  className="w-3.5 h-3.5 text-blue-400 shrink-0" />}
                  {mention.type === 'folder'    && <Folder    className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                  {mention.type === 'terminal'  && <Terminal  className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                  {mention.type === 'git'       && <GitBranch className="w-3.5 h-3.5 text-orange-400 shrink-0" />}
                  {mention.type === 'selection' && <Code2     className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0" />}
                  {mention.type === 'workspace' && <Layers    className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                  <div className="min-w-0 flex-1 truncate">
                    <span className="font-mono text-[var(--dp-info)] font-semibold truncate block">
                      {mention.name}
                    </span>
                    <p className="text-[10px] text-[var(--dp-text-muted)] truncate">
                      {mention.description}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── Main Input Container (Cohesive Bubble) ── */}
      <div
        className="relative flex flex-col rounded-xl border border-zinc-800 bg-[#16171d]/90 shadow-lg focus-within:border-violet-500/40 focus-within:ring-1 focus-within:ring-violet-500/20 transition-all duration-150"
      >
        {/* Attachment Chips Preview Bar */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 px-3 pt-2.5 pb-1 border-b border-zinc-800/60 max-h-24 overflow-y-auto">
            {attachments.map((att, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] bg-zinc-900 text-zinc-300 font-mono border border-zinc-800 shadow-sm"
              >
                {att.previewUrl ? (
                  <img src={att.previewUrl} alt={att.name} className="w-4 h-4 rounded object-cover" />
                ) : att.type === 'image' ? (
                  <ImageIcon className="w-3.5 h-3.5 text-blue-400" />
                ) : att.type === 'folder' ? (
                  <FolderPlus className="w-3.5 h-3.5 text-amber-400" />
                ) : (
                  <FileText className="w-3.5 h-3.5 text-blue-400" />
                )}
                <span className="truncate max-w-[130px]" title={att.name}>{att.name}</span>
                <button
                  type="button"
                  onClick={() => removeAttachment(idx)}
                  className="hover:text-red-400 text-zinc-500 transition-colors ml-0.5 cursor-pointer font-bold"
                  title="Remove attachment"
                >
                  <X className="w-2.5 h-2.5" />
                </button>
              </div>
            ))}
            {isUploading && (
              <span className="text-[10px] text-[#4C8DFF] animate-pulse">Uploading...</span>
            )}
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={inputRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={
            mode === 'Agent'
              ? 'Ask Loopix...'
              : mode === 'Plan'
              ? 'Describe feature to plan...'
              : 'Ask a question...'
          }
          rows={3}
          className="w-full bg-transparent text-[13px] text-zinc-200 placeholder-zinc-550 focus:outline-none resize-none leading-relaxed px-4 pt-3.5 pb-1 font-sans"
          style={{ minHeight: '60px', maxHeight: '180px' }}
        />

        {/* Inner Controls Bar inside the Bubble */}
        <div className="flex items-center justify-between px-3 pb-3 pt-1">
          {/* Left: Attachment & mention buttons */}
          <div className="flex items-center gap-1 select-none">
            <button
              onClick={() => { setInputText(inputText + '@'); inputRef.current?.focus(); }}
              className="w-6.5 h-6.5 flex items-center justify-center rounded bg-transparent hover:bg-zinc-800 text-zinc-400 hover:text-white cursor-pointer transition-colors"
              title="Mention context (@)"
            >
              <AtSign className="w-3.5 h-3.5" />
            </button>
            
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-6.5 h-6.5 flex items-center justify-center rounded bg-transparent hover:bg-zinc-800 text-zinc-400 hover:text-white cursor-pointer transition-colors"
              title="Upload file or image attachment"
            >
              <Paperclip className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Right: Context Symbol + Round Send/Cancel Trigger */}
          <div className="flex items-center gap-2">
            {/* Context Symbol Indicator near Send Button */}
            {onOpenContextModal && (
              <button
                type="button"
                onClick={onOpenContextModal}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900/90 hover:bg-zinc-800 border border-zinc-800/80 text-zinc-400 hover:text-white cursor-pointer transition-all text-[10.5px] font-mono group"
                title="Click to view Context Window details & breakdown"
              >
                <div className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center text-[8px] font-bold ${circleColor}`}>
                  ◯
                </div>
                <span className="font-bold">{pct}%</span>
              </button>
            )}

            {isGenerating ? (
              <button
                type="button"
                onClick={onCancel}
                className="w-7 h-7 flex items-center justify-center rounded-full bg-red-950/40 border border-red-900/40 text-red-400 hover:bg-red-900/60 cursor-pointer transition-all hover:scale-105 active:scale-95"
                title="Stop generation"
              >
                <Square className="w-3 h-3 fill-current" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleTriggerSend}
                disabled={!inputText.trim() && attachments.length === 0}
                className="w-7 h-7 flex items-center justify-center rounded-full disabled:opacity-35 disabled:cursor-not-allowed cursor-pointer transition-all hover:scale-105 active:scale-95"
                style={{
                  background: 'linear-gradient(135deg, #7c6af0 0%, #4f8df5 100%)',
                  boxShadow: (inputText.trim() || attachments.length > 0) ? '0 3px 8px rgba(124,106,240,0.3)' : 'none',
                }}
                title="Send (Enter)"
              >
                <Send className="w-3 h-3 text-white" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Outer Footer Controls (Outside the Bubble) ── */}
      <div className="flex items-center justify-between mt-2.5 px-0.5 select-none text-[11px] font-sans">
        {/* Left: Auto Apply toggle */}
        {(mode === 'Agent' || mode === 'Goal') ? (
          <label className="flex items-center gap-1.5 text-zinc-500 hover:text-zinc-300 cursor-pointer select-none font-medium transition-colors">
            <input
              type="checkbox"
              checked={autoApply}
              onChange={(e) => setAutoApply(e.target.checked)}
              className="rounded border-zinc-800 bg-zinc-950 text-[#3B7AE8] focus:ring-0 focus:ring-offset-0 w-3.5 h-3.5 cursor-pointer"
            />
            <span>Auto Apply</span>
          </label>
        ) : (
          <div />
        )}


      </div>
    </div>
  );
};
