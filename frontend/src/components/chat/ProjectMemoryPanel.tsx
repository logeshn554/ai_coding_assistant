import React, { useState } from 'react';
import { Brain, Plus, Trash2, ToggleLeft, ToggleRight, Sparkles } from 'lucide-react';
import type { ProjectMemoryItem } from '../../types/chat';

interface ProjectMemoryPanelProps {
  memories: ProjectMemoryItem[];
  onAddMemory: (item: Omit<ProjectMemoryItem, 'id'>) => void;
  onToggleMemory: (id: string) => void;
  onDeleteMemory: (id: string) => void;
}

export const ProjectMemoryPanel: React.FC<ProjectMemoryPanelProps> = ({
  memories,
  onAddMemory,
  onToggleMemory,
  onDeleteMemory
}) => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [category, setCategory] = useState<ProjectMemoryItem['category']>('convention');

  const handleCreate = () => {
    if (!title.trim() || !content.trim()) return;
    onAddMemory({
      category,
      title: title.trim(),
      content: content.trim(),
      enabled: true
    });
    setTitle('');
    setContent('');
    setShowAddModal(false);
  };

  return (
    <div className="bg-[#12141c] border border-white/10 rounded-xl p-3 text-xs space-y-3 shadow-md">
      <div className="flex items-center justify-between pb-2 border-b border-white/5">
        <div>
          <h4 className="font-bold text-white text-xs flex items-center gap-1.5">
            <Brain className="w-4 h-4 text-purple-400" /> Persistent Project Memory
          </h4>
          <p className="text-[10px] text-gray-400">Rules & architectural guidelines enforced on every AI turn</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1 bg-violet-600 hover:bg-violet-500 text-white px-2.5 py-1 rounded-lg font-semibold text-[10px] shadow-sm transition-all cursor-pointer"
        >
          <Plus className="w-3 h-3" /> Add Rule
        </button>
      </div>

      {/* Memory Items List */}
      <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
        {memories.length === 0 ? (
          <div className="text-center py-6 text-gray-500 text-[11px] border border-dashed border-white/5 rounded-lg">
            No persistent rules configured. Click "Add Rule" to teach AI project preferences.
          </div>
        ) : (
          memories.map((item) => (
            <div 
              key={item.id}
              className={`p-2.5 border rounded-lg transition-all ${
                item.enabled 
                  ? 'bg-black/30 border-white/10 text-gray-200' 
                  : 'bg-black/10 border-white/5 text-gray-500 opacity-60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 shrink-0">
                    {item.category}
                  </span>
                  <span className="font-semibold text-white truncate text-[11px]">{item.title}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button 
                    onClick={() => onToggleMemory(item.id)}
                    className="text-gray-400 hover:text-white transition-colors"
                    title={item.enabled ? 'Disable rule' : 'Enable rule'}
                  >
                    {item.enabled ? <ToggleRight className="w-4 h-4 text-emerald-400" /> : <ToggleLeft className="w-4 h-4 text-gray-600" />}
                  </button>
                  <button 
                    onClick={() => onDeleteMemory(item.id)}
                    className="text-gray-500 hover:text-rose-400 transition-colors p-0.5"
                    title="Delete rule"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <p className="text-[10px] text-gray-400 mt-1 line-clamp-2 leading-relaxed font-mono">
                {item.content}
              </p>
            </div>
          ))
        )}
      </div>

      {/* Add Memory Modal Overlay */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#181b26] border border-white/10 rounded-xl w-[400px] p-4 shadow-2xl space-y-3 font-sans">
            <h3 className="font-bold text-white text-sm flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-violet-400" /> Add Persistent Memory Rule
            </h3>
            
            <div className="space-y-2">
              <div>
                <label className="text-[10px] font-semibold text-gray-400 block mb-1">Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value as any)}
                  className="w-full bg-[#10121a] border border-white/10 rounded-lg p-2 text-xs text-white"
                >
                  <option value="convention">Coding Convention</option>
                  <option value="architecture">Architecture Rule</option>
                  <option value="preference">User Preference</option>
                  <option value="instruction">Saved Instruction</option>
                  <option value="ignored">Ignored Folders/Patterns</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-semibold text-gray-400 block mb-1">Rule Title</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Use Tailwind CSS with 8px spacing"
                  className="w-full bg-[#10121a] border border-white/10 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-semibold text-gray-400 block mb-1">Instruction Details</label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder="Exact prompt instruction to inject on every task turn..."
                  rows={3}
                  className="w-full bg-[#10121a] border border-white/10 rounded-lg p-2 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-3 py-1.5 text-xs text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!title.trim() || !content.trim()}
                className="px-3 py-1.5 text-xs font-semibold bg-violet-600 hover:bg-violet-500 text-white rounded-lg disabled:opacity-40 transition-colors"
              >
                Save Rule
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
