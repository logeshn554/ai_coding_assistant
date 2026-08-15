import React, { useState, useEffect, useMemo } from 'react';
import { X, Check, Search, Sparkles, Cpu } from 'lucide-react';

export interface ProfileItem {
  id: string;
  name: string;
  base_url?: string;
  api_format?: string;
  model_name?: string;
  is_active?: boolean;
}

interface ProviderSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectModel: (modelName: string, providerId?: string) => void;
  activeModelName?: string;
}

export const ProviderSelectorModal: React.FC<ProviderSelectorModalProps> = ({
  isOpen,
  onClose,
  onSelectModel,
  activeModelName = '',
}) => {
  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchProfiles = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/profiles');
      if (res.ok) {
        const data = await res.json();
        const list: ProfileItem[] = data.profiles || [];
        setProfiles(list);
        const activeId = data.active_id || (list.find((p) => p.is_active)?.id ?? list[0]?.id ?? null);
        setActiveProfileId(activeId);
      }
    } catch (err) {
      console.error('Failed to fetch profiles:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchProfiles();
      setSearchQuery('');
    }
  }, [isOpen]);

  const filteredProfiles = useMemo(() => {
    if (!searchQuery.trim()) return profiles;
    const q = searchQuery.toLowerCase();
    return profiles.filter(
      (p) =>
        (p.model_name && p.model_name.toLowerCase().includes(q)) ||
        (p.name && p.name.toLowerCase().includes(q))
    );
  }, [profiles, searchQuery]);

  const handleSelectModel = (profile: ProfileItem) => {
    const modelToUse = profile.model_name || 'default';
    setActiveProfileId(profile.id);
    onSelectModel(modelToUse, profile.id);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4 animate-[fadeIn_150ms_ease-out]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md bg-[#11131a] border border-white/10 rounded-2xl shadow-2xl overflow-hidden font-sans text-zinc-200 flex flex-col max-h-[80vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/10 bg-[#161922] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <h2 className="font-bold text-sm text-zinc-100">Select Model</h2>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-2.5 border-b border-white/5 bg-[#141620] shrink-0">
          <div className="relative flex items-center">
            <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 bg-black/40 border border-white/10 rounded-lg text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-purple-500 transition-colors font-mono"
              autoFocus
            />
          </div>
        </div>

        {/* Model List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {loading ? (
            <div className="py-10 flex flex-col items-center justify-center text-zinc-500 space-y-2">
              <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs">Loading models...</span>
            </div>
          ) : filteredProfiles.length === 0 ? (
            <div className="py-10 flex flex-col items-center justify-center text-zinc-500 space-y-1">
              <span className="text-xs">No models found</span>
            </div>
          ) : (
            filteredProfiles.map((profile) => {
              const isSelected =
                profile.id === activeProfileId ||
                profile.is_active ||
                profile.model_name === activeModelName;

              return (
                <div
                  key={profile.id}
                  onClick={() => handleSelectModel(profile)}
                  className={`group p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                    isSelected
                      ? 'bg-purple-500/15 border-purple-500/50 shadow-sm shadow-purple-500/10'
                      : 'bg-white/[0.02] hover:bg-white/[0.06] border-white/5 hover:border-white/15'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                        isSelected
                          ? 'bg-purple-600 text-white'
                          : 'bg-white/[0.04] text-zinc-400 group-hover:text-zinc-200'
                      }`}
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="font-mono text-xs font-semibold text-zinc-100 truncate">
                        {profile.model_name || 'default'}
                      </div>
                      <div className="text-[10.5px] text-zinc-400 truncate flex items-center gap-1.5">
                        <span>{profile.name || 'Profile'}</span>
                        {isSelected && (
                          <span className="text-[9px] font-bold px-1 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                            Active
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="shrink-0">
                    {isSelected ? (
                      <div className="w-5 h-5 rounded-full bg-purple-600 flex items-center justify-center text-white">
                        <Check className="w-3 h-3" />
                      </div>
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-white/10 group-hover:border-purple-400/50 flex items-center justify-center text-transparent group-hover:text-purple-400/60 transition-all">
                        <Check className="w-3 h-3" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
