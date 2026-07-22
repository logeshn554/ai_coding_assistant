import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, Square, Sparkles, FileText, Folder, Terminal, 
  GitBranch, Code2, Layers, ChevronRight 
} from 'lucide-react';
import type { SlashCommand, ContextMention } from '../../types/chat';

const SLASH_COMMANDS: SlashCommand[] = [
  { name: '/plan', description: 'Generate a step-by-step implementation plan', example: '/plan Add authentication system' },
  { name: '/build', description: 'Run build and verify for type errors', example: '/build' },
  { name: '/fix', description: 'Diagnose and fix runtime or lint errors', example: '/fix Fix broken login state' },
  { name: '/refactor', description: 'Refactor code for performance and cleanliness', example: '/refactor Clean up state hooks' },
  { name: '/test', description: 'Generate unit tests for active file', example: '/test Create tests for user.service.ts' },
  { name: '/document', description: 'Generate JSDoc comments and documentation', example: '/document Add docs to api handler' },
  { name: '/review', description: 'Perform security & code quality review', example: '/review Scan workspace for bugs' },
  { name: '/explain', description: 'Explain active selection or file logic', example: '/explain How does routing work?' },
  { name: '/deploy', description: 'Prepare build bundle for deployment', example: '/deploy Verify production build' },
];

