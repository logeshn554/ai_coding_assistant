import React, { useState, useEffect, useRef } from 'react';
import {
  Puzzle,
  Search,
  Upload,
  Power,
  RefreshCw,
  Download,
  Trash2,
  Loader2,
  Play,
  Terminal,
  Code,
  Zap,
  CheckCircle,
  XCircle
} from 'lucide-react';

interface Extension {
  id: string;
  name: string;
  description: string;
  version: string;
  category?: string;
  publisher?: string;
  installed: boolean;
  enabled?: boolean;
  downloads?: number;
  download_url?: string;
  icon_url?: string;
}

interface ActiveCapability {
  id: string;
  name: string;
  publisher: string;
  version: string;
  description: string;
  status: string;
  dir?: string;
  main?: string;
  commands: Array<{ id: string; title: string; category?: string; description?: string }>;
  snippets: Array<{ name: string; language: string; prefix: string; description?: string }>;
  ai_tools: Array<{ name: string; description: string }>;
}

export default function ExtensionsSidebar() {
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'installed' | 'marketplace' | 'active'>('installed');
  const [installedExtensions, setInstalledExtensions] = useState<Extension[]>([]);
  const [marketplaceExtensions, setMarketplaceExtensions] = useState<Extension[]>([]);
  const [activeCapabilities, setActiveCapabilities] = useState<ActiveCapability[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [executingCmdId, setExecutingCmdId] = useState<string | null>(null);
  const [lastOutput, setLastOutput] = useState<{ title: string; text: string; success: boolean } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchInstalled = async () => {
    try {
      const res = await fetch('/api/extensions/installed');
      if (res.ok) {
        const data = await res.json();
        setInstalledExtensions(data.extensions || []);
      }
    } catch (e) {
      console.error('Failed to fetch installed extensions:', e);
    }
  };

  const fetchActiveCapabilities = async () => {
    try {
      const res = await fetch('/api/extensions/active');
      if (res.ok) {
        const data = await res.json();
        setActiveCapabilities(data.active_extensions || []);
      }
    } catch (e) {
      console.error('Failed to fetch active capabilities:', e);
    }
  };

  const searchMarketplace = async (query: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/extensions/search?query=${encodeURIComponent(query)}&size=30`);
      if (res.ok) {
        const data = await res.json();
        setMarketplaceExtensions(data.extensions || []);
      }
    } catch (e) {
      console.error('Failed to search marketplace:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInstalled();
    fetchActiveCapabilities();
    searchMarketplace(search || 'python');
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (search.trim() || activeTab === 'marketplace') {
        searchMarketplace(search || 'tools');
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [search, activeTab]);

  const handleInstall = async (ext: Extension) => {
    setActionLoadingId(ext.id);
    try {
      const res = await fetch('/api/extensions/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: ext.id,
          name: ext.name,
          description: ext.description,
          version: ext.version,
          category: ext.category,
          publisher: ext.publisher,
          download_url: ext.download_url
        })
      });
      if (res.ok) {
        await fetchInstalled();
        await fetchActiveCapabilities();
        setMarketplaceExtensions(prev =>
          prev.map(item => item.id === ext.id ? { ...item, installed: true, enabled: true } : item)
        );
      }
    } catch (e) {
      console.error('Install error:', e);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleUninstall = async (ext: Extension) => {
    setActionLoadingId(ext.id);
    try {
      const res = await fetch('/api/extensions/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: ext.id })
      });
      if (res.ok) {
        await fetchInstalled();
        await fetchActiveCapabilities();
        setMarketplaceExtensions(prev =>
          prev.map(item => item.id === ext.id ? { ...item, installed: false, enabled: false } : item)
        );
      }
    } catch (e) {
      console.error('Uninstall error:', e);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleToggleEnable = async (ext: Extension) => {
    const nextState = !(ext.enabled !== false);
    try {
      const res = await fetch('/api/extensions/toggle-enable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: ext.id, enabled: nextState })
      });
      if (res.ok) {
        await fetchInstalled();
        await fetchActiveCapabilities();
      }
    } catch (e) {
      console.error('Toggle error:', e);
    }
  };

  const handleVsixUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus(`Installing ${file.name}...`);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/extensions/load-vsix', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        setUploadStatus(`Installed ${file.name}`);
        await fetchInstalled();
        await fetchActiveCapabilities();
      } else {
        const err = await res.json();
        setUploadStatus(`Error: ${err.detail || 'Failed to install'}`);
      }
    } catch {
      setUploadStatus('Upload failed');
    } finally {
      setTimeout(() => setUploadStatus(null), 3500);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const executeCommand = async (cmdId: string, cmdTitle: string) => {
    setExecutingCmdId(cmdId);
    try {
      const res = await fetch('/api/extensions/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command_id: cmdId })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setLastOutput({ title: cmdTitle, text: data.output || 'Executed successfully.', success: true });
      } else {
        setLastOutput({ title: cmdTitle, text: data.detail || data.error || 'Execution failed.', success: false });
      }
      await fetchActiveCapabilities();
    } catch (e) {
      setLastOutput({ title: cmdTitle, text: `Execution error: ${e}`, success: false });
    } finally {
      setExecutingCmdId(null);
    }
  };

  const displayedList = React.useMemo(() => {
    if (activeTab === 'installed') {
      if (!search.trim()) return installedExtensions.filter(e => e.installed);
      const q = search.toLowerCase();
      return installedExtensions.filter(
        e => e.installed && (e.name.toLowerCase().includes(q) || e.description.toLowerCase().includes(q))
      );
    }
    return marketplaceExtensions;
  }, [activeTab, search, installedExtensions, marketplaceExtensions]);

  return (
    <div className="h-full flex flex-col font-sans select-none border-r border-[#2A3146] bg-[#11131A] text-zinc-200">
      
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#2A3146] bg-[#161922] shrink-0">
        <div className="flex items-center gap-2">
          <Puzzle className="w-4 h-4 text-purple-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">Extensions Engine</span>
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleVsixUpload}
            accept=".vsix,.zip"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
            title="Install from VSIX Package..."
          >
            <Upload className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => { fetchInstalled(); fetchActiveCapabilities(); searchMarketplace(search || 'python'); }}
            className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
            title="Refresh Extensions & Capabilities"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Upload Toast */}
      {uploadStatus && (
        <div className="px-3 py-1.5 bg-purple-950/60 border-b border-purple-500/30 text-purple-200 text-[10px] font-mono flex items-center gap-1.5 animate-[fadeIn_150ms_ease-out]">
          <Loader2 className="w-3 h-3 animate-spin text-purple-400 shrink-0" />
          <span className="truncate">{uploadStatus}</span>
        </div>
      )}

      {/* Search Input */}
      <div className="p-2.5 border-b border-[#2A3146] bg-[#141620] shrink-0">
        <div className="relative flex items-center">
          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search Open VSX Marketplace..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-2.5 py-1.5 bg-black/40 border border-white/10 rounded-xl text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-purple-500 transition-colors"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex px-2 py-1.5 border-b border-[#2A3146] bg-[#141620] gap-1 text-[10.5px] shrink-0">
        <button
          onClick={() => setActiveTab('installed')}
          className={`flex-1 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
            activeTab === 'installed'
              ? 'bg-purple-600/30 text-purple-300 border border-purple-500/30'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Installed ({installedExtensions.filter(e => e.installed).length})
        </button>
        <button
          onClick={() => setActiveTab('active')}
          className={`flex-1 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
            activeTab === 'active'
              ? 'bg-emerald-600/30 text-emerald-300 border border-emerald-500/30'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Active ({activeCapabilities.length})
        </button>
        <button
          onClick={() => setActiveTab('marketplace')}
          className={`flex-1 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
            activeTab === 'marketplace'
              ? 'bg-purple-600/30 text-purple-300 border border-purple-500/30'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          Marketplace
        </button>
      </div>

      {/* Main View Area */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {activeTab === 'active' ? (
          <div className="space-y-2">
            <div className="p-2 rounded-xl bg-emerald-950/30 border border-emerald-500/20 text-emerald-300 text-[11px] flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>
                {activeCapabilities.length} Dynamic Extensions Active in IDE Engine
              </span>
            </div>

            {activeCapabilities.length === 0 ? (
              <div className="py-12 text-center text-xs text-zinc-500">
                No active extensions loaded. Enable an installed extension to activate its capabilities.
              </div>
            ) : (
              activeCapabilities.map((act) => (
                <div
                  key={act.id}
                  className="p-3 rounded-xl border border-white/10 bg-white/[0.03] space-y-2.5"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-zinc-100">{act.name}</span>
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          Active
                        </span>
                      </div>
                      <p className="text-[10px] text-zinc-400 mt-0.5">{act.description}</p>
                    </div>
                  </div>

                  {/* Commands Section */}
                  {act.commands.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-semibold text-purple-300 uppercase tracking-wider flex items-center gap-1">
                        <Terminal className="w-3 h-3 text-purple-400" /> Contributed Commands ({act.commands.length})
                      </span>
                      <div className="space-y-1 pl-1">
                        {act.commands.map((cmd) => (
                          <div
                            key={cmd.id}
                            className="flex items-center justify-between p-1.5 bg-black/40 rounded-lg border border-white/5 hover:border-purple-500/30 transition-colors"
                          >
                            <div className="min-w-0 flex-1 pr-2">
                              <div className="text-[11px] font-medium text-zinc-200 truncate">{cmd.title}</div>
                              <div className="text-[9px] font-mono text-zinc-500 truncate">{cmd.id}</div>
                            </div>
                            <button
                              onClick={() => executeCommand(cmd.id, cmd.title)}
                              disabled={executingCmdId === cmd.id}
                              className="px-2 py-1 rounded bg-purple-600/40 hover:bg-purple-600 text-purple-200 text-[10px] font-semibold flex items-center gap-1 cursor-pointer transition-colors shrink-0 disabled:opacity-50"
                            >
                              {executingCmdId === cmd.id ? (
                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              ) : (
                                <Play className="w-2.5 h-2.5 fill-purple-200" />
                              )}
                              Run
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI Tools Section */}
                  {act.ai_tools.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-semibold text-blue-300 uppercase tracking-wider flex items-center gap-1">
                        <Zap className="w-3 h-3 text-blue-400" /> Contributed AI Tools ({act.ai_tools.length})
                      </span>
                      <div className="space-y-1 pl-1">
                        {act.ai_tools.map((tool) => (
                          <div key={tool.name} className="p-1.5 bg-blue-950/20 rounded-lg border border-blue-500/20 text-[10px]">
                            <span className="font-mono text-blue-300 font-bold">{tool.name}</span>
                            <p className="text-zinc-400 text-[9px] mt-0.5">{tool.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Snippets Section */}
                  {act.snippets.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1">
                        <Code className="w-3 h-3 text-amber-400" /> Contributed Snippets ({act.snippets.length})
                      </span>
                      <div className="flex flex-wrap gap-1 pl-1">
                        {act.snippets.map((snip) => (
                          <span key={snip.name} className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 text-[9.5px] font-mono">
                            {snip.prefix || snip.name} ({snip.language})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        ) : loading && displayedList.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-zinc-500 space-y-2">
            <Loader2 className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin text-purple-400" />
            <span className="text-xs">Searching Open VSX Registry...</span>
          </div>
        ) : displayedList.length === 0 ? (
          <div className="py-12 flex flex-col items-center justify-center text-zinc-500 space-y-1 text-xs">
            <span>No extensions found</span>
            {activeTab === 'installed' && (
              <button
                onClick={() => setActiveTab('marketplace')}
                className="text-purple-400 hover:underline pt-1"
              >
                Browse Marketplace
              </button>
            )}
          </div>
        ) : (
          displayedList.map((ext) => {
            const isInstalled = ext.installed || installedExtensions.some(e => e.id === ext.id && e.installed);
            const isEnabled = ext.enabled !== false;
            const isActionLoading = actionLoadingId === ext.id;
            const activeCap = activeCapabilities.find(a => a.id === ext.id);

            return (
              <div
                key={ext.id}
                className="p-2.5 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/15 transition-all flex flex-col gap-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <div className="w-7 h-7 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center shrink-0 mt-0.5 overflow-hidden">
                      {ext.icon_url ? (
                        <img src={ext.icon_url} alt="" className="w-5 h-5 object-contain" />
                      ) : (
                        <Puzzle className="w-3.5 h-3.5 text-purple-400" />
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-xs text-zinc-100 truncate">{ext.name}</span>
                        <span className="text-[9px] font-mono text-zinc-500 shrink-0">v{ext.version}</span>
                        {isInstalled && isEnabled && (
                          <span className="px-1 py-0.5 rounded text-[8px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="text-[10px] text-zinc-400 line-clamp-2 leading-relaxed mt-0.5">
                        {ext.description || 'VS Code Extension'}
                      </p>
                      <div className="flex items-center gap-2 mt-1 text-[9px] text-zinc-500">
                        <span>{ext.publisher || 'Community'}</span>
                        {activeCap && activeCap.commands.length > 0 && (
                          <span className="text-purple-400">• {activeCap.commands.length} commands</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Actions Row */}
                <div className="flex items-center justify-between pt-1.5 border-t border-white/5">
                  <div className="flex items-center gap-1">
                    {isInstalled && (
                      <button
                        onClick={() => handleToggleEnable(ext)}
                        className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold transition-colors cursor-pointer ${
                          isEnabled
                            ? 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                            : 'bg-zinc-800 text-zinc-400 hover:text-white'
                        }`}
                        title={isEnabled ? 'Disable Extension' : 'Enable Extension'}
                      >
                        <Power className="w-2.5 h-2.5" />
                        <span>{isEnabled ? 'Enabled' : 'Disabled'}</span>
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5">
                    {isInstalled ? (
                      <button
                        onClick={() => handleUninstall(ext)}
                        disabled={isActionLoading}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-[10.5px] font-semibold transition-colors cursor-pointer disabled:opacity-50"
                      >
                        {isActionLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                        <span>Uninstall</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => handleInstall(ext)}
                        disabled={isActionLoading}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-[10.5px] font-bold shadow-sm transition-all cursor-pointer disabled:opacity-50"
                      >
                        {isActionLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                        <span>Install</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Execution Output Panel */}
      {lastOutput && (
        <div className="p-3 border-t border-[#2A3146] bg-[#0c0e14] text-[11px] space-y-1.5 shrink-0">
          <div className="flex items-center justify-between">
            <span className="font-bold text-purple-300 flex items-center gap-1.5">
              {lastOutput.success ? (
                <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              ) : (
                <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
              )}
              {lastOutput.title}
            </span>
            <button
              onClick={() => setLastOutput(null)}
              className="text-zinc-500 hover:text-zinc-300 text-[10px]"
            >
              Dismiss
            </button>
          </div>
          <pre className="p-2 bg-black/60 rounded-lg text-[10px] font-mono text-zinc-300 whitespace-pre-wrap max-h-32 overflow-y-auto border border-white/5">
            {lastOutput.text}
          </pre>
        </div>
      )}

    </div>
  );
}