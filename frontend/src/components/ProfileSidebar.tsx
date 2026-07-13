import { Shield, CreditCard, Cloud, LogOut, CheckCircle2 } from 'lucide-react';

export default function ProfileSidebar() {
  const stats = [
    { label: 'Developer Plan', val: 'DevPilot Pro' },
    { label: 'Workspace Sync', val: 'Active' },
    { label: 'Monthly Tokens', val: '412K / 1.5M' },
    { label: 'API Queries', val: '1,424' }
  ];

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] shrink-0 select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Developer Profile</span>
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
            <div className="p-2.5 flex items-center justify-between text-[11px] hover:bg-white/[0.02] cursor-pointer transition-colors">
              <span className="flex items-center gap-2 text-gray-400">
                <Shield className="w-3.5 h-3.5 text-[var(--dp-accent)]" />
                SSO & Keyring
              </span>
              <span className="text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1 rounded-sm uppercase font-bold">
                Secure
              </span>
            </div>

            <div className="p-2.5 flex items-center justify-between text-[11px] hover:bg-white/[0.02] cursor-pointer transition-colors">
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
        <button className="w-full py-2 bg-red-500/10 hover:bg-red-500/15 border border-red-500/20 hover:border-red-500/30 text-red-400 rounded-lg text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer mt-4">
          <LogOut className="w-3.5 h-3.5" />
          Sign Out
        </button>
      </div>
    </div>
  );
}
