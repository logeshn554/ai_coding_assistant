import { useState, useEffect } from 'react';
import { Box, Search, Plus, Trash2, RefreshCw } from 'lucide-react';

interface Dependency {
  name: string;
  version: string;
  type: string;
}

export default function PackagesSidebar() {
  const [manager, setManager] = useState('npm');
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [search, setSearch] = useState('');
  const [newPkg, setNewPkg] = useState('');
  const [loading, setLoading] = useState(false);
  const [installOutput, setInstallOutput] = useState<string | null>(null);

  const loadPackages = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/packages/list');
      const data = await res.json();
      setManager(data.manager || 'npm');
      setDependencies(data.dependencies || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPackages();
  }, []);

  const handleInstall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPkg.trim()) return;
    setLoading(true);
    setInstallOutput(null);
    try {
      const res = await fetch('/api/packages/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newPkg.trim() })
      });
      const data = await res.json();
      if (res.ok) {
        setNewPkg('');
        setInstallOutput(data.output || 'Package installed successfully.');
        loadPackages();
      } else {
        alert('Failed to install package: ' + data.detail);
      }
    } catch (err) {
      alert('Error installing package: ' + err);
    } finally {
      setLoading(false);
    }
  };

  const handleUninstall = async (name: string) => {
    if (!confirm(`Are you sure you want to remove package '${name}'?`)) return;
    setLoading(true);
    setInstallOutput(null);
    try {
      const res = await fetch('/api/packages/uninstall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      const data = await res.json();
      if (res.ok) {
        setInstallOutput(data.output || 'Package removed successfully.');
        loadPackages();
      } else {
        alert('Failed to remove package: ' + data.detail);
      }
    } catch (err) {
      alert('Error removing package: ' + err);
    } finally {
      setLoading(false);
    }
  };

  const filteredDependencies = dependencies.filter(dep =>
    dep.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col bg-[#0e1014] text-gray-300 font-sans select-none">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5 bg-[#111318] flex items-center justify-between shrink-0">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Box className="w-3.5 h-3.5 text-violet-400" />
          Project Dependencies
        </span>
        <span className="text-[8px] uppercase font-bold bg-violet-500/25 text-violet-455 border border-violet-500/20 px-1.5 py-0.2 rounded-full shrink-0">
          {manager}
        </span>
      </div>

      {/* Package installer input */}
      <form onSubmit={handleInstall} className="p-3 border-b border-white/5 bg-[#0e1014] shrink-0 space-y-2">
        <div className="flex gap-2">
          <input
            type="text"
            value={newPkg}
            onChange={(e) => setNewPkg(e.target.value)}
            placeholder={manager === 'npm' ? "lodash, express..." : "requests, pandas..."}
            className="flex-1 bg-[#171922] border border-white/5 hover:border-white/10 rounded px-2.5 py-1 text-[10px] text-white focus:outline-none focus:border-violet-500 transition-all"
          />
          <button
            type="submit"
            disabled={loading || !newPkg.trim()}
            className="py-1 px-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white rounded text-[10px] font-semibold flex items-center gap-1 transition-all"
          >
            {loading ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />} Add
          </button>
        </div>
      </form>

      {/* Filter search bar */}
      <div className="px-3 py-2 border-b border-white/5 bg-[#0e1014] shrink-0">
        <div className="relative flex items-center bg-black/25 border border-white/5 hover:border-white/10 rounded px-2 py-0.5 gap-1.5">
          <Search className="w-3 h-3 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter dependencies..."
            className="w-full bg-transparent text-[9px] text-white focus:outline-none"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-3">
        <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
          Installed Packages ({filteredDependencies.length})
        </div>
        <div className="space-y-1">
          {filteredDependencies.map((dep) => (
            <div key={dep.name} className="flex justify-between items-center p-2 bg-black/15 border border-white/5 rounded transition-all hover:bg-white/5">
              <div className="flex flex-col min-w-0">
                <span className="text-[10px] font-medium text-gray-300 truncate" title={dep.name}>{dep.name}</span>
                <span className="text-[8px] text-gray-550 capitalize">{dep.type} dependency</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[9px] text-gray-450 font-mono font-bold bg-white/5 px-1.5 py-0.2 rounded border border-white/5">
                  {dep.version}
                </span>
                <button
                  onClick={() => handleUninstall(dep.name)}
                  disabled={loading}
                  className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors"
                  title={`Uninstall ${dep.name}`}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
          {filteredDependencies.length === 0 && (
            <div className="py-8 text-center text-xs text-gray-650 italic">
              No packages found
            </div>
          )}
        </div>

        {/* Output console log */}
        {installOutput && (
          <div className="space-y-1.5 pt-2 border-t border-white/5 select-text">
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider select-none">
              Console Output
            </div>
            <pre className="p-2 bg-black/30 border border-white/5 rounded font-mono text-[8px] text-gray-550 whitespace-pre-wrap max-h-32 overflow-y-auto pr-1">
              {installOutput}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
