/**
 * EditorArea.tsx — Upgraded Monaco editor with:
 *  - Full options parity (bracket-pair colorization, folding, ligatures, inlineSuggest, etc.)
 *  - Persistent editor state (open tabs, cursor position, scroll) via localStorage
 *  - LSP integration via LSPContext (lazy-connects on language change)
 *  - onEditorRef callback so parent can drive revealLine / goToSymbol
 *  - Dirty-tab dot with tooltip
 *  - Backup/rollback UI preserved
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import Editor, { DiffEditor, type OnMount } from '@monaco-editor/react';
import { X, Save, FileCode, RotateCcw } from 'lucide-react';
import { useLSP } from '../core/lsp/LSPContext';

// ── Types ────────────────────────────────────────────────────────────────────

interface Tab {
  path: string;
  name: string;
  isDirty: boolean;
  content: string;
  savedContent: string;
  /** Persisted cursor position */
  cursorLine?: number;
  cursorCol?: number;
  /** Persisted scroll top ratio (0-1) */
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
  /** Callback giving parent a handle to the live Monaco editor instance */
  onEditorRef?: (editor: any | null) => void;
}

// ── Language detection ───────────────────────────────────────────────────────

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
  less: 'less',
  html: 'html',
  htm: 'html',
  xml: 'xml',
  md: 'markdown',
  mdx: 'markdown',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'ini',
  sh: 'shell',
  bash: 'shell',
  bat: 'bat',
  ps1: 'powershell',
  rs: 'rust',
  go: 'go',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  h: 'c',
  hpp: 'cpp',
  cs: 'csharp',
  rb: 'ruby',
  php: 'php',
  swift: 'swift',
  kt: 'kotlin',
  sql: 'sql',
  dockerfile: 'dockerfile',
};

// Languages for which we attempt to connect LSP
const LSP_LANGUAGES = new Set(['python', 'typescript', 'javascript']);

function getLanguage(path: string): string {
  const parts = path.split('.');
  const ext = parts.pop()?.toLowerCase() ?? '';
  const filename = path.split('/').pop()?.toLowerCase() ?? '';
  if (filename === 'dockerfile') return 'dockerfile';
  if (filename === 'makefile') return 'makefile';
  return EXT_TO_LANG[ext] ?? 'plaintext';
}

// ── localStorage persistence helpers ─────────────────────────────────────────

const LS_TABS_KEY = 'devpilot_editor_tabs';
const LS_ACTIVE_KEY = 'devpilot_editor_active';
const LS_CURSOR_PREFIX = 'devpilot_cursor_';
const LS_SCROLL_PREFIX = 'devpilot_scroll_';

function persistTabs(paths: string[], active: string | null) {
  try {
    localStorage.setItem(LS_TABS_KEY, JSON.stringify(paths));
    if (active) localStorage.setItem(LS_ACTIVE_KEY, active);
  } catch {}
}

function persistCursor(path: string, line: number, col: number) {
  try {
    localStorage.setItem(LS_CURSOR_PREFIX + path, JSON.stringify({ line, col }));
  } catch {}
}

