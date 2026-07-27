import React, { useState, useEffect } from 'react';
import { Code, Plus, Copy, Check, Trash2, Search } from 'lucide-react';

interface Snippet {
  id: string;
  title: string;
  language: string;
  code: string;
  description?: string;
}

export default function SnippetsSidebar() {
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  const [filterText, setFilterText] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const [newTitle, setNewTitle] = useState('');
  const [newLang, setNewLang] = useState('python');
  const [newCode, setNewCode] = useState('');
  const [newDesc, setNewDesc] = useState('');

  const fetchSnippets = async () => {
    try {
      const res = await fetch('/api/snippets');
      const data = await res.json();
      setSnippets(data.snippets || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchSnippets();
  }, []);

  const handleCopy = (snip: Snippet) => {
    navigator.clipboard.writeText(snip.code);
    setCopiedId(snip.id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`/api/snippets/${id}`, { method: 'DELETE' });
      fetchSnippets();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddSnippet = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newCode.trim()) return;

    const item: Snippet = {
      id: `snip_${Date.now()}`,
      title: newTitle.trim(),
      language: newLang.trim().toLowerCase(),
      code: newCode.trim(),
      description: newDesc.trim()
    };

    try {
      await fetch('/api/snippets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item)
      });
      setNewTitle('');
      setNewCode('');
      setNewDesc('');
      setShowAddForm(false);
      fetchSnippets();
    } catch (e) {
      console.error(e);
    }
  };

  const filtered = snippets.filter(
    s =>
      s.title.toLowerCase().includes(filterText.toLowerCase()) ||
      s.language.toLowerCase().includes(filterText.toLowerCase()) ||
      s.code.toLowerCase().includes(filterText.toLowerCase())
  );

  return (
    <div className="h-full flex flex-col bg-[#0f1017] text-[#c8ccd8] font-sans select-none border-r border-zinc-800">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-800 bg-[#13141f] flex items-center justify-between shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5 font-sans">
          <Code className="w-4 h-4 text-violet-400" />
          Code Snippets
        </span>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="p-1 hover:bg-zinc-800 text-violet-400 hover:text-violet-300 rounded transition-colors"
          title="Add New Snippet"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {/* Filter Bar */}
      <div className="p-2 border-b border-zinc-800 bg-[#11121a] shrink-0">
        <div className="relative flex items-center">
          <Search className="w-3.5 h-3.5 absolute left-2.5 text-zinc-500" />
          <input
            type="text"
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
            placeholder="Search snippets..."
            className="w-full pl-8 pr-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-200 focus:outline-none focus:border-violet-500"
          />
        </div>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <form onSubmit={handleAddSnippet} className="p-3 border-b border-zinc-800 bg-zinc-900/90 space-y-2 shrink-0 text-xs">
          <input
            type="text"
            placeholder="Snippet Title"
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            className="w-full px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg font-sans text-zinc-200 focus:outline-none focus:border-violet-500"
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Language (e.g. python, ts)"
              value={newLang}
              onChange={e => setNewLang(e.target.value)}
              className="flex-1 px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg font-mono text-zinc-200 focus:outline-none focus:border-violet-500"
            />
            <input
              type="text"
              placeholder="Description"
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              className="flex-1 px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg font-sans text-zinc-200 focus:outline-none focus:border-violet-500"
            />
          </div>
          <textarea
            placeholder="Code content..."
            value={newCode}
            onChange={e => setNewCode(e.target.value)}
            rows={3}
            className="w-full px-2.5 py-1 bg-zinc-950 border border-zinc-800 rounded-lg font-mono text-zinc-200 focus:outline-none focus:border-violet-500 resize-none"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3 py-1 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-lg text-xs"
            >
              Save Snippet
            </button>
          </div>
        </form>
      )}

      {/* Snippets Feed */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 font-sans scrollbar-none">
        {filtered.length === 0 ? (
          <div className="p-4 text-center text-xs text-zinc-500 italic">No code snippets found.</div>
        ) : (
          filtered.map(snip => (
            <div key={snip.id} className="p-3 bg-zinc-950 border border-zinc-800 rounded-xl space-y-2 group shadow-inner">
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-zinc-200 truncate max-w-[160px]">{snip.title}</span>
                <span className="px-1.5 py-0.5 bg-violet-950/60 text-violet-400 border border-violet-800/40 rounded text-[9.5px] font-mono uppercase font-semibold">
                  {snip.language}
                </span>
              </div>
              {snip.description && <div className="text-[10.5px] text-zinc-400">{snip.description}</div>}
              <pre className="p-2 bg-zinc-900 rounded-lg font-mono text-[10px] text-zinc-300 overflow-x-auto max-h-32 scrollbar-none leading-relaxed select-text">
                {snip.code}
              </pre>
              <div className="flex items-center justify-end gap-1.5 pt-1">
                <button
                  onClick={() => handleCopy(snip)}
                  className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white rounded-lg text-[10.5px] font-semibold flex items-center gap-1 cursor-pointer transition-colors"
                >
                  {copiedId === snip.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedId === snip.id ? 'Copied' : 'Copy'}</span>
                </button>
                <button
                  onClick={() => handleDelete(snip.id)}
                  className="p-1 hover:bg-red-950/50 text-zinc-500 hover:text-red-400 rounded-lg transition-colors cursor-pointer"
                  title="Delete snippet"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
