import React, { useState, useRef, useEffect } from 'react';
import {
  Send, Square, FileText, Folder, Terminal,
  GitBranch, Code2, Layers, ChevronRight, AtSign
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

interface AiCommandBarProps {
  inputText: string;
  setInputText: (text: string) => void;
  onSend: () => void;
  isGenerating: boolean;
  onCancel: () => void;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
}

export const AiCommandBar: React.FC<AiCommandBarProps> = ({
  inputText, setInputText, onSend, isGenerating, onCancel, mode, setMode
}) => {
  const [showSlashMenu, setShowSlashMenu]     = useState(false);
  const [showMentionMenu, setShowMentionMenu] = useState(false);
  const [selectedIndex, setSelectedIndex]     = useState(0);
  const [workspaceFiles, setWorkspaceFiles]   = useState<string[]>([]);
  const [mentionFilter, setMentionFilter]     = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Fetch flat workspace files on mount or when menu opens
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
      if (isGenerating) onCancel(); else if (inputText.trim()) onSend();
    }
  };

  const insertSlashCommand = (cmd: SlashCommand) => {
    const words = inputText.split(/\s+/);
    words.pop();
    setInputText([...words, cmd.name].join(' ') + ' ');
    setShowSlashMenu(false);
    if (cmd.name === '/plan') setMode('Plan');
    if (cmd.name === '/goal') setMode('Goal');
    inputRef.current?.focus();
  };

  const insertMention = (mention: ContextMention) => {
    const words = inputText.split(/\s+/);
    words.pop();
    setInputText([...words, mention.name].join(' ') + ' ');
    setShowMentionMenu(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative flex flex-col gap-2">

      {/* ── Slash Command Menu ── */}
      {showSlashMenu && (
        <div
          className="absolute bottom-full left-0 mb-2 w-72 rounded-xl overflow-hidden z-50 animate-slide-down"
          style={{ background: 'var(--dp-bg-elevated)', border: '1px solid var(--dp-border-mid)', boxShadow: 'var(--dp-shadow-float)' }}
        >
          <div className="px-3 py-2 text-[10px] font-semibold text-[var(--dp-accent)] border-b border-[var(--dp-border)] uppercase tracking-wider flex items-center justify-between">
            <span>Slash Commands</span>
            <span className="text-[var(--dp-text-muted)] normal-case font-normal">↑↓ navigate · Enter select</span>
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            {SLASH_COMMANDS.map((cmd, idx) => (
              <div
                key={cmd.name}
                onClick={() => insertSlashCommand(cmd)}
                className={`px-3 py-2 text-xs cursor-pointer flex items-center justify-between transition-colors ${
                  idx === selectedIndex
                    ? 'bg-[var(--dp-accent-dim)] text-[var(--dp-text-bright)]'
                    : 'text-[var(--dp-text-secondary)] hover:bg-white/4'
                }`}
              >
                <div>
                  <span className="font-mono text-[var(--dp-accent)] font-semibold">{cmd.name}</span>
                  <p className="text-[10px] text-[var(--dp-text-muted)] mt-0.5">{cmd.description}</p>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-[var(--dp-text-muted)] shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Mention Menu ── */}
      {showMentionMenu && (
        <div
          className="absolute bottom-full left-0 mb-2 w-80 rounded-xl overflow-hidden z-50 animate-slide-down"
          style={{ background: 'var(--dp-bg-elevated)', border: '1px solid var(--dp-border-mid)', boxShadow: 'var(--dp-shadow-float)' }}
        >
          <div className="px-3 py-2 text-[10px] font-semibold text-[var(--dp-info)] border-b border-[var(--dp-border)] uppercase tracking-wider flex items-center justify-between">
            <span>Context & File Mentions</span>
            <span className="text-[var(--dp-text-muted)] normal-case font-normal">↑↓ navigate · Enter select</span>
          </div>
          <div className="max-h-56 overflow-y-auto py-1">
            {activeMentions.length === 0 ? (
              <div className="px-3 py-3 text-xs text-[var(--dp-text-muted)] italic text-center">
                No matching files or context
              </div>
            ) : (
              activeMentions.map((mention, idx) => (
                <div
                  key={mention.name + idx}
                  onClick={() => insertMention(mention)}
                  className={`px-3 py-2 text-xs cursor-pointer flex items-center gap-2.5 transition-colors ${
                    idx === selectedIndex
                      ? 'bg-[rgba(96,165,250,0.12)] text-[var(--dp-text-bright)] font-medium'
                      : 'text-[var(--dp-text-secondary)] hover:bg-white/4'
                  }`}
                >
                  {mention.type === 'file'      && <FileText className="w-3.5 h-3.5 text-[var(--dp-info)] shrink-0" />}
                  {mention.type === 'folder'    && <Folder   className="w-3.5 h-3.5 text-[var(--dp-warning)] shrink-0" />}
                  {mention.type === 'terminal'  && <Terminal  className="w-3.5 h-3.5 text-[var(--dp-success)] shrink-0" />}
                  {mention.type === 'git'       && <GitBranch className="w-3.5 h-3.5 text-orange-400 shrink-0" />}
                  {mention.type === 'selection' && <Code2     className="w-3.5 h-3.5 text-purple-400 shrink-0" />}
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

      {/* ── Main Input Container ── */}
      <div
        className="relative flex flex-col rounded-xl transition-all duration-150 focus-within:shadow-[0_0_0_2px_rgba(124,106,240,0.35)]"
        style={{
          background: 'var(--dp-bg-elevated)',
          border: '1px solid var(--dp-border-mid)',
        }}
      >
        {/* Textarea */}
        <textarea
          ref={inputRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            mode === 'Agent'
              ? 'Ask DevPilot anything...'
              : mode === 'Plan'
              ? 'Describe feature to plan...'
              : 'Ask a question...'
          }
          rows={3}
          className="w-full bg-transparent text-[12px] text-[var(--dp-text-primary)] placeholder-[var(--dp-text-muted)] focus:outline-none resize-none leading-relaxed px-3 pt-3 pb-1 font-sans"
          style={{ minHeight: '70px', maxHeight: '180px' }}
        />

        {/* Footer */}
        <div className="flex items-center justify-between px-2 pb-2 pt-1">
          {/* Left: context tools */}
          <div className="flex items-center gap-0.5">
            <button
              onClick={() => { setInputText(inputText + '@'); inputRef.current?.focus(); }}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/6 cursor-pointer transition-colors"
              title="Mention context (@)"
            >
              <AtSign className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => { setInputText(inputText + '/'); inputRef.current?.focus(); }}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/6 cursor-pointer transition-colors"
              title="Slash command (/)"
            >
              <span className="text-[12px] font-bold">/</span>
            </button>
            <button
              className="w-7 h-7 flex items-center justify-center rounded-lg text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/6 cursor-pointer transition-colors"
              title="Add file context"
            >
            </button>
          </div>

          {/* Right: Send / Stop */}
          {isGenerating ? (
            <button
              onClick={onCancel}
              className="w-8 h-8 flex items-center justify-center rounded-xl bg-[var(--dp-error)]/15 border border-[var(--dp-error)]/30 text-[var(--dp-error)] hover:bg-[var(--dp-error)]/25 transition-all cursor-pointer"
              title="Stop generation"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          ) : (
            <button
              onClick={onSend}
              disabled={!inputText.trim()}
              className="w-8 h-8 flex items-center justify-center rounded-xl disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-all hover:scale-105 active:scale-95"
              style={{
                background: 'linear-gradient(135deg, #7c6af0 0%, #4f8df5 100%)',
                boxShadow: inputText.trim() ? '0 4px 12px rgba(124,106,240,0.4)' : 'none',
              }}
              title="Send (Enter)"
            >
              <Send className="w-3.5 h-3.5 text-white" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
