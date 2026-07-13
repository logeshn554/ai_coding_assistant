import React from 'react';
import { Folder, Search, Settings, GitBranch, Play, Puzzle, Bot, LayoutGrid } from 'lucide-react';
import { useUI } from '../../core/ui/UIContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useGit } from '../../core/git/GitContext';

export const ActivityBar: React.FC = () => {
  const { sidebarTab, setSidebarTab, isSidebarOpen, setIsSidebarOpen } = useUI();
  const { setIsSettingsOpen } = useSettings();
  const { gitChangesList } = useGit();

  const topTabs = [
    { id: 'explorer', icon: Folder, label: 'Explorer' },
    { id: 'search', icon: Search, label: 'Search' },
    { id: 'git', icon: GitBranch, label: 'Source Control', badge: gitChangesList?.length || 0 },
    { id: 'debug', icon: Play, label: 'Run & Debug' },
    { id: 'extensions', icon: Puzzle, label: 'Extensions' },
    { id: 'agents', icon: Bot, label: 'Agents' },
    { id: 'workspace', icon: LayoutGrid, label: 'Workspace' }
  ];

  return (
    <div className="w-[56px] bg-[var(--dp-bg-tertiary)] border-r border-[var(--dp-border)] flex flex-col justify-between py-3 shrink-0 select-none z-10">
      {/* Top Icons */}
      <div className="flex flex-col w-full gap-2">
        {topTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = isSidebarOpen && sidebarTab === tab.id;
          return (
            <div key={tab.id} className="relative w-full flex justify-center py-1">
              {/* Active indicator bar */}
              {isActive && (
                <div className="absolute left-0 top-1.5 bottom-1.5 w-[3px] bg-[var(--dp-accent)] rounded-r-md shadow-[0_0_8px_var(--dp-accent)]" />
              )}
              <button
                onClick={() => {
                  if (isSidebarOpen && sidebarTab === tab.id) {
                    setIsSidebarOpen(false);
                  } else {
                    setSidebarTab(tab.id as any);
                    setIsSidebarOpen(true);
                  }
                }}
                className={`relative p-2.5 transition-all duration-150 flex items-center justify-center cursor-pointer rounded-lg hover:bg-white/[0.04]
                  ${isActive
                    ? 'text-white'
                    : 'text-gray-500 hover:text-gray-200'
                  }`}
                title={tab.label}
              >
                <Icon className="w-[20px] h-[20px]" />

                {/* Badge */}
                {tab.badge && tab.badge > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 dp-badge dp-badge-accent text-[8px] min-w-[14px] h-[14px] px-1">
                    {tab.badge > 99 ? '99+' : tab.badge}
                  </span>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Bottom Icons: Profile & Settings */}
      <div className="flex flex-col w-full items-center gap-2">
        {/* Settings */}
        <div className="relative w-full flex justify-center py-1">
          <button
            onClick={() => setIsSettingsOpen(true)}
            className="p-2.5 text-gray-550 hover:text-gray-250 hover:bg-white/[0.04] transition-colors cursor-pointer rounded-lg"
            title="Settings"
          >
            <Settings className="w-[20px] h-[20px]" />
          </button>
        </div>
      </div>
    </div>
  );
};
