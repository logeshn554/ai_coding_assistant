import React, { useState, useEffect, useRef } from 'react';
import { Puzzle, Search, Upload, Power, RefreshCw, Download, Trash2, Loader2 } from 'lucide-react';

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

export default function ExtensionsSidebar() {
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'installed' | 'marketplace' | 'recommended'>('installed');
  const [installedExtensions, setInstalledExtensions] = useState<Extension[]>([]);
  const [marketplaceExtensions, setMarketplaceExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
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
    searchMarketplace(search || 'python');
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (search.trim() || activeTab === 'marketplace' || activeTab === 'recommended') {
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
        fetchInstalled();
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

  // Compute displayed list based on active tab and search
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
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">Extensions</span>
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
            onClick={() => { fetchInstalled(); searchMarketplace(search || 'python'); }}
            className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
            title="Refresh Extensions"
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

      {/* Extension List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {loading && displayedList.length === 0 ? (
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
                      </div>
                      <p className="text-[10px] text-zinc-400 line-clamp-2 leading-relaxed mt-0.5">
                        {ext.description || 'VS Code Extension'}
                      </p>
                      <div className="flex items-center gap-2 mt-1 text-[9px] text-zinc-500">
                        <span>{ext.publisher || 'Community'}</span>
                        {typeof ext.downloads === 'number' && ext.downloads > 0 && (
                          <span>• {ext.downloads.toLocaleString()} downloads</span>
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

    </div>
  );
}