const CONTEXT_MENTIONS: ContextMention[] = [
  { name: '@file', type: 'file', description: 'Reference a specific file from workspace' },
  { name: '@folder', type: 'folder', description: 'Reference a folder directory' },
  { name: '@terminal', type: 'terminal', description: 'Attach recent terminal output & logs' },
  { name: '@git', type: 'git', description: 'Attach git diff and uncommitted changes' },
  { name: '@selection', type: 'selection', description: 'Attach currently highlighted editor selection' },
  { name: '@workspace', type: 'workspace', description: 'Attach global workspace index context' },
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
  inputText,
  setInputText,
  onSend,
  isGenerating,
  onCancel,
  mode,
  setMode
}) => {
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [showMentionMenu, setShowMentionMenu] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Detect trigger characters
    const lastWord = inputText.split(/\s+/).pop() || '';
    if (lastWord.startsWith('/')) {
      setShowSlashMenu(true);
      setShowMentionMenu(false);
      setSelectedIndex(0);
    } else if (lastWord.startsWith('@')) {
      setShowMentionMenu(true);
      setShowSlashMenu(false);
      setSelectedIndex(0);
    } else {
      setShowSlashMenu(false);
      setShowMentionMenu(false);
    }
  }, [inputText]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (showSlashMenu) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % SLASH_COMMANDS.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + SLASH_COMMANDS.length) % SLASH_COMMANDS.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertSlashCommand(SLASH_COMMANDS[selectedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        setShowSlashMenu(false);
        return;
      }
    }

    if (showMentionMenu) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % CONTEXT_MENTIONS.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + CONTEXT_MENTIONS.length) % CONTEXT_MENTIONS.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(CONTEXT_MENTIONS[selectedIndex]);
        return;
      }
      if (e.key === 'Escape') {
        setShowMentionMenu(false);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (isGenerating) {
        onCancel();
      } else {
        onSend();
      }
    }
  };

  const insertSlashCommand = (cmd: SlashCommand) => {
    const words = inputText.split(/\s+/);
    words.pop();
    const newText = [...words, cmd.name].join(' ') + ' ';
    setInputText(newText);
    setShowSlashMenu(false);
    if (cmd.name === '/plan') setMode('Plan');
  };

  const insertMention = (mention: ContextMention) => {
    const words = inputText.split(/\s+/);
    words.pop();
    const newText = [...words, mention.name].join(' ') + ' ';
    setInputText(newText);
    setShowMentionMenu(false);
  };

  return (
    <div className="relative flex flex-col bg-[#14171f] border border-white/10 rounded-xl p-2.5 shadow-xl transition-all duration-120 focus-within:border-violet-500/60 focus-within:ring-1 focus-within:ring-violet-500/40">
      {/* Autocomplete Slash Menu */}
      {showSlashMenu && (
        <div className="absolute bottom-full left-0 mb-2 w-72 bg-[#1a1d27] border border-white/10 rounded-lg shadow-2xl overflow-hidden z-50">
          <div className="px-2.5 py-1.5 text-[10px] font-semibold text-violet-400 border-b border-white/5 uppercase tracking-wider flex items-center justify-between">
            <span>Slash Commands</span>
            <span className="text-gray-500">↑↓ to navigate</span>
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            {SLASH_COMMANDS.map((cmd, idx) => (
              <div
                key={cmd.name}
                onClick={() => insertSlashCommand(cmd)}
                className={`px-3 py-2 text-xs cursor-pointer flex items-center justify-between transition-colors ${
                  idx === selectedIndex ? 'bg-violet-600/20 text-white font-medium' : 'text-gray-300 hover:bg-white/5'
                }`}
              >
                <div>
                  <span className="font-mono text-violet-300 font-bold">{cmd.name}</span>
                  <p className="text-[10px] text-gray-400">{cmd.description}</p>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Autocomplete Mentions Menu */}
      {showMentionMenu && (
        <div className="absolute bottom-full left-0 mb-2 w-72 bg-[#1a1d27] border border-white/10 rounded-lg shadow-2xl overflow-hidden z-50">
          <div className="px-2.5 py-1.5 text-[10px] font-semibold text-blue-400 border-b border-white/5 uppercase tracking-wider flex items-center justify-between">
            <span>Context Mentions</span>
            <span className="text-gray-500">↑↓ to navigate</span>
          </div>
          <div className="max-h-48 overflow-y-auto py-1">
            {CONTEXT_MENTIONS.map((mention, idx) => (
              <div
                key={mention.name}
                onClick={() => insertMention(mention)}
                className={`px-3 py-2 text-xs cursor-pointer flex items-center gap-2.5 transition-colors ${
                  idx === selectedIndex ? 'bg-blue-600/20 text-white font-medium' : 'text-gray-300 hover:bg-white/5'
                }`}
              >
                {mention.type === 'file' && <FileText className="w-4 h-4 text-blue-400" />}
                {mention.type === 'folder' && <Folder className="w-4 h-4 text-amber-400" />}
                {mention.type === 'terminal' && <Terminal className="w-4 h-4 text-green-400" />}
                {mention.type === 'git' && <GitBranch className="w-4 h-4 text-orange-400" />}
                {mention.type === 'selection' && <Code2 className="w-4 h-4 text-purple-400" />}
                {mention.type === 'workspace' && <Layers className="w-4 h-4 text-cyan-400" />}
                <div>
                  <span className="font-mono text-blue-300 font-bold">{mention.name}</span>
                  <p className="text-[10px] text-gray-400">{mention.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mode Selector & Quick Tags */}
      <div className="flex items-center justify-between pb-2 mb-1.5 border-b border-white/5 text-[11px]">
        <div className="flex items-center gap-1.5 bg-[#0e1015] p-0.5 rounded-lg border border-white/5">
          {(['Agent', 'Plan', 'Ask'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                mode === m
                  ? 'bg-violet-600 text-white shadow-sm font-semibold'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`}
            >
              {m === 'Agent' ? '⚡ Autonomous Agent' : m === 'Plan' ? '📋 Architect Plan' : '💬 Ask Advisory'}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-gray-400 text-[10px]">
          <span className="font-mono bg-white/5 px-1.5 py-0.5 rounded border border-white/5">Type @ context</span>
          <span className="font-mono bg-white/5 px-1.5 py-0.5 rounded border border-white/5">Type / command</span>
        </div>
      </div>

      {/* Text Area */}
      <textarea
        ref={inputRef}
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          mode === 'Agent'
            ? 'Describe task or change (e.g. "Build user login flow with JWT")...'
            : mode === 'Plan'
            ? 'Describe architectural feature to plan...'
            : 'Ask a question or request explanation...'
        }
        rows={3}
        className="w-full bg-transparent text-xs text-white placeholder-gray-500 focus:outline-none resize-none leading-relaxed"
      />

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-white/5">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-violet-400" /> DevPilot v2.4 Engine
          </span>
        </div>

        {isGenerating ? (
          <button
            onClick={onCancel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 text-xs font-semibold transition-all"
          >
            <Square className="w-3.5 h-3.5 fill-current" /> Stop Execution
          </button>
        ) : (
          <button
            onClick={onSend}
            disabled={!inputText.trim()}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold shadow-md shadow-violet-600/20 transition-all cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" /> Run Task
          </button>
        )}
      </div>
    </div>
  );
};
