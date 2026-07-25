import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Clock, ChevronRight } from 'lucide-react';
import { useCommand } from '../../core/command/CommandContext';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useAI } from '../../core/ai/AIContext';
import { useGit } from '../../core/git/GitContext';
import { useUI } from '../../core/ui/UIContext';

// ── Fuzzy match ──────────────────────────────────────────────────────────────
interface FuzzyResult {
  score: number;
  /** indices of matched chars in the label */
  indices: number[];
}

function fuzzyMatch(query: string, text: string): FuzzyResult | null {
  if (!query) return { score: 0, indices: [] };
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  let qi = 0;
  const indices: number[] = [];
  let score = 0;
  let lastMatch = -1;

  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      indices.push(ti);
      // Consecutive bonus
      if (ti === lastMatch + 1) score += 3;
      // Word-boundary bonus
      if (ti === 0 || t[ti - 1] === ' ' || t[ti - 1] === ':') score += 2;
      score += 1;
      lastMatch = ti;
      qi++;
    }
  }
  if (qi < q.length) return null; // not all chars matched
  return { score, indices };
}

/** Render label with matched chars highlighted */
function HighlightedLabel({ label, indices }: { label: string; indices: number[] }) {
  const set = new Set(indices);
  return (
    <span>
      {label.split('').map((ch, i) =>
        set.has(i) ? (
          <span key={i} style={{ color: 'var(--dp-accent)', fontWeight: 700 }}>{ch}</span>
        ) : (
          <span key={i}>{ch}</span>
        )
      )}
    </span>
  );
}

// ── Recently-used persistence ────────────────────────────────────────────────
const RECENT_KEY = 'devpilot_recent_commands';
const MAX_RECENT = 5;

function loadRecent(): string[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch { return []; }
}
function saveRecent(label: string) {
  const prev = loadRecent().filter(l => l !== label);
  localStorage.setItem(RECENT_KEY, JSON.stringify([label, ...prev].slice(0, MAX_RECENT)));
}

// ── Category colours ─────────────────────────────────────────────────────────
const CAT_COLORS: Record<string, string> = {
  AI:    'var(--dp-accent)',
  Git:   'var(--dp-git-added)',
  Debug: 'var(--dp-warning)',
  View:  'var(--dp-info)',
  File:  'var(--dp-text-secondary)',
  Tools: 'var(--dp-error)',
};

interface Command {
  label: string;
  category: string;
  shortcut?: string;
  action: () => void;
}

