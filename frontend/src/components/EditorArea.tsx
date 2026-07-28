/**
 * EditorArea.tsx — Premium Monaco editor with:
 *  - Full options parity (bracket-pair colorization, folding, ligatures, inlineSuggest, etc.)
 *  - Persistent editor state (open tabs, cursor position, scroll) via localStorage
 *  - LSP integration via LSPContext (lazy-connects on language change)
 *  - File backup & rollback revert UI
 *  - AI Proposed Code Changes DiffEditor review bar
 *  - Inline AI Edit Popover (Cmd/Ctrl+K in editor)
 *  - DebugControlBar integration
 *  - World-class Welcome Dashboard with project & service analytics when no file is open
 */
import { useState, useEffect, useRef } from 'react';
import Editor, { DiffEditor } from '@monaco-editor/react';
import {
  X, Save, RotateCcw, Play, Folder, Search,
  Sparkles, Zap, FileCode, Check
} from 'lucide-react';
import { useLSP } from '../core/lsp/LSPContext';
import { InlineChatPopover } from './editor/InlineChatPopover';
import { BreadcrumbBar } from './editor/BreadcrumbBar';
import { useAI } from '../core/ai/AIContext';
import { useTerminal } from '../core/terminal/TerminalContext';
import { getExecutableCommandForFile } from '../utils/executableCommand';
import { DebugControlBar } from './debug/DebugControlBar';


interface Tab {
  path: string;
  name: string;
  isDirty: boolean;
  content: string;
  savedContent: string;
  cursorLine?: number;
  cursorCol?: number;
  scrollTopRatio?: number;
}

interface EditorAreaProps {
  activeFilePath: string | null;
  openFiles: string[];
  onFileClose: (path: string) => void;
  onFileSelect: (path: string) => void;
  proposedDiff: {
    path: string;
    original: string;
    proposed: string;
  } | null;
  onRefreshWorkspace: () => void;
  refreshTrigger: number;
  onOpenFolder?: () => void;
  workspacePath?: string;
  onEditorRef?: (editor: any | null) => void;
}

const EXT_TO_LANG: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  json: 'json',
  jsonc: 'json',
  py: 'python',
  css: 'css',
  scss: 'scss',
  html: 'html',
  xml: 'xml',
  md: 'markdown',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'ini',
  sh: 'shell',
  bat: 'bat',
  ps1: 'powershell',
  rs: 'rust',
  go: 'go',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  sql: 'sql',
  dockerfile: 'dockerfile',
};

function getLanguage(path: string): string {
  const parts = path.split('.');
  const ext = parts.pop()?.toLowerCase() ?? '';
  const filename = path.split('/').pop()?.toLowerCase() ?? '';
  if (filename === 'dockerfile') return 'dockerfile';
  return EXT_TO_LANG[ext] ?? 'plaintext';
}

const LS_CURSOR_PREFIX = 'devpilot_cursor_';
const LS_SCROLL_PREFIX = 'devpilot_scroll_';

function getPrefixedKey(prefix: string, workspacePath: string | null | undefined, path: string): string {
  const wsName = workspacePath ? workspacePath.replace(/\\/g, '/').split('/').pop() || 'default' : 'default';
  return `${prefix}${wsName}_${path}`;
}

function persistCursor(workspacePath: string | null | undefined, path: string, line: number, col: number) {
  try { localStorage.setItem(getPrefixedKey(LS_CURSOR_PREFIX, workspacePath, path), JSON.stringify({ line, col })); } catch {}
}

