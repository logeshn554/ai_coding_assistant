import { useState, useEffect, useRef } from 'react';
import Editor, { DiffEditor } from '@monaco-editor/react';
import { X, Save, FileCode, RotateCcw } from 'lucide-react';

interface Tab {
  path: string;
  name: string;
  isDirty: boolean;
  content: string;
  savedContent: string;
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
}

export default function EditorArea({
  activeFilePath,
  openFiles,
  onFileClose,
  onFileSelect,
  proposedDiff,
  onRefreshWorkspace,
  refreshTrigger,
  onOpenFolder,
  workspacePath
}: EditorAreaProps) {
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTab, setActiveTab] = useState<Tab | null>(null);
  const [loading, setLoading] = useState(false);
  const editorRef = useRef<any>(null);
  const [backups, setBackups] = useState<{ timestamp: number; filename: string }[]>([]);
  const [showBackupsDropdown, setShowBackupsDropdown] = useState(false);


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
        body: JSON.stringify({
          path: activeTab.path,
          timestamp
        })
      });
      if (res.ok) {
        setShowBackupsDropdown(false);
        const contentRes = await fetch(`/api/files/content?path=${encodeURIComponent(activeTab.path)}`);
        if (contentRes.ok) {
          const contentData = await contentRes.json();
          setTabs(prev => prev.map(t => {
            if (t.path === activeTab.path) {
              return { ...t, content: contentData.content, savedContent: contentData.content, isDirty: false };
            }
            return t;
          }));
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

  // Synchronize openFiles list with tabs state
  useEffect(() => {
    const syncTabs = async () => {
      const existingPaths = tabs.map(t => t.path);
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
            
            newTabs.push({
              path: filePath,
              name: tabName,
              isDirty: false,
              content: data.content,
              savedContent: data.content
            });
          } catch (e) {
            console.error('Error loading tab content:', e);
          } finally {
            setLoading(false);
          }
        }
      }

      const filteredTabs = newTabs.filter(t => openFiles.includes(t.path));
      if (filteredTabs.length !== tabs.length || changed) {
        setTabs(filteredTabs);
      }
    };

    syncTabs();
  }, [openFiles]);

  // Set the active tab when activeFilePath changes
  useEffect(() => {
    if (activeFilePath) {
      const active = tabs.find(t => t.path === activeFilePath);
      if (active) {
        setActiveTab(active);
      }
    } else {
      setActiveTab(null);
    }
  }, [activeFilePath, tabs]);

  // Intercept Ctrl+S / Cmd+S to save the active file
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSaveActiveFile();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab]);

  // Re-fetch content for open tabs when refreshTrigger changes (e.g. after agent edits)
  useEffect(() => {
    const reloadTabs = async () => {
      const updatedTabs = await Promise.all(tabs.map(async (tab) => {
        if (tab.isDirty) return tab;
        try {
          const res = await fetch(`/api/files/content?path=${encodeURIComponent(tab.path)}`);
          const data = await res.json();
          return {
            ...tab,
            content: data.content,
            savedContent: data.content,
            isDirty: false
          };
        } catch (e) {
          console.error('Error reloading tab content:', e);
          return tab;
        }
      }));
      setTabs(updatedTabs);
    };

    if (refreshTrigger > 0 && tabs.length > 0) {
      reloadTabs();
    }
  }, [refreshTrigger]);

  const handleSaveActiveFile = async () => {
    if (!activeTab || !activeTab.isDirty) return;
    try {
      const res = await fetch('/api/files/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: activeTab.path,
          content: activeTab.content
        })
      });
      if (res.ok) {
        setTabs(prev => prev.map(t => {
          if (t.path === activeTab.path) {
            return { ...t, isDirty: false, savedContent: t.content };
          }
          return t;
        }));
        onRefreshWorkspace();
      } else {
        alert('Failed to save file');
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleEditorChange = (value: string | undefined) => {
    if (!activeTab || value === undefined) return;
    
    setTabs(prev => prev.map(t => {
      if (t.path === activeTab.path) {
        const isDirty = value !== t.savedContent;
        return { ...t, content: value, isDirty };
      }
      return t;
    }));
  };

  const getLanguage = (path: string) => {
    const ext = path.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'ts': return 'typescript';
      case 'tsx': return 'typescript';
      case 'js': return 'javascript';
      case 'jsx': return 'javascript';
      case 'json': return 'json';
      case 'py': return 'python';
      case 'css': return 'css';
      case 'html': return 'html';
      case 'md': return 'markdown';
      default: return 'plaintext';
    }
  };



  // Determine if there is a proposed diff for the active tab
  const showDiff = proposedDiff && activeTab && proposedDiff.path === activeTab.path;

  return (
    <div className="h-full flex flex-col bg-[#1e1e1e] text-[#cccccc] overflow-hidden">
      
      {/* Tabs bar */}
      <div className="flex bg-[#181818] border-b border-[#2d2d2d] overflow-x-auto min-h-[35px] max-h-[35px] select-none scrollbar-none shrink-0">
        {tabs.map(tab => {
          const isActive = activeTab?.path === tab.path;
          return (
            <div
              key={tab.path}
              onClick={() => onFileSelect(tab.path)}
              className={`group flex items-center gap-1.5 px-3 h-full border-r border-[#2d2d2d] cursor-pointer text-xs shrink-0 ${
                isActive 
                  ? 'bg-[#1e1e1e] text-white font-medium border-t-2 border-t-[#8b5cf6]' 
                  : 'bg-[#181818] text-gray-400 hover:bg-[#1f1f1f] hover:text-[#cccccc]'
              }`}
            >
              <span className="font-sans">{tab.name}</span>
              {tab.isDirty && (
                <span className="w-1.5 h-1.5 rounded-full bg-[#8b5cf6] shrink-0 font-sans" title="Unsaved changes" />
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onFileClose(tab.path);
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded-none hover:bg-white/5 text-gray-500 hover:text-white cursor-pointer font-sans"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Editor Main Section */}
      <div className="flex-1 relative overflow-hidden">
        {loading && (
          <div className="absolute inset-0 bg-[#111318]/50 z-10 flex items-center justify-center text-sm font-semibold">
            Loading file...
          </div>
        )}
        
        {activeTab ? (
          <div className="h-full flex flex-col">
            
            {/* Interactive Breadcrumbs Bar */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#12141c] text-[11px] text-gray-500 border-b border-white/5 select-none font-mono">
              <div className="flex items-center gap-1">
                <FileCode className="w-3.5 h-3.5 text-violet-400 shrink-0" />
                {activeTab.path.split('/').map((seg, idx, arr) => (
                  <span key={idx} className="flex items-center gap-1">
                    {idx > 0 && <span className="text-gray-600 font-bold">&gt;</span>}
                    <span className={idx === arr.length - 1 ? "text-gray-300 font-medium" : "hover:text-gray-300 cursor-pointer"}>
                      {seg}
                    </span>
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-4 relative">
                <span>{getLanguage(activeTab.path).toUpperCase()}</span>
                
                {/* Revert History Button */}
                <div className="relative">
                  <button
                    onClick={() => {
                      fetchBackups();
                      setShowBackupsDropdown(!showBackupsDropdown);
                    }}
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
                              <span className="text-[9px] text-gray-650 font-mono">#{bak.timestamp.toString().slice(-4)}</span>
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
                    className="flex items-center gap-1 text-violet-400 hover:text-violet-300 font-medium"
                  >
                    <Save className="w-3.5 h-3.5" /> Save
                  </button>
                )}

              </div>
            </div>

            {/* Editor element */}
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
                  }}
                />
              ) : (
                <Editor
                  value={activeTab.content}
                  onChange={handleEditorChange}
                  language={getLanguage(activeTab.path)}
                  theme="vs-dark"
                  height="100%"
                  options={{
                    fontSize: 13,
                    fontFamily: "'Fira Code', 'Courier New', monospace",
                    minimap: { enabled: true },
                    wordWrap: "on",
                    lineNumbers: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    stickyScroll: { enabled: true },
                  }}
                  onMount={(editor, monaco) => {
                    editorRef.current = editor;
                    
                    // Listen to cursor position changes
                    editor.onDidChangeCursorPosition((e) => {
                      const position = e.position;
                      window.dispatchEvent(new CustomEvent('editor-cursor-change', {
                        detail: { line: position.lineNumber, column: position.column }
                      }));
                    });

                    // Listen to markers (diagnostics) changes
                    const updateDiagnostics = () => {
                      const model = editor.getModel();
                      if (model) {
                        const markers = monaco.editor.getModelMarkers({ resource: model.uri });
                        const errors = markers.filter((m: any) => m.severity === monaco.MarkerSeverity.Error).length;
                        const warnings = markers.filter((m: any) => m.severity === monaco.MarkerSeverity.Warning).length;
                        window.dispatchEvent(new CustomEvent('editor-diagnostics', {
                          detail: { errors, warnings }
                        }));
                      }
                    };

                    // Initial diagnostics check
                    updateDiagnostics();

                    // Register listeners for markers change
                    const markersListener = monaco.editor.onDidChangeMarkers((uris: any[]) => {
                      const model = editor.getModel();
                      if (model && uris.some((uri: any) => uri.toString() === model.uri.toString())) {
                        updateDiagnostics();
                      }
                    });

                    // Store disposal cleanups on the editor object if needed, or handle on unmount
                    (editor as any)._markersListener = markersListener;
                  }}
                />
              )}
            </div>
          </div>
        ) : (
          <div className="h-full bg-[var(--dp-bg-primary)] p-8 flex flex-col justify-center items-center select-none overflow-y-auto font-sans">
            <div className="max-w-4xl w-full mx-auto space-y-8 my-auto">
              
              {/* Centered Hero */}
              <div className="flex flex-col items-center text-center max-w-2xl mx-auto pt-4 pb-2">
                <div className="relative mb-5 flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#8B5CF6] to-[#3B82F6] shadow-lg shadow-[#8B5CF6]/30">
                  {/* Glowing, pulsed background */}
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

              {/* Grid Layout of Two Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Card 1: Start */}
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
                          const event = new KeyboardEvent('keydown', { ctrlKey: true, shiftKey: true, key: 'P' });
                          window.dispatchEvent(event);
                        }}
                        className="w-full text-left px-3 py-2 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#8b5cf6]/30 hover:bg-[var(--dp-bg-hover)] text-xs text-gray-300 hover:text-white rounded-md cursor-pointer transition-all flex items-center gap-2.5 font-medium"
                      >
                        <span className="w-3.5 h-3.5 text-violet-400 shrink-0">⌨️</span>
                        <span>Command Palette</span>
                      </button>

                      <button
                        onClick={async () => {
                          if (!workspacePath) {
                            alert("Please open a workspace first.");
                            return;
                          }
                          const filename = prompt("Enter new file path (relative to workspace, e.g. test.py):");
                          if (!filename || !filename.trim()) return;
                          try {
                            const res = await fetch("/api/files/create", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ path: filename.trim(), is_dir: false })
                            });
                            if (res.ok) {
                              onFileSelect?.(filename.trim());
                            } else {
                              const data = await res.json();
                              alert("Failed to create file: " + (data.detail || "Unknown error"));
                            }
                          } catch (e) {
                            console.error(e);
                            alert("Error creating file.");
                          }
                        }}
                        className="w-full text-left px-3 py-2 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#8b5cf6]/30 hover:bg-[var(--dp-bg-hover)] text-xs text-gray-300 hover:text-white rounded-md cursor-pointer transition-all flex items-center gap-2.5 font-medium"
                      >
                        <span className="w-3.5 h-3.5 text-violet-400 shrink-0">➕</span>
                        <span>New File...</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* Card 2: Recent Workspace */}
                <div className="p-5 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-[10px] shadow-md hover:border-[#8b5cf6]/40 hover:-translate-y-0.5 transition-all duration-300 flex flex-col justify-between min-h-[180px]">
                  <div>
                    <h2 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-3">Recent Workspace</h2>
                    <div className="p-3 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] rounded-md text-xs text-gray-400 space-y-2">
                      {workspacePath ? (
                        <div>
                          <div className="text-white font-semibold truncate font-mono">{workspacePath.split('/').pop() || workspacePath.split('\\').pop()}</div>
                          <div className="text-[9px] text-gray-500 font-mono truncate select-all mt-1">{workspacePath}</div>
                        </div>
                      ) : (
                        <div className="italic text-gray-600">No folder loaded. Open a workspace folder to begin coding.</div>
                      )}
                    </div>
                  </div>
                </div>

              </div>

              {/* Bottom Tip of the Day Banner */}
              <div className="p-4 bg-gradient-to-r from-[#8B5CF6]/10 to-[#3B82F6]/5 border border-[#8B5CF6]/15 rounded-[10px] flex items-start gap-3 mt-6">
                <div className="p-1 bg-[#8B5CF6]/10 border border-[#8B5CF6]/20 text-[#8B5CF6] rounded shrink-0 text-sm">
                  💡
                </div>
                <div>
                  <h4 className="text-[10px] font-bold text-white uppercase tracking-wider">Tip of the Day</h4>
                  <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">
                    Use <code className="text-violet-300 font-mono font-bold bg-violet-950/40 px-1 py-0.2 rounded">@filename</code> in the AI Chat panel to attach specific files to the agent context. Try switching to <code className="text-violet-300 font-mono font-bold bg-violet-950/40 px-1 py-0.2 rounded">Agent</code> mode for autonomous multi-file edits.
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