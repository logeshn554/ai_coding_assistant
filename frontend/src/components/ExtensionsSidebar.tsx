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
    <div className="h-full flex flex-col font-sans select-none border-r border-[var(--dp-border)]" style={{ background: '#1E1F22', color: '#DFE1E5' }}>
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--dp-border)] flex items-center justify-between shrink-0" style={{ background: '#2B2D30' }}>
        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--dp-text-primary)] flex items-center gap-1.5 font-sans">
          <Puzzle className="w-4 h-4 text-[#4C8DFF]" />
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
            className="px-2 py-0.5 text-[10.5px] font-medium flex items-center gap-1 cursor-pointer transition-colors border border-[var(--dp-border)] rounded-[4px]"
            style={{ background: '#2B2D30', color: '#DFE1E5' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#3B3D42'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = '#2B2D30'; }}
            title="Install from VSIX / ZIP package"
          >
            <Upload className="w-3 h-3 text-[#4C8DFF]" /> VSIX
          </button>
          <button
            onClick={fetchExtensions}
            disabled={loading}
            className="p-1 text-[var(--dp-text-secondary)] hover:text-[var(--dp-text-primary)] rounded cursor-pointer transition-colors"
            title="Refresh Marketplace"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Upload Notification */}
      {uploadStatus && (
        <div className="px-3 py-1.5 border-b text-[10.5px] font-medium truncate" style={{ background: 'rgba(76,141,255,0.12)', borderColor: '#393B40', color: '#4C8DFF' }}>
          {uploadStatus}
        </div>
      )}

      {/* Category Tabs */}
      <div className="flex border-b border-[var(--dp-border)] text-[11px] font-semibold px-2 pt-1 gap-1" style={{ background: '#1A1B1E' }}>
        {[
          { id: 'all', label: 'All' },
          { id: 'installed', label: `Installed (${extensions.filter(e => e.installed).length})` },
          { id: 'recommended', label: 'Recommended' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-2.5 py-1.5 transition-colors cursor-pointer border-b-2 ${
              activeTab === tab.id
                ? 'border-[var(--dp-accent)] text-[var(--dp-text-primary)] font-semibold'
                : 'border-transparent text-[var(--dp-text-secondary)] hover:text-[var(--dp-text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search Input */}
      <div className="p-2.5 border-b border-[var(--dp-border)] shrink-0" style={{ background: '#2B2D30' }}>
        <div className="relative flex items-center border border-[var(--dp-border)] rounded-[4px] px-2.5 py-1.5 gap-2" style={{ background: '#1E1F22' }}>
          <Search className="w-3.5 h-3.5 text-[var(--dp-text-muted)] shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search extension name, ID, category..."
            className="w-full bg-transparent text-xs text-[var(--dp-text-primary)] focus:outline-none placeholder-[var(--dp-text-muted)] font-sans"
          />
        </div>
      </div>

      {/* Extension List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2.5 scrollbar-none">
        {filteredExtensions.map((ext) => (
          <div
            key={ext.id}
            className={`p-3 border rounded-[4px] space-y-2 transition-all ${
              ext.installed
                ? ext.enabled !== false
                  ? 'border-[#4C8DFF]/40 shadow-xs'
                  : 'border-[var(--dp-border)] opacity-60'
                : 'border-[var(--dp-border)] hover:border-[var(--dp-border-mid)]'
            }`}
            style={{ background: '#2B2D30' }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold text-[var(--dp-text-primary)] truncate">{ext.name}</span>
                  {ext.category && (
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[var(--dp-border)] text-[var(--dp-text-secondary)]" style={{ background: '#1E1F22' }}>
                      {ext.category}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-[var(--dp-text-secondary)] font-mono mt-0.5">{ext.publisher || 'verified'} • {ext.version}</div>
              </div>

              {/* Status Badge */}
              <div className="flex items-center gap-1 shrink-0">
                <span className="text-[9px] text-[#62D26F] font-semibold bg-[#62D26F]/10 border border-[#62D26F]/20 px-1.5 py-0.5 rounded-[3px] flex items-center gap-1 font-mono">
                  <ShieldCheck className="w-3 h-3 text-[#62D26F]" /> Verified
                </span>
              </div>
            </div>

            <p className="text-[11px] text-[var(--dp-text-secondary)] leading-relaxed font-sans line-clamp-2">
              {ext.description}
            </p>

            {/* Actions Bar */}
            <div className="flex items-center justify-between pt-1 border-t border-[var(--dp-border)] select-none">
              <div className="flex items-center gap-1.5">
                {ext.installed && (
                  <button
                    onClick={() => handleToggleEnable(ext)}
                    className={`flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-semibold cursor-pointer transition-colors ${
                      ext.enabled !== false
                        ? 'bg-[#62D26F]/10 text-[#62D26F] border border-[#62D26F]/20'
                        : 'bg-transparent text-[var(--dp-text-muted)] border border-[var(--dp-border)]'
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
                className={`px-2.5 py-1 rounded-[4px] text-[11px] font-semibold cursor-pointer transition-colors ${
                  ext.installed
                    ? 'bg-transparent hover:bg-[#FF6B6B]/10 text-[var(--dp-text-secondary)] hover:text-[#FF6B6B] border border-[var(--dp-border)] hover:border-[#FF6B6B]/30'
                    : 'bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white'
                }`}
              >
                {ext.installed ? 'Uninstall' : 'Install'}
              </button>
            </div>
          </div>
        ))}

        {filteredExtensions.length === 0 && (
          <div className="py-10 text-center text-xs text-[var(--dp-text-secondary)] italic font-sans space-y-2">
            <Puzzle className="w-6 h-6 text-[var(--dp-text-muted)] mx-auto" />
            <div>No extensions found matching your search.</div>
          </div>
        )}
      </div>
    </div>
  );
}
