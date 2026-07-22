import React, { useState, useRef, useEffect } from 'react';
import {
  Send, Square, Sparkles, FileText, Folder, Terminal,
  GitBranch, Code2, Layers, ChevronRight, Plus, AtSign
} from 'lucide-react';
import type { SlashCommand, ContextMention } from '../../types/chat';

const SLASH_COMMANDS: SlashCommand[] = [
  { name: '/plan',      description: 'Generate a step-by-step implementation plan',    example: '/plan Add authentication system' },
  { name: '/build',     description: 'Run build and verify for type errors',           example: '/build' },
  { name: '/fix',       description: 'Diagnose and fix runtime or lint errors',        example: '/fix Fix broken login state' },
  { name: '/refactor',  description: 'Refactor code for performance and cleanliness',  example: '/refactor Clean up state hooks' },
  { name: '/test',      description: 'Generate unit tests for active file',            example: '/test Create tests for auth.ts' },
  { name: '/document',  description: 'Generate JSDoc comments and documentation',      example: '/document Add docs to api handler' },
  { name: '/review',    description: 'Perform security & code quality review',         example: '/review Scan workspace for bugs' },
  { name: '/explain',   description: 'Explain active selection or file logic',         example: '/explain How does routing work?' },
  { name: '/deploy',    description: 'Prepare build bundle for deployment',            example: '/deploy Verify production build' },
];

const CONTEXT_MENTIONS: ContextMention[] = [
  { name: '@file',      type: 'file',      description: 'Reference a specific file' },
  { name: '@folder',    type: 'folder',    description: 'Reference a folder directory' },
  { name: '@terminal',  type: 'terminal',  description: 'Attach recent terminal output' },
  { name: '@git',       type: 'git',       description: 'Attach git diff & changes' },
  { name: '@selection', type: 'selection', description: 'Attach highlighted editor selection' },
  { name: '@workspace', type: 'workspace', description: 'Attach global workspace context' },
];

const SUGGESTED_PROMPTS = [
  'Build a user authentication flow with JWT',
  'Add error handling to API endpoints',
  'Create unit tests for existing functions',
  'Refactor for better performance',
];

interface AiCommandBarProps {
  inputText: string;
  setInputText: (text: string) => void;
  onSend: () => void;
  isGenerating: boolean;
  onCancel: () => void;
  mode: 'Ask' | 'Plan' | 'Agent';
  setMode: (mode: 'Ask' | 'Plan' | 'Agent') => void;
}

