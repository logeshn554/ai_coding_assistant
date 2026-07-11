import { useState, useEffect } from 'react';
import { Puzzle, Search } from 'lucide-react';

interface Extension {
  id: string;
  name: string;
  description: string;
  version: string;
  installed: boolean;
}

export default function ExtensionsSidebar() {
  const [search, setSearch] = useState('');
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [loading, setLoading] = useState(false);

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

  useEffect(() => {
    fetchExtensions();
  }, []);

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
          version: ext.version
        })
      });
      if (res.ok) {
        fetchExtensions();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const filteredExtensions = extensions.filter(ext =>
    ext.name.toLowerCase().includes(search.toLowerCase()) ||
    ext.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col bg-[#0e1014] text-gray-300 font-sans select-none">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 bg-[#111318] flex items-center justify-between shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Puzzle className="w-3.5 h-3.5 text-violet-400" />
          Extensions Marketplace
        </span>
        <button
          onClick={fetchExtensions}
          disabled={loading}
          className="text-[10px] text-violet-400 hover:text-violet-300 disabled:opacity-50"
        >
          Refresh
        </button>
      </div>

      {/* Search marketplace */}
      <div className="p-3 border-b border-white/5 bg-[#0e1014] shrink-0">
        <div className="relative flex items-center bg-[#171922] border border-white/5 hover:border-white/10 rounded px-2 py-1 gap-1.5">
          <Search className="w-3.5 h-3.5 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search extensions..."
            className="w-full bg-transparent text-[10px] text-white focus:outline-none"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {filteredExtensions.map((ext) => (
          <div key={ext.id} className="p-2.5 bg-[#161822] border border-white/5 rounded-lg space-y-1.5 transition-all hover:border-violet-500/20">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-200">{ext.name}</span>
              <span className="text-[8px] text-gray-500 font-mono">{ext.version}</span>
            </div>
            <p className="text-[9px] text-gray-400 leading-relaxed">
              {ext.description}
            </p>
            <div className="flex items-center justify-between pt-1">
              <span className="text-[8px] text-violet-400 font-semibold bg-violet-500/10 px-1 py-0.2 rounded">
                Verified
              </span>
              <button
                onClick={() => handleToggleInstall(ext)}
                className={`px-2 py-0.5 rounded text-[9px] font-semibold transition-all ${
                  ext.installed
                    ? 'bg-red-650/15 hover:bg-red-600/20 text-red-400 border border-red-500/10'
                    : 'bg-violet-600 hover:bg-violet-500 text-white'
                }`}
              >
                {ext.installed ? 'Uninstall' : 'Install'}
              </button>
            </div>
          </div>
        ))}
        {filteredExtensions.length === 0 && (
          <div className="py-8 text-center text-xs text-gray-650 italic">
            No extensions match your search
          </div>
        )}
      </div>
    </div>
  );
}
