import React from 'react';
import { Folder, Search, Settings, GitBranch, Play, Puzzle, Bot, LayoutGrid, User, FlaskConical } from 'lucide-react';
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
    { id: 'extensions', icon: Puzzle,      label: 'Extensions' },
    { id: 'testing',    icon: FlaskConical,label: 'Testing' },
    { id: 'agents',     icon: Bot,         label: 'AI Agents' },
    { id: 'workspace',  icon: LayoutGrid,  label: 'Workspace' },
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
      className="w-[48px] flex flex-col justify-between py-2 shrink-0 select-none z-10"
      style={{ background: 'var(--dp-bg-tertiary)', borderRight: '1px solid var(--dp-border)' }}
    >
      {/* Top: Nav icons */}
      <div className="flex flex-col items-center gap-0.5 w-full px-1">
        {topTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = isSidebarOpen && sidebarTab === tab.id;

          return (
            <div key={tab.id} className="relative w-full flex justify-center">
              <button
                onClick={() => handleTabClick(tab.id)}
                title={tab.label}
                className={`
                  relative w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-150 cursor-pointer
                  ${isActive
                    ? 'bg-[var(--dp-accent-dim)] text-[var(--dp-accent-hover)] shadow-[0_0_12px_rgba(124,106,240,0.2)]'
                    : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5'
                  }
                `}
              >
                <Icon className="w-[18px] h-[18px]" strokeWidth={isActive ? 2 : 1.75} />

                {/* Active accent left bar */}
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-[var(--dp-accent)] rounded-r-full shadow-[0_0_6px_var(--dp-accent)]" />
                )}

                {/* Badge */}
                {tab.badge != null && tab.badge > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-[14px] flex items-center justify-center rounded-full bg-[var(--dp-accent)] text-white text-[8px] font-bold px-1 leading-none shadow-sm">
                    {tab.badge > 99 ? '99+' : tab.badge}
                  </span>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Bottom: Profile + Settings */}
      <div className="flex flex-col items-center gap-0.5 w-full px-1">
        {/* Profile */}
        <div className="relative w-full flex justify-center">
          <button
            onClick={() => handleTabClick('profile')}
            title="Profile"
            className={`
              w-9 h-9 flex items-center justify-center rounded-xl transition-all duration-150 cursor-pointer
              ${isSidebarOpen && sidebarTab === 'profile'
                ? 'bg-[var(--dp-accent-dim)] text-[var(--dp-accent-hover)]'
                : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5'
              }
            `}
          >
            <User className="w-[18px] h-[18px]" strokeWidth={1.75} />
            {isSidebarOpen && sidebarTab === 'profile' && (
              <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-[var(--dp-accent)] rounded-r-full" />
            )}
          </button>
        </div>

        {/* Settings */}
        <div className="relative w-full flex justify-center">
          <button
            onClick={() => setIsSettingsOpen(true)}
            title="Settings"
            className="w-9 h-9 flex items-center justify-center rounded-xl text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5 transition-all duration-150 cursor-pointer"
          >
            <Settings className="w-[18px] h-[18px]" strokeWidth={1.75} />
          </button>
        </div>

        {/* Avatar pip — opens Profile sidebar */}
        <div
          onClick={() => handleTabClick('profile')}
          className={`mt-1 w-7 h-7 rounded-full flex items-center justify-center text-white text-[9px] font-bold shadow-sm cursor-pointer transition-all duration-150 ${
            isSidebarOpen && sidebarTab === 'profile'
              ? 'bg-gradient-to-br from-violet-400 to-indigo-500 ring-2 ring-violet-400/50 scale-110'
              : 'bg-gradient-to-br from-violet-500 to-indigo-600 hover:scale-110 hover:ring-2 hover:ring-violet-400/40'
          }`}
          title="Profile"
        >
          U
        </div>
      </div>
    </div>
  );
};
