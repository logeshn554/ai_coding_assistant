import { useEffect, useState } from 'react';
import { Shield, LogOut, Cpu, Settings, Check, Edit3, User } from 'lucide-react';
import { useSettings } from '../core/settings/SettingsContext';

interface ProfileItem {
  id: string;
  name: string;
  model_name: string;
  base_url?: string;
  api_format?: string;
}

export default function ProfileSidebar() {
  const { activeProfileName, setIsSettingsOpen, handleSettingsChanged } = useSettings();
  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [activeId, setActiveId] = useState<string>('');

  // Dynamic user profile info with persistence
  const [userName, setUserName] = useState<string>(() => localStorage.getItem('loopix_user_name') || 'Developer');
  const [userRole, setUserRole] = useState<string>(() => localStorage.getItem('loopix_user_role') || 'Software Engineer');
  const [isEditingProfile, setIsEditingProfile] = useState<boolean>(false);
  const [editName, setEditName] = useState<string>(userName);
  const [editRole, setEditRole] = useState<string>(userRole);

  const loadProfiles = async () => {
    try {
      const res = await fetch('/api/profiles');
      if (res.ok) {
        const data = await res.json();
        const profs = data.profiles || [];
        setProfiles(profs);
        const resolvedId = data.active_profile_id || profs.find((p: any) => p.isActive)?.id || (profs[0]?.id || '');
        setActiveId(resolvedId);
      }
    } catch (e) {
      console.error('Error fetching profiles in ProfileSidebar:', e);
    }
  };

  useEffect(() => {
    loadProfiles();
  }, [activeProfileName]);

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    const finalName = editName.trim() || 'Developer';
    const finalRole = editRole.trim() || 'Software Engineer';
    setUserName(finalName);
    setUserRole(finalRole);
    localStorage.setItem('loopix_user_name', finalName);
    localStorage.setItem('loopix_user_role', finalRole);
    setIsEditingProfile(false);
  };

  const handleSwitchActive = async (id: string) => {
    try {
      const res = await fetch('/api/profiles/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        setActiveId(id);
        handleSettingsChanged();
        loadProfiles();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const userInitial = (userName.charAt(0) || 'D').toUpperCase();

  return (
    <div className="h-full flex flex-col bg-[#11131A] text-zinc-200 select-none font-sans border-r border-[#2A3146]">
      
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[#2A3146] bg-[#161922] shrink-0">
        <div className="flex items-center gap-2">
          <User className="w-4 h-4 text-[#4C8DFF]" />
          <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">Developer Profile</span>
        </div>
        <button
          onClick={() => setIsSettingsOpen(true)}
          className="p-1 hover:bg-white/10 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer"
          title="Configure AI Models & Settings"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        
        {/* User Card */}
        <div className="p-3 bg-[#161922] border border-[#2A3146] rounded-xl shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#8B5CF6] to-[#4C8DFF] flex items-center justify-center text-white text-base font-bold shadow-md shadow-[#4C8DFF]/20 shrink-0">
                {userInitial}
              </div>
              <div className="min-w-0">
                <h4 className="text-xs font-bold text-white truncate leading-snug">{userName}</h4>
                <p className="text-[10px] text-zinc-400 truncate mt-0.5">{userRole}</p>
              </div>
            </div>
            <button
              onClick={() => {
                setEditName(userName);
                setEditRole(userRole);
                setIsEditingProfile(!isEditingProfile);
              }}
              className="p-1.5 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white cursor-pointer transition-colors"
              title="Edit Profile Details"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Inline Edit Form */}
          {isEditingProfile && (
            <form onSubmit={handleSaveProfile} className="pt-2 border-t border-white/10 space-y-2 animate-[fadeIn_150ms_ease-out]">
              <div>
                <label className="text-[9px] uppercase font-bold text-zinc-400">Display Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  placeholder="Your Name..."
                  className="w-full mt-0.5 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-[#4C8DFF]"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-[9px] uppercase font-bold text-zinc-400">Role / Title</label>
                <input
                  type="text"
                  value={editRole}
                  onChange={e => setEditRole(e.target.value)}
                  placeholder="e.g. Fullstack Engineer..."
                  className="w-full mt-0.5 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-zinc-200 focus:outline-none focus:border-[#4C8DFF]"
                />
              </div>
              <div className="flex gap-1.5 pt-1">
                <button
                  type="submit"
                  className="flex-1 py-1 bg-[#4C8DFF] hover:bg-[#6AA3FF] text-white rounded-lg text-[10px] font-bold cursor-pointer"
                >
                  Save Profile
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditingProfile(false)}
                  className="px-2 py-1 bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white rounded-lg text-[10px] cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>

        {/* AI Profiles Switcher */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Connected AI Profiles</h3>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="text-[10px] text-[#4C8DFF] hover:underline cursor-pointer font-semibold"
            >
              Manage
            </button>
          </div>

          <div className="bg-[#141620] border border-[#2A3146] rounded-xl divide-y divide-[#2A3146] overflow-hidden">
            {profiles.length === 0 ? (
              <div className="p-3 text-center text-xs text-zinc-500">
                No AI profiles configured yet. Click Settings to add your LLM API keys.
              </div>
            ) : (
              profiles.map((p) => {
                const isActive = p.id === activeId;
                return (
                  <div
                    key={p.id}
                    onClick={() => handleSwitchActive(p.id)}
                    className={`p-2.5 flex items-center justify-between text-xs cursor-pointer transition-colors ${
                      isActive ? 'bg-[#4C8DFF]/15' : 'hover:bg-white/[0.03]'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Cpu className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-[#4C8DFF]' : 'text-zinc-400'}`} />
                      <div className="truncate">
                        <div className={`font-semibold truncate ${isActive ? 'text-blue-300' : 'text-zinc-300'}`}>
                          {p.name}
                        </div>
                        <div className="text-[9px] text-zinc-500 truncate font-mono">
                          {p.model_name || (p.api_format ? `${p.api_format.toUpperCase()} API` : p.base_url) || 'Custom API'}
                        </div>
                      </div>
                    </div>
                    {isActive && (
                      <Check className="w-3.5 h-3.5 text-[#4C8DFF] shrink-0 ml-2" />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Security & Keyring */}
        <div className="space-y-2">
          <h3 className="text-[10px] font-bold uppercase tracking-wider text-zinc-400">Security & Credentials</h3>
          <div className="bg-[#141620] border border-[#2A3146] rounded-xl overflow-hidden">
            <div
              onClick={() => setIsSettingsOpen(true)}
              className="p-2.5 flex items-center justify-between text-xs hover:bg-white/[0.03] cursor-pointer transition-colors"
            >
              <span className="flex items-center gap-2 text-zinc-300">
                <Shield className="w-3.5 h-3.5 text-[#4C8DFF]" />
                OS Keyring Storage
              </span>
              <span className="text-[9px] bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.2 rounded-full uppercase font-bold">
                Encrypted
              </span>
            </div>
          </div>
        </div>

        {/* Terms & Beta Disclaimer Link */}
        <div className="pt-2 border-t border-[#2A3146]">
          <button
            onClick={() => {
              window.dispatchEvent(new CustomEvent('loopix-open-terms'));
            }}
            className="w-full text-center text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer py-1"
          >
            Terms of Service & Beta Disclaimers
          </button>
        </div>

        {/* Action button */}
        <button
          onClick={() => {
            if (confirm("Are you sure you want to reset the active workspace session?")) {
              window.location.reload();
            }
          }}
          className="w-full py-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 hover:border-red-500/30 text-red-400 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer"
        >
          <LogOut className="w-3.5 h-3.5" />
          Reset Workspace Session
        </button>

      </div>
    </div>
  );
}
