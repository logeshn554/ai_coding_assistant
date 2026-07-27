import React, { useState, useEffect, useRef } from 'react';
import { Puzzle, Search, Upload, Power, ShieldCheck, RefreshCw } from 'lucide-react';


interface Extension {
  id: string;
  name: string;
  description: string;
  version: string;
  category?: string;
  publisher?: string;
  installed: boolean;
  enabled?: boolean;
}

export default function ExtensionsSidebar() {
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'installed' | 'recommended'>('all');
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchExtensions = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/extensions/installed');
      const data = await res.json();
      setExtensions(data.extensions || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleInstall = async (ext: Extension) => {
    try {
      const action = ext.installed ? 'uninstall' : 'install';
      const res = await fetch(`/api/extensions/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: ext.id,
          name: ext.name,
          description: ext.description,
          version: ext.version,
          category: ext.category
        })
      });
      if (res.ok) {
        fetchExtensions();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleToggleEnable = async (ext: Extension) => {
    try {
      const res = await fetch('/api/extensions/toggle-enable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: ext.id, enabled: !(ext.enabled !== false) })
      });
      if (res.ok) {
        fetchExtensions();
      }
    } catch (e) {
      console.error(e);
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
        setUploadStatus(`Successfully loaded ${file.name}`);
        fetchExtensions();
      } else {
        const err = await res.json();
        setUploadStatus(`Failed: ${err.detail || 'Error parsing VSIX'}`);
      }
    } catch (err) {
      setUploadStatus('Upload failed');
    } finally {
      setTimeout(() => setUploadStatus(null), 3500);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const filteredExtensions = extensions.filter(ext => {
    const matchesSearch = ext.name.toLowerCase().includes(search.toLowerCase()) ||
      ext.description.toLowerCase().includes(search.toLowerCase()) ||
      (ext.category && ext.category.toLowerCase().includes(search.toLowerCase()));

    if (!matchesSearch) return false;

    if (activeTab === 'installed') return ext.installed;
    if (activeTab === 'recommended') return !ext.installed;
    return true;
  });

  useEffect(() => {
    fetchExtensions();
  }, []);

  return (
    <div className="h-full flex flex-col bg-[#0d0e15] text-[#c8ccd8] font-sans select-none border-r border-zinc-800">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-800 bg-[#11131c] flex items-center justify-between shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5 font-sans">
          <Puzzle className="w-4 h-4 text-violet-400" />
          Extension Marketplace
        </span>
        <div className="flex items-center gap-1.5">
          <input
            type="file"
            accept=".vsix,.zip"
            ref={fileInputRef}
            onChange={handleVsixUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-violet-300 rounded-lg text-[10.5px] font-medium flex items-center gap-1 cursor-pointer transition-colors"
            title="Install from VSIX / ZIP package"
          >
            <Upload className="w-3 h-3 text-violet-400" /> VSIX
          </button>
          <button
            onClick={fetchExtensions}
            disabled={loading}
            className="p-1 text-zinc-400 hover:text-zinc-200 rounded cursor-pointer transition-colors"
            title="Refresh Marketplace"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Upload Notification */}
      {uploadStatus && (
        <div className="px-3 py-1.5 bg-violet-950/60 border-b border-violet-800/40 text-[10.5px] text-violet-300 font-medium truncate">
          {uploadStatus}
        </div>
      )}

      {/* Category Tabs */}
      <div className="flex border-b border-zinc-800 bg-[#0b0c14] text-[11px] font-semibold px-2 pt-1 gap-1">
        {[
          { id: 'all', label: 'All' },
          { id: 'installed', label: `Installed (${extensions.filter(e => e.installed).length})` },
          { id: 'recommended', label: 'Recommended' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-2.5 py-1.5 rounded-t-lg transition-colors cursor-pointer ${
              activeTab === tab.id
                ? 'bg-[#11131c] text-violet-300 border-t border-x border-zinc-800'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search Input */}
      <div className="p-2.5 border-b border-zinc-800 bg-[#11131c] shrink-0">
        <div className="relative flex items-center bg-zinc-950 border border-zinc-800 hover:border-violet-500/50 rounded-xl px-2.5 py-1.5 gap-2 focus-within:border-violet-500/80">
          <Search className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search extension name, ID, category..."
            className="w-full bg-transparent text-xs text-zinc-100 focus:outline-none placeholder:text-zinc-600 font-sans"
          />
        </div>
      </div>

      {/* Extension List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2.5 scrollbar-none">
        {filteredExtensions.map((ext) => (
          <div
            key={ext.id}
            className={`p-3 bg-zinc-950 border rounded-xl space-y-2 transition-all ${
              ext.installed
                ? ext.enabled !== false
                  ? 'border-violet-500/40 shadow-sm'
                  : 'border-zinc-800 opacity-60'
                : 'border-zinc-800 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold text-zinc-100 truncate">{ext.name}</span>
                  {ext.category && (
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-400 border border-zinc-800">
                      {ext.category}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono mt-0.5">{ext.publisher || 'verified'} • {ext.version}</div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center gap-1 shrink-0">
                <span className="text-[9px] text-emerald-400 font-semibold bg-emerald-950/40 border border-emerald-800/40 px-1.5 py-0.5 rounded-md flex items-center gap-1 font-mono">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" /> Verified
                </span>
              </div>
            </div>

            <p className="text-[11px] text-zinc-400 leading-relaxed font-sans line-clamp-2">
              {ext.description}
            </p>

            {/* Actions Bar */}
            <div className="flex items-center justify-between pt-1 border-t border-zinc-900 select-none">
              <div className="flex items-center gap-1.5">
                {ext.installed && (
                  <button
                    onClick={() => handleToggleEnable(ext)}
                    className={`flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold cursor-pointer transition-colors ${
                      ext.enabled !== false
                        ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800/40'
                        : 'bg-zinc-900 text-zinc-500 border border-zinc-800'
                    }`}
                    title={ext.enabled !== false ? 'Disable extension' : 'Enable extension'}
                  >
                    <Power className="w-3 h-3" />
                    <span>{ext.enabled !== false ? 'Enabled' : 'Disabled'}</span>
                  </button>
                )}
              </div>

              <button
                onClick={() => handleToggleInstall(ext)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer transition-colors shadow-sm ${
                  ext.installed
                    ? 'bg-zinc-900 hover:bg-red-950/60 text-zinc-400 hover:text-red-300 border border-zinc-800 hover:border-red-800/40'
                    : 'bg-violet-600 hover:bg-violet-500 text-white'
                }`}
              >
                {ext.installed ? 'Uninstall' : 'Install'}
              </button>
            </div>
          </div>
        ))}

        {filteredExtensions.length === 0 && (
          <div className="py-10 text-center text-xs text-zinc-500 italic font-sans space-y-2">
            <Puzzle className="w-6 h-6 text-zinc-700 mx-auto" />
            <div>No extensions found matching your search.</div>
          </div>
        )}
      </div>
    </div>
  );
}