// ── Component ────────────────────────────────────────────────────────────────
export const CommandPalette: React.FC = () => {
  const { isCommandPaletteOpen, setIsCommandPaletteOpen, commandSearch, setCommandSearch } = useCommand();
  const { handleOpenWorkspaceFolder } = useWorkspace();
  const { setIsSettingsOpen } = useSettings();
  const { setMessages, handleSendMessage } = useAI();
  const { updateStatusBarInfo } = useGit();
  const { setSidebarTab, setIsSidebarOpen } = useUI();

  const [selectedIdx, setSelectedIdx] = useState(0);
  const [recentLabels, setRecentLabels] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isCommandPaletteOpen) {
      setRecentLabels(loadRecent());
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [isCommandPaletteOpen]);

  if (!isCommandPaletteOpen) return null;

  const close = () => { setIsCommandPaletteOpen(false); setCommandSearch(''); };

  const allCommands: Command[] = [
    // File
    { category: 'File', label: 'Go to File… (Quick Open)', shortcut: 'Ctrl+P',
      action: () => { close(); window.dispatchEvent(new KeyboardEvent('keydown', { key: 'p', ctrlKey: true, bubbles: true })); } },
    { category: 'File', label: 'Go to Symbol in File…', shortcut: 'Ctrl+Shift+O',
      action: () => { close(); window.dispatchEvent(new KeyboardEvent('keydown', { key: 'o', ctrlKey: true, shiftKey: true, bubbles: true })); } },
    { category: 'File', label: 'File: Open Workspace Folder',
      action: () => { close(); handleOpenWorkspaceFolder(); } },
    // AI
    { category: 'AI', label: 'AI: Configure Model Profile Settings', shortcut: 'Ctrl+,',
      action: () => { close(); setIsSettingsOpen(true); } },
    { category: 'AI', label: 'AI: Clear Assistant Chat Logs',
      action: () => { close(); setMessages([]); } },
    { category: 'AI', label: 'AI: Scan Workspace for Bugs',
      action: () => { close(); handleSendMessage('Scan the full workspace for bugs and provide a concise bug report.', 'Ask', false); } },
    { category: 'AI', label: 'AI: Generate Tests for Active File',
      action: () => { close(); handleSendMessage('Generate comprehensive unit tests for the active file.', 'Agent', true); } },
    { category: 'AI', label: 'AI: Explain Active File',
      action: () => { close(); handleSendMessage('Explain the purpose and architecture of the active file in detail.', 'Ask', false); } },
    { category: 'AI', label: 'AI: Review Code Quality',
      action: () => { close(); handleSendMessage('Review the active file for code quality, best practices, and potential improvements.', 'Ask', false); } },
    // Debug
    { category: 'Debug', label: 'Debug: Start Project Execution', shortcut: 'F5',
      action: async () => { close(); await fetch('/api/debug/start', { method: 'POST' }); await updateStatusBarInfo(); } },
    { category: 'Debug', label: 'Debug: Stop Project Execution', shortcut: 'Shift+F5',
      action: async () => { close(); await fetch('/api/debug/stop', { method: 'POST' }); await updateStatusBarInfo(); } },
    // Git
    { category: 'Git', label: 'Git: Pull Latest Updates',
      action: async () => { close(); await fetch('/api/git/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'pull' }) }); } },
    { category: 'Git', label: 'Git: Push Local Commits',
      action: async () => { close(); await fetch('/api/git/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'push' }) }); } },
    { category: 'Git', label: 'Git: Stage All Changes',
      action: async () => { close(); await fetch('/api/git/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'accept_all' }) }); } },
    // View
    { category: 'View', label: 'View: Open File Explorer Sidebar', shortcut: 'Ctrl+Shift+E',
      action: () => { close(); setSidebarTab('explorer'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Code Search Sidebar', shortcut: 'Ctrl+Shift+F',
      action: () => { close(); setSidebarTab('search'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Git Control Sidebar', shortcut: 'Ctrl+Shift+G',
      action: () => { close(); setSidebarTab('git'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Run/Debug Sidebar',
      action: () => { close(); setSidebarTab('debug'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Extensions Sidebar',
      action: () => { close(); setSidebarTab('extensions'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Developer Profile Sidebar',
      action: () => { close(); setSidebarTab('profile'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Testing Explorer',
      action: () => { close(); setSidebarTab('testing'); setIsSidebarOpen(true); } },
    { category: 'View', label: 'View: Open Dependencies Manager',
      action: () => { close(); setSidebarTab('packages'); setIsSidebarOpen(true); } },
  ];

  // Build filtered + scored list
  const query = commandSearch.trim();
  type ScoredCmd = Command & { score: number; indices: number[] };

  let displayList: ScoredCmd[];
  if (!query) {
    // Show recent commands at top, then all
    const recentCmds = recentLabels
      .map(lbl => allCommands.find(c => c.label === lbl))
      .filter(Boolean) as Command[];
    const rest = allCommands.filter(c => !recentLabels.includes(c.label));
    displayList = [...recentCmds, ...rest].map(c => ({ ...c, score: 0, indices: [] }));
  } else {
    displayList = allCommands
      .map(cmd => {
        const m = fuzzyMatch(query, cmd.label);
        return m ? { ...cmd, score: m.score, indices: m.indices } : null;
      })
      .filter(Boolean)
      .sort((a, b) => b!.score - a!.score) as ScoredCmd[];
  }

  const recentSet = new Set(recentLabels);
  const showDivider = !query && recentLabels.length > 0;

  const executeCommand = useCallback((cmd: Command) => {
    saveRecent(cmd.label);
    cmd.action();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx(i => Math.min(i + 1, displayList.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (displayList[selectedIdx]) executeCommand(displayList[selectedIdx]);
    } else if (e.key === 'Escape') {
      close();
    }
  };

  // Auto-scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [selectedIdx]);

  // Reset selection when query changes
  useEffect(() => { setSelectedIdx(0); }, [commandSearch]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[80px]"
      onClick={close}
    >
      <div
        className="w-[560px] overflow-hidden"
        style={{
          background: 'var(--dp-bg-elevated)',
          border: '1px solid var(--dp-border-mid)',
          borderRadius: 'var(--dp-radius-lg)',
          boxShadow: 'var(--dp-shadow-float)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div
          className="p-2 flex items-center gap-2"
          style={{ borderBottom: '1px solid var(--dp-border)', background: 'var(--dp-bg-secondary)' }}
        >
          <Search className="w-4 h-4 shrink-0" style={{ color: 'var(--dp-accent)' }} />
          <input
            ref={inputRef}
            autoFocus
            type="text"
            value={commandSearch}
            onChange={e => setCommandSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search commands… (e.g. 'gen test', 'dbg start')"
            className="w-full bg-transparent text-xs focus:outline-none font-mono"
            style={{ color: 'var(--dp-text-bright)' }}
          />
          <span
            className="text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0"
            style={{ background: 'var(--dp-bg-active)', color: 'var(--dp-text-muted)' }}
          >
            ESC
          </span>
        </div>

        {/* List */}
        <div ref={listRef} className="max-h-80 overflow-y-auto py-1">
          {displayList.length === 0 && (
            <div className="px-4 py-4 text-xs italic" style={{ color: 'var(--dp-text-muted)' }}>
              No commands match "{query}"
            </div>
          )}

          {displayList.map((cmd, idx) => {
            const isSelected = idx === selectedIdx;
            const isRecent = !query && recentSet.has(cmd.label);
            const showSectionDivider = showDivider && idx === recentLabels.length && recentLabels.length > 0;

            return (
              <React.Fragment key={cmd.label}>
                {showSectionDivider && (
                  <div
                    className="px-4 py-1 text-[9px] font-bold uppercase tracking-widest flex items-center gap-2"
                    style={{ color: 'var(--dp-text-muted)', borderTop: '1px solid var(--dp-border)' }}
                  >
                    All Commands
                  </div>
                )}
                <button
                  onClick={() => executeCommand(cmd)}
                  onMouseEnter={() => setSelectedIdx(idx)}
                  className="w-full text-left px-3 py-1.5 flex items-center gap-2 cursor-pointer transition-colors"
                  style={{
                    background: isSelected ? 'var(--dp-bg-selected)' : 'transparent',
                    color: isSelected ? 'var(--dp-text-bright)' : 'var(--dp-text-primary)',
                  }}
                >
                  {/* Category pill */}
                  <span
                    className="text-[8px] font-bold px-1.5 py-0.5 rounded shrink-0"
                    style={{
                      color: CAT_COLORS[cmd.category] || 'var(--dp-text-muted)',
                      background: `color-mix(in srgb, ${CAT_COLORS[cmd.category] || 'var(--dp-text-muted)'} 12%, transparent)`,
                      border: `1px solid color-mix(in srgb, ${CAT_COLORS[cmd.category] || 'var(--dp-text-muted)'} 25%, transparent)`,
                    }}
                  >
                    {cmd.category}
                  </span>

                  {/* Label with highlights */}
                  <span className="flex-1 text-xs font-sans truncate">
                    {query && cmd.indices.length > 0
                      ? <HighlightedLabel label={cmd.label} indices={cmd.indices} />
                      : cmd.label}
                  </span>

                  {/* Recent icon */}
                  {isRecent && (
                    <Clock className="w-3 h-3 shrink-0" style={{ color: 'var(--dp-text-muted)' }} />
                  )}

                  {/* Shortcut */}
                  {cmd.shortcut && (
                    <span
                      className="text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0"
                      style={{ background: 'var(--dp-bg-active)', color: 'var(--dp-text-muted)' }}
                    >
                      {cmd.shortcut}
                    </span>
                  )}

                  {isSelected && <ChevronRight className="w-3 h-3 shrink-0" style={{ color: 'var(--dp-accent)' }} />}
                </button>
              </React.Fragment>
            );
          })}
        </div>

        {/* Footer */}
        <div
          className="px-3 py-1.5 flex items-center gap-3 text-[9px]"
          style={{ borderTop: '1px solid var(--dp-border)', color: 'var(--dp-text-muted)', background: 'var(--dp-bg-secondary)' }}
        >
          <span>↑↓ navigate</span>
          <span>↵ execute</span>
          <span>Esc close</span>
          <span className="ml-auto">{displayList.length} command{displayList.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>
  );
};