function loadCursor(path: string): { line: number; col: number } | null {
  try {
    const raw = localStorage.getItem(LS_CURSOR_PREFIX + path);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function persistScroll(path: string, ratio: number) {
  try {
    localStorage.setItem(LS_SCROLL_PREFIX + path, String(ratio));
  } catch {}
}

function loadScroll(path: string): number {
  try {
    return parseFloat(localStorage.getItem(LS_SCROLL_PREFIX + path) ?? '0') || 0;
  } catch { return 0; }
}

// ── Monaco editor options (VS Code parity) ───────────────────────────────────

const EDITOR_OPTIONS = {
  // Typography
  fontSize: 13,
  fontFamily: "'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'Courier New', monospace",
  fontLigatures: true,
  lineHeight: 1.6,
  letterSpacing: 0.3,

  // Behaviour
  wordWrap: 'on' as const,
  tabSize: 2,
  insertSpaces: true,
  detectIndentation: true,
  trimAutoWhitespace: true,
  formatOnType: false,
  formatOnPaste: false,

  // Display
  lineNumbers: 'on' as const,
  lineNumbersMinChars: 4,
  lineDecorationsWidth: 8,
  renderLineHighlight: 'line' as const,
  renderWhitespace: 'none' as const,
  showFoldingControls: 'mouseover' as const,

  // Folding
  folding: true,
  foldingStrategy: 'auto' as const,
  foldingHighlight: true,

  // Minimap
  minimap: { enabled: true, scale: 1, renderCharacters: false },

  // Bracket pair colorization (VS Code 2021+)
  bracketPairColorization: { enabled: true, independentColorPoolPerBracketType: true },
  guides: {
    bracketPairs: true,
    bracketPairsHorizontal: 'active' as const,
    indentation: true,
    highlightActiveIndentation: true,
  },

  // Scroll
  scrollBeyondLastLine: false,
  smoothScrolling: true,
  scrollbar: {
    vertical: 'auto' as const,
    horizontal: 'auto' as const,
    useShadows: false,
    verticalScrollbarSize: 8,
    horizontalScrollbarSize: 8,
  },

  // Cursor
  cursorBlinking: 'smooth' as const,
  cursorStyle: 'line' as const,
  cursorSmoothCaretAnimation: 'on' as const,
  multiCursorModifier: 'ctrlCmd' as const,

  // Sticky scroll (headers stay in view)
  stickyScroll: { enabled: true, maxLineCount: 5, scrollWithEditor: true },

  // Code lens & inline suggestions
  codeLens: true,
  inlineSuggest: { enabled: true, mode: 'subword' as const },
  quickSuggestions: { other: true, comments: false, strings: false },
  suggestOnTriggerCharacters: true,
  acceptSuggestionOnEnter: 'smart' as const,
  tabCompletion: 'on' as const,

  // Hover / docs
  hover: { enabled: true, delay: 300, sticky: true },
  parameterHints: { enabled: true, cycle: true },

  // Layout
  automaticLayout: true,
  padding: { top: 8, bottom: 8 },

  // Accessibility
  accessibilitySupport: 'auto' as const,
  renderValidationDecorations: 'on' as const,
};

// ── Component ────────────────────────────────────────────────────────────────

export default function EditorArea({
  activeFilePath,
  openFiles,
  onFileClose,
  onFileSelect,
  proposedDiff,
  onRefreshWorkspace,
  refreshTrigger,
  onOpenFolder,
  workspacePath,
  onEditorRef,
}: EditorAreaProps) {
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTab, setActiveTab] = useState<Tab | null>(null);
  const [loading, setLoading] = useState(false);
  const [backups, setBackups] = useState<{ timestamp: number; filename: string }[]>([]);
  const [showBackupsDropdown, setShowBackupsDropdown] = useState(false);

  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);

  // Track whether we need to restore cursor/scroll after editor mounts
  const pendingRestoreRef = useRef<{ line: number; col: number; scroll: number } | null>(null);

  const { connect: connectLSP, isReady: lspReady, error: lspError } = useLSP();

  // ── Editor mount handler ─────────────────────────────────────────────────

  const handleEditorMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Forward ref to parent (for GoToSymbol)
      onEditorRef?.(editor);

      // Restore cursor & scroll position
      if (pendingRestoreRef.current) {
        const { line, col, scroll } = pendingRestoreRef.current;
        pendingRestoreRef.current = null;
        setTimeout(() => {
          try {
            editor.setPosition({ lineNumber: line, column: col });
            editor.revealLineInCenter(line);
            // Restore scroll by ratio
            const model = editor.getModel();
            if (model && scroll > 0) {
              const totalLines = model.getLineCount();
              const targetLine = Math.floor(scroll * totalLines);
              editor.revealLine(targetLine);
            }
          } catch {}
        }, 50);
      }

      // Persist cursor position changes
      editor.onDidChangeCursorPosition((e: any) => {
        const { lineNumber: line, column: col } = e.position;

        // Dispatch for statusbar
        window.dispatchEvent(
          new CustomEvent('editor-cursor-change', { detail: { line, column: col } })
        );

        // Persist to localStorage
        const path = activeFilePath;
        if (path) persistCursor(path, line, col);

        // Update tab cursor info
        setTabs((prev) =>
          prev.map((t) =>
            t.path === path ? { ...t, cursorLine: line, cursorCol: col } : t
          )
        );
      });

      // Persist scroll position
      editor.onDidScrollChange((e: any) => {
        const path = activeFilePath;
        if (!path) return;
        const model = editor.getModel();
        if (!model) return;
        const totalLines = model.getLineCount();
        if (totalLines > 0) {
          const ratio = e.scrollTop / (totalLines * editor.getOption(monaco.editor.EditorOption.lineHeight));
          persistScroll(path, ratio);
        }
      });

      // Diagnostics → status bar
      const updateDiagnostics = () => {
        const model = editor.getModel();
        if (!model) return;
        const markers = monaco.editor.getModelMarkers({ resource: model.uri });
        const errors = markers.filter((m: any) => m.severity === monaco.MarkerSeverity.Error).length;
        const warnings = markers.filter((m: any) => m.severity === monaco.MarkerSeverity.Warning).length;
        window.dispatchEvent(
          new CustomEvent('editor-diagnostics', { detail: { errors, warnings } })
        );
      };
      updateDiagnostics();
      monaco.editor.onDidChangeMarkers((uris: any[]) => {
        const model = editor.getModel();
        if (model && uris.some((u: any) => u.toString() === model.uri.toString())) {
          updateDiagnostics();
        }
      });
    },
    [activeFilePath, onEditorRef]
  );

  // ── Sync openFiles → tabs ────────────────────────────────────────────────

  useEffect(() => {
    const syncTabs = async () => {
      const existingPaths = tabs.map((t) => t.path);
      const newTabs = [...tabs];
      let changed = false;

      for (const filePath of openFiles) {
        if (!existingPaths.includes(filePath)) {
          changed = true;
          try {
            setLoading(true);
            const res = await fetch(`/api/files/content?path=${encodeURIComponent(filePath)}`);
            const data = await res.json();
            const tabName = filePath.split('/').pop() || filePath;
            const cursor = loadCursor(filePath);
            newTabs.push({
              path: filePath,
              name: tabName,
              isDirty: false,
              content: data.content,
              savedContent: data.content,
              cursorLine: cursor?.line,
              cursorCol: cursor?.col,
              scrollTopRatio: loadScroll(filePath),
            });
          } catch (e) {
            console.error('Error loading tab content:', e);
          } finally {
            setLoading(false);
          }
        }
      }

      const filteredTabs = newTabs.filter((t) => openFiles.includes(t.path));
      if (filteredTabs.length !== tabs.length || changed) {
        setTabs(filteredTabs);
      }
    };
    syncTabs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openFiles]);

  // ── Persist tab list on change ───────────────────────────────────────────

  useEffect(() => {
    persistTabs(
      tabs.map((t) => t.path),
      activeFilePath
    );
  }, [tabs, activeFilePath]);

  // ── Set active tab ───────────────────────────────────────────────────────

  useEffect(() => {
    if (activeFilePath) {
      const active = tabs.find((t) => t.path === activeFilePath);
      if (active) {
        setActiveTab(active);
        // Queue cursor+scroll restore for next editor mount or immediately
        if (active.cursorLine) {
          pendingRestoreRef.current = {
            line: active.cursorLine,
            col: active.cursorCol ?? 1,
            scroll: active.scrollTopRatio ?? 0,
          };
          // If editor already mounted, restore now
          if (editorRef.current) {
            const { line, col } = pendingRestoreRef.current;
            try {
              editorRef.current.setPosition({ lineNumber: line, column: col });
              editorRef.current.revealLineInCenter(line);
            } catch {}
            pendingRestoreRef.current = null;
          }
        }
      }
    } else {
      setActiveTab(null);
    }
  }, [activeFilePath, tabs]);

  // ── Connect LSP when language changes ───────────────────────────────────

  useEffect(() => {
    if (!activeFilePath || !monacoRef.current) return;
    const lang = getLanguage(activeFilePath);
    if (LSP_LANGUAGES.has(lang)) {
      connectLSP(lang, monacoRef.current);
    }
  }, [activeFilePath, connectLSP]);

  // ── Ctrl+S save ──────────────────────────────────────────────────────────

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSaveActiveFile();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // ── Refresh on agent edits ───────────────────────────────────────────────

  useEffect(() => {
    const reloadTabs = async () => {
      const updatedTabs = await Promise.all(
        tabs.map(async (tab) => {
          if (tab.isDirty) return tab;
          try {
            const res = await fetch(`/api/files/content?path=${encodeURIComponent(tab.path)}`);
            const data = await res.json();
            return { ...tab, content: data.content, savedContent: data.content, isDirty: false };
          } catch {
            return tab;
          }
        })
      );
      setTabs(updatedTabs);
    };
    if (refreshTrigger > 0 && tabs.length > 0) reloadTabs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  // ── Save active file ─────────────────────────────────────────────────────

  const handleSaveActiveFile = async () => {
    if (!activeTab || !activeTab.isDirty) return;
    try {
      const res = await fetch('/api/files/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTab.path, content: activeTab.content }),
      });
      if (res.ok) {
        setTabs((prev) =>
          prev.map((t) =>
            t.path === activeTab.path ? { ...t, isDirty: false, savedContent: t.content } : t
          )
        );
        onRefreshWorkspace();
      } else {
        alert('Failed to save file');
      }
    } catch (e) {
      console.error(e);
    }
  };

  // ── Editor change handler ────────────────────────────────────────────────

  const handleEditorChange = (value: string | undefined) => {
    if (!activeTab || value === undefined) return;
    setTabs((prev) =>
      prev.map((t) => {
        if (t.path === activeTab.path) {
          return { ...t, content: value, isDirty: value !== t.savedContent };
        }
        return t;
      })
    );
  };

  // ── Backup / rollback ────────────────────────────────────────────────────

  const fetchBackups = async () => {
    if (!activeTab) return;
    try {
      const res = await fetch(`/api/files/backups?path=${encodeURIComponent(activeTab.path)}`);
      if (res.ok) {
        const data = await res.json();
        setBackups(data.backups || []);
      }
    } catch (e) {
      console.error('Error fetching backups:', e);
    }
  };

  const handleRollback = async (timestamp?: number) => {
    if (!activeTab) return;
    try {
      const res = await fetch('/api/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTab.path, timestamp }),
      });
      if (res.ok) {
        setShowBackupsDropdown(false);
        const contentRes = await fetch(`/api/files/content?path=${encodeURIComponent(activeTab.path)}`);
        if (contentRes.ok) {
          const contentData = await contentRes.json();
          setTabs((prev) =>
            prev.map((t) =>
              t.path === activeTab.path
                ? { ...t, content: contentData.content, savedContent: contentData.content, isDirty: false }
                : t
            )
          );
        }
        onRefreshWorkspace();
      } else {
        alert('Failed to rollback file');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const formatTime = (ts: number) => {
    const diff = Date.now() - ts;
    if (diff < 60000) return 'Just now';
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return new Date(ts).toLocaleString();
  };

  // ── Diff mode ─────────────────────────────────────────────────────────────

  const showDiff = proposedDiff && activeTab && proposedDiff.path === activeTab.path;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="h-full flex flex-col bg-[#1e1e1e] text-[#cccccc] overflow-hidden">

      {/* ── Tabs bar ── */}
      <div className="flex bg-[#181818] border-b border-[#2d2d2d] overflow-x-auto min-h-[35px] max-h-[35px] select-none scrollbar-none shrink-0">
        {tabs.map((tab) => {
          const isActive = activeTab?.path === tab.path;
          return (
            <div
              key={tab.path}
              onClick={() => onFileSelect(tab.path)}
              title={tab.path}
              className={`group flex items-center gap-1.5 px-3 h-full border-r border-[#2d2d2d] cursor-pointer text-xs shrink-0 transition-colors ${
                isActive
                  ? 'bg-[#1e1e1e] text-white font-medium border-t-2 border-t-[#8b5cf6]'
                  : 'bg-[#181818] text-gray-400 hover:bg-[#1f1f1f] hover:text-[#cccccc]'
              }`}
            >
              <span className="font-sans">{tab.name}</span>
              {tab.isDirty && (
                <span
                  className="w-1.5 h-1.5 rounded-full bg-[#8b5cf6] shrink-0 font-sans"
                  title="Unsaved changes — press Ctrl+S to save"
                />
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onFileClose(tab.path);
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded-none hover:bg-white/5 text-gray-500 hover:text-white cursor-pointer font-sans"
                title="Close tab"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          );
        })}
      </div>

      {/* ── Editor main area ── */}
      <div className="flex-1 relative overflow-hidden">
        {loading && (
          <div className="absolute inset-0 bg-[#111318]/50 z-10 flex items-center justify-center text-sm font-semibold">
            Loading file...
          </div>
        )}

        {activeTab ? (
          <div className="h-full flex flex-col">

            {/* ── Breadcrumbs bar ── */}
            <div className="flex items-center justify-between px-4 py-1.5 bg-[#12141c] text-[11px] text-gray-500 border-b border-white/5 select-none font-mono">
              <div className="flex items-center gap-1 min-w-0">
                <FileCode className="w-3.5 h-3.5 text-violet-400 shrink-0" />
                {activeTab.path.split('/').map((seg, idx, arr) => (
                  <span key={idx} className="flex items-center gap-1 min-w-0">
                    {idx > 0 && <span className="text-gray-600 font-bold shrink-0">&gt;</span>}
                    <span className={`${idx === arr.length - 1 ? 'text-gray-300 font-medium' : 'hover:text-gray-300 cursor-pointer'} truncate`}>
                      {seg}
                    </span>
                  </span>
                ))}
              </div>

              <div className="flex items-center gap-3 shrink-0 ml-2">
                {/* LSP indicator */}
                {lspReady && (
                  <span className="text-[9px] text-green-400 font-semibold flex items-center gap-0.5" title="Language server connected">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                    LSP
                  </span>
                )}
                {lspError && (
                  <span className="text-[9px] text-amber-500" title={lspError}>⚠ LSP</span>
                )}

                {/* Language label */}
                <span className="text-gray-600">{getLanguage(activeTab.path).toUpperCase()}</span>

                {/* Cursor position */}
                {activeTab.cursorLine && (
                  <span className="text-gray-600">
                    Ln {activeTab.cursorLine}, Col {activeTab.cursorCol ?? 1}
                  </span>
                )}

                {/* Revert history */}
                <div className="relative">
                  <button
                    onClick={() => { fetchBackups(); setShowBackupsDropdown(!showBackupsDropdown); }}
                    className="flex items-center gap-1 text-amber-500 hover:text-amber-400 font-medium cursor-pointer"
                    title="Revert File Backups"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Revert
                  </button>
                  {showBackupsDropdown && (
                    <div className="absolute right-0 mt-2 w-56 bg-[#161822] border border-white/10 rounded-lg shadow-xl z-50 py-1 select-none text-[11px] font-sans text-left">
                      <div className="px-3 py-1 border-b border-white/5 text-[10px] text-gray-500 font-semibold uppercase tracking-wider">
                        Available Backups
                      </div>
                      {backups.length === 0 ? (
                        <div className="px-3 py-2 text-gray-500 italic">No backups found</div>
                      ) : (
                        <div className="max-h-48 overflow-y-auto divide-y divide-white/2">
                          {backups.map((bak) => (
                            <button
                              key={bak.timestamp}
                              onClick={() => handleRollback(bak.timestamp)}
                              className="w-full text-left px-3 py-1.5 hover:bg-violet-600/10 hover:text-violet-400 text-gray-300 transition-colors flex justify-between items-center cursor-pointer font-sans"
                            >
                              <span>{formatTime(bak.timestamp)}</span>
                              <span className="text-[9px] text-gray-600 font-mono">#{bak.timestamp.toString().slice(-4)}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Save button */}
                {activeTab.isDirty && (
                  <button
                    onClick={handleSaveActiveFile}
                    className="flex items-center gap-1 text-violet-400 hover:text-violet-300 font-medium"
                    title="Save (Ctrl+S)"
                  >
                    <Save className="w-3.5 h-3.5" /> Save
                  </button>
                )}
              </div>
            </div>

            {/* ── Monaco Editor / Diff Editor ── */}
            <div className="flex-1 overflow-hidden flex flex-col relative">
              {showDiff && proposedDiff && (
                <div className="bg-[#181a24] border-b border-white/10 px-4 py-2 flex items-center justify-between z-10 shrink-0 select-none">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse"></span>
                    <span className="text-xs font-semibold text-white">AI Proposed Code Changes</span>
                    <span className="text-[10px] font-mono text-gray-400 bg-white/5 px-2 py-0.5 rounded">
                      {proposedDiff.path}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => {
                        handleSaveActiveFile();
                        onRefreshWorkspace();
                      }}
                      className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold shadow transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      ✓ Accept Changes
                    </button>
                    <button 
                      onClick={() => onRefreshWorkspace()}
                      className="px-3 py-1 bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 border border-rose-500/30 rounded text-xs font-semibold transition-colors flex items-center gap-1 cursor-pointer"
                    >
                      ✕ Reject
                    </button>
                    <button 
                      onClick={() => {
                        window.dispatchEvent(new CustomEvent('devpilot-explain-diff', { detail: proposedDiff }));
                      }}
                      className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-gray-300 rounded text-xs font-medium transition-colors"
                    >
                      💡 Explain
                    </button>
                    <button 
                      onClick={() => {
                        window.dispatchEvent(new CustomEvent('devpilot-regenerate-diff', { detail: proposedDiff }));
                      }}
                      className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-violet-300 rounded text-xs font-medium transition-colors"
                    >
                      🔄 Regenerate
                    </button>
                  </div>
                </div>
              )}
              <div className="flex-1 overflow-hidden">
                {showDiff ? (
                  <DiffEditor
                    original={proposedDiff.original}
                    modified={proposedDiff.proposed}
                    language={getLanguage(activeTab.path)}
                    theme="vs-dark"
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
                    key={activeTab.path} // remount on file change so state is clean
                    value={activeTab.content}
                    onChange={handleEditorChange}
                    language={getLanguage(activeTab.path)}
                    theme="vs-dark"
                    height="100%"
                    options={EDITOR_OPTIONS}
                    onMount={handleEditorMount}
                  />
                )}
              </div>
            </div>
          </div>
        ) : (
          /* ── Welcome screen (no file open) ── */
          <div className="h-full bg-[var(--dp-bg-primary)] p-8 flex flex-col justify-center items-center select-none overflow-y-auto font-sans">
            <div className="max-w-4xl w-full mx-auto space-y-8 my-auto">

              {/* Hero */}
              <div className="flex flex-col items-center text-center max-w-2xl mx-auto pt-4 pb-2">
                <div className="relative mb-5 flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#8B5CF6] to-[#3B82F6] shadow-lg shadow-[#8B5CF6]/30">
                  <span className="text-white text-2xl font-black tracking-tighter">DP</span>
                  <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-[#8B5CF6] to-[#3B82F6] blur-md opacity-45 -z-10 animate-pulse-subtle" />
                </div>
                <h1 className="text-3xl font-extrabold text-white tracking-tight leading-none">
                  DevPilot
                </h1>
                <p className="text-xs text-gray-400 mt-2 font-medium tracking-wider uppercase">
                  Multi-Agent Software Engineering Environment
                </p>
              </div>

              {/* Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                {/* Card: Start */}
                <div className="p-5 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-[10px] shadow-md hover:border-[#8b5cf6]/40 hover:-translate-y-0.5 transition-all duration-300 flex flex-col justify-between min-h-[180px]">
                  <div>
                    <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3">Start</h2>
                    <div className="flex flex-col gap-2">
                      <button
                        onClick={onOpenFolder}
                        className="w-full text-left px-3 py-2 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#8b5cf6]/30 hover:bg-[var(--dp-bg-hover)] text-xs text-gray-300 hover:text-white rounded-md cursor-pointer transition-all flex items-center gap-2.5 font-medium"
                      >
                        <span className="w-3.5 h-3.5 text-violet-400 shrink-0">📁</span>
                        <span>Open Folder...</span>
                      </button>

                      <button
                        onClick={() => {
                          window.dispatchEvent(new KeyboardEvent('keydown', { key: 'p', ctrlKey: true, bubbles: true }));
                        }}
                        className="w-full text-left px-3 py-2 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#8b5cf6]/30 hover:bg-[var(--dp-bg-hover)] text-xs text-gray-300 hover:text-white rounded-md cursor-pointer transition-all flex items-center gap-2.5 font-medium"
                      >
                        <span className="w-3.5 h-3.5 text-violet-400 shrink-0">🔍</span>
                        <span>Quick Open <kbd className="text-[9px] bg-white/10 px-1 rounded">Ctrl+P</kbd></span>
                      </button>

                      <button
                        onClick={() => {
                          const event = new KeyboardEvent('keydown', { ctrlKey: true, shiftKey: true, key: 'P', bubbles: true });
                          window.dispatchEvent(event);
                        }}
                        className="w-full text-left px-3 py-2 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#8b5cf6]/30 hover:bg-[var(--dp-bg-hover)] text-xs text-gray-300 hover:text-white rounded-md cursor-pointer transition-all flex items-center gap-2.5 font-medium"
                      >
                        <span className="w-3.5 h-3.5 text-violet-400 shrink-0">⌨️</span>
                        <span>Command Palette</span>
                      </button>

                      <button
                        onClick={async () => {
                          if (!workspacePath) { alert('Please open a workspace first.'); return; }
                          const filename = prompt('Enter new file path (relative to workspace, e.g. test.py):');
                          if (!filename?.trim()) return;
                          try {
                            const res = await fetch('/api/files/create', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ path: filename.trim(), is_dir: false }),
                            });
                            if (res.ok) onFileSelect(filename.trim());
                            else { const d = await res.json(); alert('Failed to create file: ' + (d.detail || 'Unknown error')); }
                          } catch { alert('Error creating file.'); }
                        }}
                        className="w-full text-left px-3 py-2 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#8b5cf6]/30 hover:bg-[var(--dp-bg-hover)] text-xs text-gray-300 hover:text-white rounded-md cursor-pointer transition-all flex items-center gap-2.5 font-medium"
                      >
                        <span className="w-3.5 h-3.5 text-violet-400 shrink-0">➕</span>
                        <span>New File...</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Card: Recent Workspace */}
                <div className="p-5 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-[10px] shadow-md hover:border-[#8b5cf6]/40 hover:-translate-y-0.5 transition-all duration-300 flex flex-col justify-between min-h-[180px]">
                  <div>
                    <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3">Workspace</h2>
                    <div className="p-3 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] rounded-md text-xs text-gray-400 space-y-2">
                      {workspacePath ? (
                        <div>
                          <div className="text-white font-semibold truncate font-mono">
                            {workspacePath.split('/').pop() || workspacePath.split('\\').pop()}
                          </div>
                          <div className="text-[9px] text-gray-500 font-mono truncate select-all mt-1">{workspacePath}</div>
                        </div>
                      ) : (
                        <div className="italic text-gray-600">No folder loaded. Open a workspace folder to begin coding.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Tip banner */}
              <div className="p-4 bg-gradient-to-r from-[#8B5CF6]/10 to-[#3B82F6]/5 border border-[#8B5CF6]/15 rounded-[10px] flex items-start gap-3">
                <div className="p-1 bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 text-[#8B5CF6] rounded shrink-0 text-sm">💡</div>
                <div>
                  <h4 className="text-[10px] font-bold text-white uppercase tracking-wider">Tip of the Day</h4>
                  <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
                    Press <code className="text-violet-300 font-mono font-bold bg-violet-950/40 px-1 py-0.2 rounded">Ctrl+P</code> to quick-open any file,{' '}
                    <code className="text-violet-300 font-mono font-bold bg-violet-950/40 px-1 py-0.2 rounded">Ctrl+Shift+O</code> to jump to a symbol, and{' '}
                    <code className="text-violet-300 font-mono font-bold bg-violet-950/40 px-1 py-0.2 rounded">@filename</code> in AI Chat to attach files to the agent context.
                  </p>
                </div>
              </div>

            </div>
          </div>
        )}
      </div>
    </div>
  );
}