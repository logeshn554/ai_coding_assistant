import { useEffect, useState } from 'react';
import { Shield, CreditCard, Cloud, LogOut, CheckCircle2, Cpu, Settings, Check } from 'lucide-react';
import { useSettings } from '../core/settings/SettingsContext';

interface ProfileItem {
  id: string;
  name: string;
  model_name: string;
  api_format: string;
}

export default function ProfileSidebar() {
  const { activeProfileName, setIsSettingsOpen, handleSettingsChanged } = useSettings();
  const [profiles, setProfiles] = useState<ProfileItem[]>([]);
  const [activeId, setActiveId] = useState<string>('');

  const loadProfiles = async () => {
    try {
      const res = await fetch('/api/profiles');
      if (res.ok) {
        const data = await res.json();
        setProfiles(data.profiles || []);
        setActiveId(data.active_profile_id || '');
      }
    } catch (e) {
      console.error('Error fetching profiles in ProfileSidebar:', e);
    }
  };

  useEffect(() => {
    loadProfiles();
  }, []);

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

  const stats = [
    { label: 'Developer Plan', val: 'DevPilot Pro' },
    { label: 'Workspace Sync', val: 'Active' },
    { label: 'Active Profile', val: activeProfileName || 'Default' },
    { label: 'Monthly Tokens', val: '412K / 1.5M' },
  ];

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] shrink-0 select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Developer Profile</span>
        <button
          onClick={() => setIsSettingsOpen(true)}
          className="p-1 hover:bg-white/[0.06] rounded text-gray-400 hover:text-white transition-colors cursor-pointer"
          title="Configure Settings"
        >
          <Settings className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* User Card */}
        <div className="p-3 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg flex items-center gap-3 shadow-sm">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#8B5CF6] to-[#3B82F6] flex items-center justify-center text-white text-sm font-bold shadow-md shadow-[#8B5CF6]/15">
            L
          </div>
          <div>
            <h4 className="text-[12px] font-bold text-white leading-none">logeshn554</h4>
            <p className="text-[9px] text-gray-500 mt-1">Lead Software Engineer</p>
          </div>
        </div>

        {/* AI Profiles Switcher */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Connected AI Profiles</h3>
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="text-[9px] text-blue-400 hover:underline cursor-pointer font-semibold"
            >
              Manage
            </button>
          </div>

          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg divide-y divide-[var(--dp-border)] overflow-hidden">
            {profiles.length === 0 ? (
              <div className="p-3 text-center text-xs text-gray-500">
                No AI profiles configured yet.
              </div>
            ) : (
              profiles.map((p) => {
                const isActive = p.id === activeId;
                return (
                  <div
                    key={p.id}
                    onClick={() => handleSwitchActive(p.id)}
                    className={`p-2.5 flex items-center justify-between text-[11px] cursor-pointer transition-colors ${
                      isActive ? 'bg-blue-500/10' : 'hover:bg-white/[0.02]'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Cpu className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-blue-400' : 'text-gray-400'}`} />
                      <div className="truncate">
                        <div className={`font-semibold truncate ${isActive ? 'text-blue-300' : 'text-gray-300'}`}>
                          {p.name}
                        </div>
                        <div className="text-[9px] text-gray-500 truncate font-mono">
                          {p.model_name || p.api_format}
                        </div>
                      </div>
                    </div>
                    {isActive && (
                      <Check className="w-3.5 h-3.5 text-blue-400 shrink-0 ml-2" />
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Plan / Stats */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Subscription & Tokens</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 space-y-2">
            {stats.map((s) => (
              <div key={s.label} className="flex justify-between items-center text-[11px]">
                <span className="text-gray-450">{s.label}</span>
                <span className="text-white font-semibold font-mono">{s.val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Settings */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Integrations</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg divide-y divide-[var(--dp-border)] overflow-hidden">
            <div
              onClick={() => setIsSettingsOpen(true)}
              className="p-2.5 flex items-center justify-between text-[11px] hover:bg-white/[0.02] cursor-pointer transition-colors"
            >
              <span className="flex items-center gap-2 text-gray-400">
                <Shield className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                SSO & Keyring
              </span>
              <span className="text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1 rounded-sm uppercase font-bold">
                Secure
              </span>
            </div>

            <div
              onClick={() => setIsSettingsOpen(true)}
              className="p-2.5 flex items-center justify-between text-[11px] hover:bg-white/[0.02] cursor-pointer transition-colors"
            >
              <span className="flex items-center gap-2 text-gray-400">
                <CreditCard className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Billing Details
              </span>
              <span className="text-gray-500">Manage</span>
            </div>

            <div className="p-2.5 flex items-center justify-between text-[11px] hover:bg-white/[0.02] cursor-pointer transition-colors">
              <span className="flex items-center gap-2 text-gray-400">
                <Cloud className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                Cloud Copilot
              </span>
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                Connected
              </span>
            </div>
          </div>
        </div>

        {/* Action button */}
        <button
          onClick={() => {
            if (confirm("Are you sure you want to sign out?")) {
              window.location.reload();
            }
          }}
          className="w-full py-2 bg-red-500/10 hover:bg-red-500/15 border border-red-500/20 hover:border-red-500/30 text-red-400 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer mt-4"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign Out
        </button>
      </div>
    </div>
  );
}