export const AiCommandBar: React.FC<AiCommandBarProps> = ({
  inputText, setInputText, onSend, isGenerating, onCancel, mode, setMode
}) => {
  const [showSlashMenu, setShowSlashMenu]     = useState(false);
  const [showMentionMenu, setShowMentionMenu] = useState(false);
  const [selectedIndex, setSelectedIndex]     = useState(0);
  const [showSuggested, setShowSuggested]     = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const lastWord = inputText.split(/\s+/).pop() || '';
    if (lastWord.startsWith('/')) {
      setShowSlashMenu(true); setShowMentionMenu(false); setSelectedIndex(0);
    } else if (lastWord.startsWith('@')) {
      setShowMentionMenu(true); setShowSlashMenu(false); setSelectedIndex(0);
    } else {
      setShowSlashMenu(false); setShowMentionMenu(false);
    }
  }, [inputText]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const menuOpen = showSlashMenu || showMentionMenu;
    const menuLen  = showSlashMenu ? SLASH_COMMANDS.length : CONTEXT_MENTIONS.length;

    if (menuOpen) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIndex(p => (p + 1) % menuLen); return; }
      if (e.key === 'ArrowUp')   { e.preventDefault(); setSelectedIndex(p => (p - 1 + menuLen) % menuLen); return; }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (showSlashMenu) insertSlashCommand(SLASH_COMMANDS[selectedIndex]);
        else insertMention(CONTEXT_MENTIONS[selectedIndex]);
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
    inputRef.current?.focus();
  };

  const insertMention = (mention: ContextMention) => {
    const words = inputText.split(/\s+/);
    words.pop();
    setInputText([...words, mention.name].join(' ') + ' ');
    setShowMentionMenu(false);
    inputRef.current?.focus();
  };

  const modes: Array<{ id: 'Ask' | 'Plan' | 'Agent'; label: string }> = [
    { id: 'Ask',   label: 'Ask' },
    { id: 'Plan',  label: 'Plan' },
    { id: 'Agent', label: 'Agent' },
  ];

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
          className="absolute bottom-full left-0 mb-2 w-72 rounded-xl overflow-hidden z-50 animate-slide-down"
          style={{ background: 'var(--dp-bg-elevated)', border: '1px solid var(--dp-border-mid)', boxShadow: 'var(--dp-shadow-float)' }}
        >
          <div className="px-3 py-2 text-[10px] font-semibold text-[var(--dp-info)] border-b border-[var(--dp-border)] uppercase tracking-wider flex items-center justify-between">
            <span>Context Mentions</span>
            <span className="text-[var(--dp-text-muted)] normal-case font-normal">↑↓ navigate</span>
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            {CONTEXT_MENTIONS.map((mention, idx) => (
              <div
                key={mention.name}
                onClick={() => insertMention(mention)}
                className={`px-3 py-2 text-xs cursor-pointer flex items-center gap-2.5 transition-colors ${
                  idx === selectedIndex
                    ? 'bg-[rgba(96,165,250,0.1)] text-[var(--dp-text-bright)]'
                    : 'text-[var(--dp-text-secondary)] hover:bg-white/4'
                }`}
              >
                {mention.type === 'file'      && <FileText className="w-3.5 h-3.5 text-[var(--dp-info)] shrink-0" />}
                {mention.type === 'folder'    && <Folder   className="w-3.5 h-3.5 text-[var(--dp-warning)] shrink-0" />}
                {mention.type === 'terminal'  && <Terminal  className="w-3.5 h-3.5 text-[var(--dp-success)] shrink-0" />}
                {mention.type === 'git'       && <GitBranch className="w-3.5 h-3.5 text-orange-400 shrink-0" />}
                {mention.type === 'selection' && <Code2     className="w-3.5 h-3.5 text-purple-400 shrink-0" />}
                {mention.type === 'workspace' && <Layers    className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                <div>
                  <span className="font-mono text-[var(--dp-info)] font-semibold">{mention.name}</span>
                  <p className="text-[10px] text-[var(--dp-text-muted)]">{mention.description}</p>
                </div>
              </div>
            ))}
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
          onFocus={() => !inputText && setShowSuggested(true)}
          onBlur={() => setTimeout(() => setShowSuggested(false), 200)}
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
              <Plus className="w-3.5 h-3.5" />
            </button>

            {/* Mode selector */}
            <div className="ml-1 flex items-center bg-white/4 rounded-lg p-0.5 gap-0.5">
              {modes.map(m => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  className={`px-2 py-0.5 rounded-md text-[10px] font-semibold transition-all cursor-pointer ${
                    mode === m.id
                      ? 'bg-[var(--dp-accent)] text-white shadow-sm'
                      : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-secondary)]'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
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

      {/* Suggested prompts — only when empty + focused */}
      {showSuggested && !inputText && (
        <div className="absolute bottom-full left-0 right-0 mb-2 rounded-xl overflow-hidden z-40 animate-slide-down"
          style={{ background: 'var(--dp-bg-elevated)', border: '1px solid var(--dp-border)', boxShadow: 'var(--dp-shadow-md)' }}
        >
          <div className="px-3 py-2 text-[10px] font-semibold text-[var(--dp-text-muted)] uppercase tracking-wider border-b border-[var(--dp-border)] flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-[var(--dp-accent)]" />
            Suggested
          </div>
          {SUGGESTED_PROMPTS.map((prompt, i) => (
            <div
              key={i}
              onClick={() => { setInputText(prompt); setShowSuggested(false); inputRef.current?.focus(); }}
              className="px-3 py-2 text-[11px] text-[var(--dp-text-secondary)] hover:bg-white/4 cursor-pointer transition-colors flex items-center gap-2"
            >
              <ChevronRight className="w-3 h-3 text-[var(--dp-text-muted)] shrink-0" />
              {prompt}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
