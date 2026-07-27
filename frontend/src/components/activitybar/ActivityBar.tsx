import React from 'react';
import { Folder, Search, Settings, GitBranch, Play, Puzzle, Bot, LayoutGrid, User, FlaskConical, Sparkles, Code } from 'lucide-react';
import { useUI } from '../../core/ui/UIContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useGit } from '../../core/git/GitContext';

export const ActivityBar: React.FC = () => {
  const { sidebarTab, setSidebarTab, isSidebarOpen, setIsSidebarOpen } = useUI();
  const { setIsSettingsOpen } = useSettings();
  const { gitChangesList } = useGit();

  const topTabs = [
    { id: 'explorer',   icon: Folder,      label: 'Explorer' },
    { id: 'search',     icon: Search,      label: 'Search' },
    { id: 'git',        icon: GitBranch,   label: 'Source Control', badge: gitChangesList?.length || 0 },
    { id: 'debug',      icon: Play,        label: 'Run & Debug' },
    { id: 'snippets',   icon: Code,        label: 'Code Snippets' },
    { id: 'artifacts',  icon: Sparkles,    label: 'Artifacts & Plans' },
    { id: 'extensions', icon: Puzzle,      label: 'Extensions' },
    { id: 'testing',    icon: FlaskConical,label: 'Testing' },
    { id: 'agents',     icon: Bot,         label: 'AI Agents' },
    { id: 'workspace',  icon: LayoutGrid,  label: 'Workspace Overview' },
  ];

  const handleTabClick = (tabId: string) => {
    if (isSidebarOpen && sidebarTab === tabId) {
      setIsSidebarOpen(false);
    } else {
      setSidebarTab(tabId as any);
      setIsSidebarOpen(true);
    }
  };

  return (
    <div
      className="w-[52px] flex flex-col justify-between py-3 shrink-0 select-none z-20 font-sans"
      style={{ background: 'var(--dp-bg-tertiary)', borderRight: '1px solid var(--dp-border)' }}
    >
      {/* Top: Nav icons */}
      <div className="flex flex-col items-center gap-1.5 w-full px-1.5">
        {topTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = isSidebarOpen && sidebarTab === tab.id;

          return (
            <div key={tab.id} className="relative w-full flex justify-center group">
              <button
                onClick={() => handleTabClick(tab.id)}
                title={tab.label}
                className={`
                  relative w-10 h-10 flex items-center justify-center rounded-xl transition-all duration-180 cursor-pointer
                  ${isActive
                    ? 'bg-[#7C5CFF]/15 text-[#7C5CFF] shadow-[0_0_16px_rgba(124,92,255,0.35)] ring-1 ring-[#7C5CFF]/30'
                    : 'text-[var(--dp-text-muted)] hover:text-white hover:bg-white/5'
                  }
                `}
              >
                <Icon className="w-4 h-4" strokeWidth={isActive ? 2.2 : 1.8} />

                {/* Rounded active indicator pill on left border */}
                {isActive && (
                  <span className="absolute -left-1.5 top-2.5 bottom-2.5 w-1 bg-[#7C5CFF] rounded-r-full shadow-[0_0_10px_#7C5CFF]" />
                )}

                {/* Badge */}
                {tab.badge != null && tab.badge > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] flex items-center justify-center rounded-full bg-[#7C5CFF] text-white text-[8px] font-extrabold px-1 leading-none shadow-md">
                    {tab.badge > 99 ? '99+' : tab.badge}
                  </span>
                )}
              </button>

              {/* Floating Tooltip */}
              <div className="absolute left-full top-1/2 -translate-y-1/2 ml-2 px-2.5 py-1 bg-[#1A1F2E] text-white text-[11px] font-medium rounded-lg border border-[#2A3146] shadow-xl pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap">
                {tab.label}
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom: Profile + Settings */}
      <div className="flex flex-col items-center gap-1.5 w-full px-1.5">
        {/* Profile button */}
        <div className="relative w-full flex justify-center group">
          <button
            onClick={() => handleTabClick('profile')}
            title="Profile"
            className={`
              w-10 h-10 flex items-center justify-center rounded-xl transition-all duration-180 cursor-pointer
              ${isSidebarOpen && sidebarTab === 'profile'
                ? 'bg-[#7C5CFF]/15 text-[#7C5CFF]'
                : 'text-[var(--dp-text-muted)] hover:text-white hover:bg-white/5'
              }
            `}
          >
            <User className="w-4 h-4" strokeWidth={1.8} />
            {isSidebarOpen && sidebarTab === 'profile' && (
              <span className="absolute -left-1.5 top-2.5 bottom-2.5 w-1 bg-[#7C5CFF] rounded-r-full" />
            )}
          </button>
        </div>

        {/* Settings button */}
        <div className="relative w-full flex justify-center group">
          <button
            onClick={() => setIsSettingsOpen(true)}
            title="Settings"
            className="w-10 h-10 flex items-center justify-center rounded-xl text-[var(--dp-text-muted)] hover:text-white hover:bg-white/5 transition-all duration-180 cursor-pointer"
          >
            <Settings className="w-4 h-4" strokeWidth={1.8} />
          </button>
        </div>

        {/* User avatar pip */}
        <div
          onClick={() => handleTabClick('profile')}
          className={`mt-1 w-7 h-7 rounded-full flex items-center justify-center text-white text-[10px] font-bold shadow-md cursor-pointer transition-all duration-180 ${
            isSidebarOpen && sidebarTab === 'profile'
              ? 'bg-gradient-to-br from-[#7C5CFF] to-indigo-600 ring-2 ring-[#7C5CFF]/50 scale-105'
              : 'bg-gradient-to-br from-purple-600 to-indigo-600 hover:scale-105 hover:ring-2 hover:ring-[#7C5CFF]/40'
          }`}
          title="User Profile"
        >
          U
        </div>
      </div>
    </div>
  );
};