function loadCursor(workspacePath: string | null | undefined, path: string): { line: number; col: number } | null {
  try {
    const raw = localStorage.getItem(getPrefixedKey(LS_CURSOR_PREFIX, workspacePath, path));
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function persistScroll(workspacePath: string | null | undefined, path: string, ratio: number) {
  try { localStorage.setItem(getPrefixedKey(LS_SCROLL_PREFIX, workspacePath, path), String(ratio)); } catch {}
}

function loadScroll(workspacePath: string | null | undefined, path: string): number {
  try { return parseFloat(localStorage.getItem(getPrefixedKey(LS_SCROLL_PREFIX, workspacePath, path)) ?? '0') || 0; } catch { return 0; }
}

const EDITOR_OPTIONS = {
  fontSize: 13,
  fontFamily: "'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
  fontLigatures: true,
  tabSize: 2,
  minimap: { enabled: true, side: 'right' as const },
  scrollBeyondLastLine: false,
  bracketPairColorization: { enabled: true },
  inlineSuggest: { enabled: true },
  autoClosingBrackets: 'always' as const,
  autoClosingQuotes: 'always' as const,
  formatOnPaste: true,
  formatOnType: true,
  smoothScrolling: true,
  cursorBlinking: 'smooth' as const,
  cursorSmoothCaretAnimation: 'on' as const,
  lineNumbers: 'on' as const,
  renderWhitespace: 'selection' as const,
  padding: { top: 10, bottom: 10 },
};

export default function EditorArea({
  activeFilePath,
  openFiles,
  onFileClose,
  onFileSelect,
  proposedDiff,
  onRefreshWorkspace,
  refreshTrigger: _refreshTrigger,
  onOpenFolder,
  workspacePath,
  onEditorRef,
}: EditorAreaProps) {
  const { handleSendMessage } = useAI();
  const { setBottomTab, setActiveTerminalCommand } = useTerminal();
  const { isReady: lspReady, error: lspError, connect: connectLSP } = useLSP();

  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTabPath, setActiveTabPath] = useState<string | null>(activeFilePath);
  const [showDiff, setShowDiff] = useState(false);
  const [backups, setBackups] = useState<Array<{ timestamp: number; content: string }>>([]);
  const [showBackupsDropdown, setShowBackupsDropdown] = useState(false);


  const [activeTheme, setActiveTheme] = useState<string>(() => localStorage.getItem('devpilot_theme') || 'dark');

  useEffect(() => {
    const handleThemeChange = () => {
      const saved = localStorage.getItem('devpilot_theme') || 'dark';
      setActiveTheme(saved);
    };
    window.addEventListener('devpilot-theme-change', handleThemeChange);
    window.addEventListener('storage', handleThemeChange);
    return () => {
      window.removeEventListener('devpilot-theme-change', handleThemeChange);
      window.removeEventListener('storage', handleThemeChange);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (inlineCompletionsProviderRef.current) {
        inlineCompletionsProviderRef.current.dispose();
      }
    };
  }, []);

  const monacoTheme = activeTheme === 'light' ? 'vs' : activeTheme === 'high-contrast' ? 'hc-black' : 'vs-dark';


  // Inline AI Chat Popover state
  const [inlineChatState, setInlineChatState] = useState<{
    isOpen: boolean;
    lineNumber: number;
    selectedText: string;
    position: { top: number; left: number };
    selectionRange: { startLine: number; startCol: number; endLine: number; endCol: number } | null;
  }>({
    isOpen: false,
    lineNumber: 1,
    selectedText: '',
    position: { top: 100, left: 100 },
    selectionRange: null,
  });

  const editorRef = useRef<any>(null);
  const inlineCompletionsProviderRef = useRef<any>(null);



  useEffect(() => {
    setTabs(prev => {
      const existingMap = new Map(prev.map(t => [t.path, t]));
      return openFiles.map(path => {
        if (existingMap.has(path)) return existingMap.get(path)!;
        const name = path.replace(/\\/g, '/').split('/').pop() || path;
        return { path, name, isDirty: false, content: '', savedContent: '' };
      });
    });
  }, [openFiles]);

  useEffect(() => {
    setActiveTabPath(activeFilePath);
  }, [activeFilePath]);

  useEffect(() => {
    if (proposedDiff && activeTabPath && proposedDiff.path === activeTabPath) {
      setShowDiff(true);
    } else {
      setShowDiff(false);
    }
  }, [proposedDiff, activeTabPath]);

  useEffect(() => {
    if (!activeTabPath) return;
    const tab = tabs.find(t => t.path === activeTabPath);
    if (tab && !tab.content && !tab.isDirty) {
      fetch(`/api/files/content?path=${encodeURIComponent(activeTabPath)}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && typeof data.content === 'string') {
            setTabs(prev => prev.map(t => t.path === activeTabPath ? { ...t, content: data.content, savedContent: data.content } : t));
          }
        })
        .catch(() => {});
    }

    const lang = getLanguage(activeTabPath);
    if (editorRef.current) {
      connectLSP(lang, editorRef.current);
    }
  }, [activeTabPath, tabs, connectLSP]);

  const activeTab = tabs.find(t => t.path === activeTabPath);

  const handleEditorChange = (val: string | undefined) => {
    if (val === undefined || !activeTabPath) return;
    setTabs(prev => prev.map(t => t.path === activeTabPath ? { ...t, content: val, isDirty: val !== t.savedContent } : t));
  };

  const handleSaveActiveFile = async () => {
    if (!activeTab) return;
    try {
      const res = await fetch('/api/files/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTab.path, content: activeTab.content }),
      });
      if (res.ok) {
        setTabs(prev => prev.map(t => t.path === activeTab.path ? { ...t, isDirty: false, savedContent: t.content } : t));
        onRefreshWorkspace();
      }
    } catch {}
  };

  const handleRunActiveFile = async () => {
    if (!activeTab) return;
    const cmd = await getExecutableCommandForFile(activeTab.path);
    setBottomTab('terminal');
    setActiveTerminalCommand(cmd);
  };

  const fetchBackups = async () => {
    if (!activeTabPath) return;
    try {
      const res = await fetch(`/api/files/backups?path=${encodeURIComponent(activeTabPath)}`);
      if (res.ok) {
        const data = await res.json();
        setBackups(data.backups || []);
      }
    } catch {}
  };

  const handleRollback = async (ts: number) => {
    if (!activeTabPath) return;
    try {
      const res = await fetch('/api/files/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTabPath, timestamp: ts }),
      });
      if (res.ok) {
        const data = await res.json();
        setTabs(prev => prev.map(t => t.path === activeTabPath ? { ...t, content: data.content, savedContent: data.content, isDirty: false } : t));
        setShowBackupsDropdown(false);
      }
    } catch {}
  };

  const handleAcceptDiff = async () => {
    if (!proposedDiff) return;
    try {
      const res = await fetch('/api/files/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: proposedDiff.path, content: proposedDiff.proposed }),
      });
      if (res.ok) {
        setTabs(prev => prev.map(t => t.path === proposedDiff.path ? { ...t, content: proposedDiff.proposed, savedContent: proposedDiff.proposed, isDirty: false } : t));
        setShowDiff(false);
        onRefreshWorkspace();
      }
    } catch {}
  };

  const handleRejectDiff = () => setShowDiff(false);

  const handleExplainDiff = () => {
    if (!proposedDiff) return;
    handleSendMessage(`Explain the proposed changes in ${proposedDiff.path}:\n\`\`\`diff\n${proposedDiff.proposed}\n\`\`\``, 'Ask', false);
  };

  const handleRegenerateDiff = () => {
    if (!proposedDiff) return;
    handleSendMessage(`Regenerate and improve the changes for ${proposedDiff.path}.`, 'Agent', false);
  };

  const handleEditorMount = (editor: any, monaco: any) => {
    editorRef.current = editor;
    if (onEditorRef) onEditorRef(editor);

    // Register Inline Completions Provider for Ghost Text AI Autocomplete
    if (monaco) {
      if (inlineCompletionsProviderRef.current) {
        inlineCompletionsProviderRef.current.dispose();
      }
      inlineCompletionsProviderRef.current = monaco.languages.registerInlineCompletionsProvider(
        { pattern: '**/*' },
        {
          provideInlineCompletions: async (model: any, position: any, _context: any, token: any) => {
            // Debounce to prevent server flooding during rapid typing
            await new Promise((resolve) => setTimeout(resolve, 350));
            if (token.isCancellationRequested) {
              return { items: [] };
            }

            const value = model.getValue();
            const offset = model.getOffsetAt(position);
            const prefix = value.substring(0, offset);
            const suffix = value.substring(offset);
            const language = model.getLanguageId();
            const file_path = model.uri ? model.uri.path : '';

            try {
              const res = await fetch('/api/completions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  prefix,
                  suffix,
                  language,
                  file_path: file_path || '',
                  max_tokens: 128
                })
              });
              if (res.ok && !token.isCancellationRequested) {
                const data = await res.json();
                if (data && data.completion) {
                  return {
                    items: [
                      {
                        insertText: data.completion,
                        range: new monaco.Range(
                          position.lineNumber,
                          position.column,
                          position.lineNumber,
                          position.column
                        )
                      }
                    ]
                  };
                }
              }
            } catch (err) {
              console.warn('[Inline Suggest] Fetch failed:', err);
            }

            return { items: [] };
          },
          freeInlineCompletions: () => {}
        }
      );
    }

    if (activeTabPath) {
      const pos = loadCursor(workspacePath, activeTabPath);
      if (pos) editor.setPosition({ lineNumber: pos.line, column: pos.col });
      const scrollRatio = loadScroll(workspacePath, activeTabPath);
      if (scrollRatio > 0) {
        const lineCount = editor.getModel()?.getLineCount() || 1;
        editor.revealLine(Math.floor(lineCount * scrollRatio));
      }
    }

    editor.onDidChangeCursorPosition((e: any) => {
      if (activeTabPath) {
        persistCursor(workspacePath, activeTabPath, e.position.lineNumber, e.position.column);
        window.dispatchEvent(new CustomEvent('editor-cursor-change', {
          detail: { line: e.position.lineNumber, column: e.position.column }
        }));
      }
    });

    editor.onDidScrollChange((e: any) => {
      if (activeTabPath && e.scrollHeight > 0) {
        const ratio = e.scrollTop / e.scrollHeight;
        persistScroll(workspacePath, activeTabPath, ratio);
      }
    });

    // Right-click or keybinding trigger for Inline AI Edit
    editor.addAction({
      id: 'devpilot-inline-chat',
      label: 'DevPilot: Inline AI Edit',
      keybindings: [2048 | 41], // Ctrl+K or Cmd+K
      run: (ed: any) => {
        const sel = ed.getSelection();
        const model = ed.getModel();
        const selectedText = model ? model.getValueInRange(sel) : '';
        const line = sel ? sel.startLineNumber : 1;
        const coords = ed.getScrolledVisiblePosition({ lineNumber: line, column: sel ? sel.startColumn : 1 });
        const domNode = ed.getDomNode();
        const rect = domNode ? domNode.getBoundingClientRect() : { top: 100, left: 100 };

        setInlineChatState({
          isOpen: true,
          lineNumber: line,
          selectedText: selectedText,
          position: {
            top: rect.top + (coords ? coords.top : 40),
            left: rect.left + (coords ? coords.left : 60),
          },
          selectionRange: sel ? {
            startLine: sel.startLineNumber,
            startCol: sel.startColumn,
            endLine: sel.endLineNumber,
            endCol: sel.endColumn,
          } : null,
        });
      },
    });
  };


  const getWorkspaceName = () => workspacePath ? workspacePath.replace(/\\/g, '/').split('/').pop() || 'Workspace' : 'No Workspace';

  return (
    <div className="flex-1 h-full flex flex-col bg-[#0E1016] text-[var(--dp-text-primary)] overflow-hidden font-sans select-none relative">
      
      {/* ── Open Tabs Bar ── */}
      {tabs.length > 0 && (
        <div className="h-9 bg-[#151823] border-b border-[#2A3146] flex items-center px-2 gap-1 overflow-x-auto no-scrollbar shrink-0">
          {tabs.map((tab) => {
            const isActive = tab.path === activeTabPath;
            return (
              <div
                key={tab.path}
                onClick={() => onFileSelect(tab.path)}
                className={`
                  group flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer border shrink-0 font-mono
                  ${isActive
                    ? 'bg-[#1A1F2E] text-white border-[#7C5CFF]/40 shadow-sm font-semibold'
                    : 'bg-transparent text-[var(--dp-text-muted)] border-transparent hover:text-white hover:bg-white/5'
                  }
                `}
              >
                <FileCode className={`w-3.5 h-3.5 ${isActive ? 'text-[#7C5CFF]' : 'text-gray-500'}`} />
                <span className="truncate max-w-[160px]">{tab.name}</span>
                {tab.isDirty && <span className="w-1.5 h-1.5 rounded-full bg-[#7C5CFF]" title="Unsaved changes" />}
                <button
                  onClick={(e) => { e.stopPropagation(); onFileClose(tab.path); }}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-white/10 hover:text-white transition-opacity"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Main Canvas ── */}
      <div className="flex-1 overflow-hidden relative">
        {activeTab ? (
          <div className="h-full flex flex-col">
            {/* Action Bar for Active File */}
            <div className="h-8 bg-[#151823] border-b border-[#2A3146] px-3 flex items-center justify-between text-xs text-[var(--dp-text-secondary)] shrink-0">
              <div className="flex items-center gap-2">
                <BreadcrumbBar filePath={activeTab.path} onSelectPathSegment={() => {}} />
              </div>
              <div className="flex items-center gap-2">
                {lspReady && (
                  <span className="text-[9px] text-[#32D583] font-semibold flex items-center gap-1 bg-[#32D583]/10 px-1.5 py-0.5 rounded border border-[#32D583]/30 font-mono" title="Language Server Protocol Connected">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#32D583] inline-block animate-status-pulse" />
                    LSP
                  </span>
                )}
                {lspError && <span className="text-[9px] text-[#F79009]" title={lspError}>⚠ LSP</span>}

                <span className="text-[10px] font-mono text-[var(--dp-text-muted)] uppercase">{getLanguage(activeTab.path)}</span>

                <button
                  onClick={handleRunActiveFile}
                  className="flex items-center gap-1 px-2.5 py-0.5 rounded bg-[#32D583]/15 text-[#32D583] border border-[#32D583]/30 text-[10px] font-bold hover:bg-[#32D583]/25 transition-colors cursor-pointer"
                >
                  <Play className="w-3 h-3 fill-current" /> Run
                </button>

                {/* Backups / Revert dropdown */}
                <div className="relative">
                  <button
                    onClick={() => { fetchBackups(); setShowBackupsDropdown(!showBackupsDropdown); }}
                    className="flex items-center gap-1 text-[#F79009] hover:text-amber-300 font-medium cursor-pointer text-[11px]"
                    title="Revert File Backups"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Revert
                  </button>
                  {showBackupsDropdown && (
                    <div className="absolute right-0 mt-2 w-56 bg-[#1A1F2E] border border-[#2A3146] rounded-xl shadow-2xl z-50 py-1.5 text-[11px] font-sans">
                      <div className="px-3 py-1 border-b border-[#2A3146] text-[10px] text-[var(--dp-text-muted)] font-semibold uppercase tracking-wider">
                        Available Backups
                      </div>
                      {backups.length === 0 ? (
                        <div className="px-3 py-2 text-[var(--dp-text-muted)] italic">No backups found</div>
                      ) : (
                        <div className="max-h-48 overflow-y-auto divide-y divide-[#2A3146]">
                          {backups.map((bak) => (
                            <button
                              key={bak.timestamp}
                              onClick={() => handleRollback(bak.timestamp)}
                              className="w-full text-left px-3 py-1.5 hover:bg-[#7C5CFF]/15 hover:text-[#7C5CFF] text-gray-300 transition-colors flex justify-between items-center cursor-pointer font-sans"
                            >
                              <span>{new Date(bak.timestamp).toLocaleTimeString()}</span>
                              <span className="text-[9px] text-gray-500 font-mono">#{bak.timestamp.toString().slice(-4)}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {activeTab.isDirty && (
                  <button
                    onClick={handleSaveActiveFile}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#7C5CFF]/15 text-[#7C5CFF] border border-[#7C5CFF]/30 text-[10px] font-bold hover:bg-[#7C5CFF]/25 transition-colors cursor-pointer"
                  >
                    <Save className="w-3 h-3" /> Save
                  </button>
                )}
              </div>
            </div>

            {/* Monaco Editor / Diff Editor Canvas */}
            <div className="flex-1 overflow-hidden flex flex-col relative">
              <DebugControlBar />

              {/* Proposed AI Code Changes Diff Review Bar */}
              {showDiff && proposedDiff && (
                <div className="bg-[#151823] border-b border-[#2A3146] px-4 py-2 flex items-center justify-between z-10 shrink-0 select-none">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#7C5CFF] animate-pulse" />
                    <span className="text-xs font-bold text-white">AI Proposed Code Changes</span>
                    <span className="text-[10px] font-mono text-[var(--dp-text-muted)] bg-white/5 px-2 py-0.5 rounded border border-white/5">
                      {proposedDiff.path}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleAcceptDiff}
                      className="px-3 py-1 bg-[#32D583] hover:bg-[#2bbb72] text-white rounded-lg text-xs font-bold shadow transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5" /> Accept
                    </button>
                    <button
                      onClick={handleRejectDiff}
                      className="px-3 py-1 bg-[#F04438]/20 hover:bg-[#F04438]/30 text-[#F04438] border border-[#F04438]/30 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" /> Reject
                    </button>
                    <button
                      onClick={handleExplainDiff}
                      className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                    >
                      💡 Explain
                    </button>
                    <button
                      onClick={handleRegenerateDiff}
                      className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-[#7C5CFF] rounded-lg text-xs font-medium transition-colors cursor-pointer"
                    >
                      🔄 Regenerate
                    </button>
                  </div>
                </div>
              )}

              <div className="flex-1 overflow-hidden">
                {showDiff && proposedDiff ? (
                  <DiffEditor
                    key={`diff-${proposedDiff.path}-${proposedDiff.proposed.length}`}
                    original={proposedDiff.original}
                    modified={proposedDiff.proposed}
                    language={getLanguage(activeTab.path)}
                    theme={monacoTheme}
                    height="100%"
                    options={{
                      renderSideBySide: true,
                      readOnly: true,
                      minimap: { enabled: false },
                      scrollBeyondLastLine: false,
                      fontFamily: EDITOR_OPTIONS.fontFamily,
                      fontSize: EDITOR_OPTIONS.fontSize,
                      fontLigatures: true,
                    }}
                  />
                ) : (
                  <Editor
                    key={activeTab.path}
                    value={activeTab.content}
                    onChange={handleEditorChange}
                    language={getLanguage(activeTab.path)}
                    theme={monacoTheme}
                    height="100%"
                    options={EDITOR_OPTIONS}
                    onMount={handleEditorMount}
                  />

                )}
              </div>
            </div>
          </div>
        ) : (
          /* ── WORLD-CLASS WELCOME DASHBOARD (no file open) ── */
          <div className="h-full bg-[#0E1016] p-8 overflow-y-auto font-sans select-none">
            <div className="max-w-5xl mx-auto space-y-8 my-auto py-4">

              {/* Hero Banner */}
              <div className="flex items-center justify-between p-6 rounded-2xl bg-gradient-to-r from-[#151823] via-[#1A1F2E] to-[#151823] border border-[#2A3146] shadow-xl">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-[#7C5CFF] to-indigo-600 flex items-center justify-center shadow-md shadow-[#7C5CFF]/30">
                      <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <h1 className="text-xl font-black text-white tracking-tight">DevPilot AI Editor</h1>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#7C5CFF]/20 text-[#7C5CFF] border border-[#7C5CFF]/30">
                      AI-Native IDE
                    </span>
                  </div>
                  <p className="text-xs text-[var(--dp-text-secondary)]">
                    Workspace: <span className="text-white font-mono font-semibold">{getWorkspaceName()}</span> · Multi-Agent Engineering Environment
                  </p>
                </div>

                <button
                  onClick={onOpenFolder}
                  className="flex items-center gap-2 px-4 py-2 bg-[#7C5CFF] hover:bg-[#9176FF] text-white text-xs font-bold rounded-xl shadow-lg shadow-[#7C5CFF]/30 transition-all cursor-pointer"
                >
                  <Folder className="w-4 h-4" /> Open Folder
                </button>
              </div>

              {/* Center aligned Quick Actions Card */}
              <div className="max-w-md mx-auto">
                <div className="dp-card p-6 space-y-4 shadow-2xl border border-[#2A3146] bg-[#121522]/90 backdrop-blur-md rounded-2xl">
                  <div className="flex items-center justify-between text-sm font-bold text-white border-b border-[#2A3146] pb-3">
                    <span className="flex items-center gap-2">
                      <Zap className="w-4.5 h-4.5 text-[#7C5CFF]" /> Quick Actions
                    </span>
                  </div>
                  <div className="space-y-2.5">
                    <button
                      onClick={onOpenFolder}
                      className="w-full flex items-center justify-between p-3 rounded-xl bg-[#151823] hover:bg-[#7C5CFF]/15 border border-[#2A3146] hover:border-[#7C5CFF]/40 text-xs text-white transition-all cursor-pointer shadow-sm group"
                    >
                      <span className="flex items-center gap-2.5 font-medium group-hover:text-[#7C5CFF] transition-colors">
                        <Folder className="w-4 h-4 text-[#7C5CFF]" /> Open Folder
                      </span>
                      <kbd className="text-[10px] font-mono bg-white/10 px-2 py-0.5 rounded border border-white/5 text-slate-300">Ctrl+O</kbd>
                    </button>

                    <button
                      onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }))}
                      className="w-full flex items-center justify-between p-3 rounded-xl bg-[#151823] hover:bg-[#7C5CFF]/15 border border-[#2A3146] hover:border-[#7C5CFF]/40 text-xs text-white transition-all cursor-pointer shadow-sm group"
                    >
                      <span className="flex items-center gap-2.5 font-medium group-hover:text-[#7C5CFF] transition-colors">
                        <Search className="w-4 h-4 text-[#7C5CFF]" /> Universal Search
                      </span>
                      <kbd className="text-[10px] font-mono bg-white/10 px-2 py-0.5 rounded border border-white/5 text-slate-300">Ctrl+K</kbd>
                    </button>

                    <button
                      onClick={() => handleSendMessage('Scan the full workspace for bugs and provide a concise bug report.', 'Ask', false)}
                      className="w-full flex items-center justify-between p-3 rounded-xl bg-[#151823] hover:bg-[#7C5CFF]/15 border border-[#2A3146] hover:border-[#7C5CFF]/40 text-xs text-white transition-all cursor-pointer shadow-sm group"
                    >
                      <span className="flex items-center gap-2.5 font-medium group-hover:text-[#7C5CFF] transition-colors">
                        <Sparkles className="w-4 h-4 text-amber-400" /> AI Bug Scan
                      </span>
                      <span className="text-[10px] text-amber-400 font-bold uppercase tracking-wider bg-amber-400/10 px-2.5 py-0.5 rounded-full border border-amber-400/20">SCAN</span>
                    </button>
                  </div>
                </div>
              </div>

            </div>
          </div>
        )}
      </div>

      {/* Inline AI Edit Popover */}
      <InlineChatPopover
        isOpen={inlineChatState.isOpen}
        onClose={() => setInlineChatState((prev) => ({ ...prev, isOpen: false }))}
        position={inlineChatState.position}
        lineNumber={inlineChatState.lineNumber}
        selectedText={inlineChatState.selectedText}
        filePath={activeTab?.path || ''}
        onApplyInlineEdit={async (prompt, mode) => {
          const fullPrompt = `In file ${activeTab?.path || ''} at line ${inlineChatState.lineNumber}:${
            inlineChatState.selectedText ? ` (selection: "${inlineChatState.selectedText}")` : ''
          }\n${prompt}`;
          handleSendMessage(fullPrompt, mode, true);
        }}
        onAcceptEdit={(suggestion: string) => {
          const range = inlineChatState.selectionRange;
          if (!editorRef.current || !range) return;
          editorRef.current.executeEdits('inline-chat', [{
            range: {
              startLineNumber: range.startLine,
              startColumn: range.startCol,
              endLineNumber: range.endLine,
              endColumn: range.endCol,
            },
            text: suggestion,
            forceMoveMarkers: true,
          }]);
          setInlineChatState((prev) => ({ ...prev, isOpen: false }));
        }}
      />
    </div>
  );
}