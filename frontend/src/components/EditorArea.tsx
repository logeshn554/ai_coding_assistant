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
}

export default function EditorArea({
  activeFilePath,
  openFiles,
  onFileClose,
  onFileSelect,
  proposedDiff,
  onRefreshWorkspace,
  refreshTrigger
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
      // Add tabs for any path in openFiles that isn't in tabs yet
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

      // Remove tabs that are no longer in openFiles
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
        if (tab.isDirty) return tab; // Skip dirty tabs to prevent losing unsaved user work
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
        // Update tabs state
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
    <div className="h-full flex flex-col bg-[#111318] text-gray-300 overflow-hidden">
      
      {/* Tabs bar */}
      <div className="flex bg-[#0e1014] border-b border-white/5 overflow-x-auto min-h-[35px] max-h-[35px] select-none scrollbar-none">
        {tabs.map(tab => {
          const isActive = activeTab?.path === tab.path;
          return (
            <div
              key={tab.path}
              onClick={() => onFileSelect(tab.path)}
              className={`group flex items-center gap-2 px-4 h-full border-r border-white/5 cursor-pointer text-xs transition-colors shrink-0 ${
                isActive 
                  ? 'bg-[#111318] text-white font-medium border-t-2 border-t-violet-500' 
                  : 'bg-[#0b0c10] text-gray-400 hover:bg-[#0f1116] hover:text-gray-200'
              }`}
            >
              <span>{tab.name}</span>
              {tab.isDirty && (
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400 shrink-0" title="Unsaved changes" />
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onFileClose(tab.path);
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-white/10 text-gray-500 hover:text-white"
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
                  }}
                  onMount={(editor) => {
                    editorRef.current = editor;
                  }}
                />
              )}
            </div>

          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center text-gray-500">
            <FileCode className="w-16 h-16 text-gray-700 mb-3 animate-pulse-subtle" />
            <h1 className="text-xl font-bold text-white mb-1">DevPilot Editor</h1>
            <p className="text-xs max-w-xs text-gray-600">
              Double-click a file in the explorer sidebar to open it, or type a request in the AI Panel to begin.
            </p>
          </div>
        )}
      </div>

    </div>
  );
}
