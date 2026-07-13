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

  useEffect(() => {
    fetchExtensions();
  }, []);

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#cccccc] font-sans select-none">
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-[#2d2d2d] bg-[#181818] flex items-center justify-between shrink-0">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Puzzle className="w-3.5 h-3.5 text-violet-400" />
          Extensions Marketplace
        </span>
        <div className="flex gap-2">
          <button
            onClick={fetchExtensions}
            disabled={loading}
            className="text-[10px] text-violet-400 hover:text-violet-300 disabled:opacity-50 cursor-pointer"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Search marketplace */}
      <div className="p-2.5 border-b border-[#2d2d2d] bg-[#131313] shrink-0">
        <div className="relative flex items-center bg-[#1e1e1e] border border-[#2d2d2d] hover:border-[#8b5cf6]/40 rounded-none px-2 py-0.5 gap-1.5">
          <Search className="w-3.5 h-3.5 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search extensions..."
            className="w-full bg-transparent text-[10px] text-white focus:outline-none placeholder:text-gray-655"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {filteredExtensions.map((ext) => (
          <div key={ext.id} className="p-2.5 bg-[#1e1e1e] border border-[#2d2d2d] rounded-none space-y-1.5 hover:border-[#8b5cf6]/40">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-200">{ext.name}</span>
              <span className="text-[8px] text-gray-500 font-mono">{ext.version}</span>
            </div>
            <p className="text-[9px] text-gray-400 leading-relaxed font-sans">
              {ext.description}
            </p>
            <div className="flex items-center justify-between pt-1 select-none">
              <span className="text-[8px] text-[#8b5cf6] font-semibold bg-violet-500/10 border border-violet-500/20 px-1 py-0.2 rounded-none font-mono">
                Verified
              </span>
              <button
                onClick={() => handleToggleInstall(ext)}
                className={`px-2 py-0.5 rounded-none text-[9px] font-semibold cursor-pointer ${
                  ext.installed
                    ? 'bg-red-650/10 hover:bg-red-600/15 text-red-400 border border-red-500/10'
                    : 'bg-[#8b5cf6] hover:bg-[#7c4dff] text-white'
                }`}
              >
                {ext.installed ? 'Uninstall' : 'Install'}
              </button>
            </div>
          </div>
        ))}
        {filteredExtensions.length === 0 && (
          <div className="py-8 text-center text-xs text-gray-550 italic font-sans">
            No extensions match your search
          </div>
        )}
      </div>
    </div>
  );
}