import React, { useEffect, useState } from 'react';
import { Search, Cpu, PanelRight, PanelLeft, GitBranch } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useEditor } from '../../core/editor/EditorContext';
import { useUI } from '../../core/ui/UIContext';
import { useGit } from '../../core/git/GitContext';
import { useTerminal } from '../../core/terminal/TerminalContext';
import { useAI } from '../../core/ai/AIContext';
import { useCommand } from '../../core/command/CommandContext';
import { useSettings } from '../../core/settings/SettingsContext';

import { NotificationBell, NotificationCenter } from '../NotificationCenter';

interface MenuItem {
  label: string;
  shortcut?: string;
  action: () => void;
  danger?: boolean;
  dividerAfter?: boolean;
}

const MenuDropdown: React.FC<{ items: MenuItem[]; onClose: () => void }> = ({ items, onClose }) => (
  <div className="absolute left-0 top-full mt-1 w-56 bg-[var(--dp-bg-elevated)] border border-[var(--dp-border)] shadow-[0_16px_48px_rgba(0,0,0,0.7)] py-1.5 z-50 text-xs text-[var(--dp-text-primary)] rounded-xl animate-fade-in">
    {items.map((item, i) => (
      <React.Fragment key={i}>
        <button
          onClick={() => { onClose(); item.action(); }}
          className={`w-full text-left px-3.5 py-1.5 flex items-center justify-between transition-colors cursor-pointer gap-3 font-sans
            ${item.danger
              ? 'hover:bg-red-500/10 hover:text-red-400'
              : 'hover:bg-[#7C5CFF]/15 hover:text-white'
            }`}
        >
          <span>{item.label}</span>
          {item.shortcut && (
            <span className="text-[9px] text-[var(--dp-text-muted)] font-mono bg-white/5 px-1.5 py-0.5 rounded">{item.shortcut}</span>
          )}
        </button>
        {item.dividerAfter && <div className="border-t border-[var(--dp-border)] my-1 mx-2" />}
      </React.Fragment>
    ))}
  </div>
);

export const TitleBar: React.FC = () => {
  const { workspacePath, handleOpenWorkspaceFolder, changeWorkspacePath, triggerRefresh } = useWorkspace();
  const { activeFilePath } = useEditor();
  const { activeMenu, setActiveMenu, setSidebarTab, isSidebarOpen, setIsSidebarOpen, isAiPanelOpen, setIsAiPanelOpen } = useUI();
  const { statusBarBranch, statusBarDebug } = useGit();
  const { setBottomTab } = useTerminal();
  const { handleSendMessage, contextPercentage = 0, contextTokensRaw = 0 } = useAI();
  const { setIsCommandPaletteOpen } = useCommand();
  const { activeProfileName } = useSettings();


  const [isNotifOpen, setIsNotifOpen] = useState(false);

  const getWorkspaceName = () => {
    if (!workspacePath) return 'No Folder';
    const normalized = workspacePath.replace(/\\/g, '/');
    return normalized.split('/').pop() || 'Workspace';
  };

  const handleStartStopDebug = async () => {
    const storedCmd = localStorage.getItem('devpilot_detected_run_command');
    if (storedCmd) {
      setBottomTab('terminal');
      window.dispatchEvent(new CustomEvent('devpilot-run-terminal-command', { detail: { command: storedCmd } }));
      return;
    }

    setIsAiPanelOpen(true);
    handleSendMessage('run the project', 'Agent', true);
  };

  useEffect(() => {
    if (!activeMenu) return;
    const handler = () => setActiveMenu(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [activeMenu, setActiveMenu]);

  type MenuId = 'file' | 'edit' | 'view' | 'terminal' | 'help';

  const menus: Record<MenuId, MenuItem[]> = {
    file: [
      { label: 'Open Folder...', shortcut: 'Ctrl+O', action: () => handleOpenWorkspaceFolder(), dividerAfter: true },
      { label: 'Refresh File Tree', action: () => triggerRefresh() },
      { label: 'Scan for Bugs', action: () => handleSendMessage('Scan the full workspace for bugs and provide a concise bug report.', 'Ask', false), dividerAfter: true },
      ...(workspacePath ? [{ label: 'Close Folder', action: () => changeWorkspacePath(''), danger: true } as MenuItem] : []),
    ],
    edit: [
      { label: 'Find in Files', shortcut: 'Ctrl+Shift+F', action: () => { setSidebarTab('search'); setIsSidebarOpen(true); }, dividerAfter: true },
      { label: 'Command Palette', shortcut: 'Ctrl+Shift+P', action: () => setIsCommandPaletteOpen(true) },
    ],
    view: [
      { label: 'Explorer', shortcut: 'Ctrl+Shift+E', action: () => { setSidebarTab('explorer'); setIsSidebarOpen(true); } },
      { label: 'Search', shortcut: 'Ctrl+Shift+F', action: () => { setSidebarTab('search'); setIsSidebarOpen(true); } },
      { label: 'Source Control', shortcut: 'Ctrl+Shift+G', action: () => { setSidebarTab('git'); setIsSidebarOpen(true); } },
      { label: 'Run & Debug', shortcut: 'Ctrl+Shift+D', action: () => { setSidebarTab('debug'); setIsSidebarOpen(true); } },
      { label: 'Extensions', shortcut: 'Ctrl+Shift+X', action: () => { setSidebarTab('extensions'); setIsSidebarOpen(true); } },
      { label: 'Developer Profile', shortcut: 'Ctrl+Shift+P', action: () => { setSidebarTab('profile'); setIsSidebarOpen(true); }, dividerAfter: true },
      { label: 'Terminal', shortcut: 'Ctrl+`', action: () => setBottomTab('terminal') },
      { label: 'Problems', shortcut: 'Ctrl+Shift+M', action: () => setBottomTab('problems') },
    ],
    terminal: [
      { label: 'New Terminal', shortcut: 'Ctrl+Shift+`', action: () => setBottomTab('terminal'), dividerAfter: true },
      { label: statusBarDebug === 'Running' ? 'Stop Running' : 'Start Project', shortcut: 'F5', action: handleStartStopDebug },
    ],
    help: [
      { label: 'Documentation', action: () => window.open('https://github.com', '_blank') },
      { label: 'Welcome Screen', action: () => window.dispatchEvent(new CustomEvent('show-welcome-screen')) },
    ],
  };

  const renderMenu = (id: MenuId, label: string) => (
    <div key={id} className="relative">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu === id ? null : id); }}
        className={`px-2 py-1 rounded text-[11.5px] font-medium transition-colors cursor-pointer ${
          activeMenu === id
            ? 'bg-white/10 text-white font-semibold'
            : 'text-[var(--dp-text-secondary)] hover:text-white hover:bg-white/5'
        }`}
      >
        {label}
      </button>
      {activeMenu === id && menus[id].length > 0 && (
        <MenuDropdown items={menus[id]} onClose={() => setActiveMenu(null)} />
      )}
    </div>
  );

  const formatTokens = (num: number) => {
    if (!num) return '0K';
    if (num < 1000) return `${num}`;
    return `${(num / 1000).toFixed(0)}K`;
  };

  return (
    <div className="h-10 bg-[var(--dp-bg-tertiary)] border-b border-[var(--dp-border)] flex items-center justify-between px-3 select-none shrink-0 z-30 font-sans">

      {/* ── Left: Branding + Workspace Selector + Menus ── */}
      <div className="flex items-center gap-2.5">
        {/* DevPilot Logo */}
        <div className="w-5 h-5 rounded-md bg-gradient-to-tr from-[#7C5CFF] via-purple-600 to-indigo-500 flex items-center justify-center text-white text-[10px] font-extrabold shadow-md shadow-[#7C5CFF]/30 shrink-0 tracking-tighter">
          DP
        </div>
        <span className="text-[12px] font-bold text-[var(--dp-text-bright)] tracking-tight">DevPilot</span>

        {/* Workspace Selector Dropdown Badge */}
        <div
          onClick={handleOpenWorkspaceFolder}
          className="flex items-center gap-1.5 px-2 py-0.5 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] hover:border-[#7C5CFF]/40 rounded-lg text-[11px] text-[var(--dp-text-primary)] cursor-pointer transition-colors"
          title="Switch Workspace Folder"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#7C5CFF]" />
          <span className="font-semibold truncate max-w-[120px] text-[var(--dp-text-primary)]">{getWorkspaceName()}</span>
        </div>

        {/* Top Menus */}
        <div className="flex items-center gap-0.5 ml-1">
          {renderMenu('file', 'File')}
          {renderMenu('edit', 'Edit')}
          {renderMenu('view', 'View')}
          {renderMenu('terminal', 'Terminal')}
          {renderMenu('help', 'Help')}
        </div>
      </div>

      {/* ── Center: Universal Search Trigger ── */}
      <div
        onClick={() => setIsCommandPaletteOpen(true)}
        className="flex items-center justify-between w-80 max-w-sm h-6.5 px-2.5 bg-[var(--dp-bg-secondary)] hover:bg-[var(--dp-bg-elevated)] border border-[var(--dp-border)] hover:border-[#7C5CFF]/40 rounded-lg text-xs text-[var(--dp-text-muted)] cursor-pointer transition-all duration-150 group shadow-sm"
      >
        <div className="flex items-center gap-2 truncate">
          <Search className="w-3.5 h-3.5 text-[var(--dp-text-muted)] group-hover:text-[#7C5CFF] transition-colors shrink-0" />
          <span className="truncate text-[11px] text-[var(--dp-text-secondary)]">
            {activeFilePath
              ? `${getWorkspaceName()} › ${activeFilePath.replace(/\\/g, '/').split('/').pop()}`
              : 'Search files, commands, symbols...'
            }
          </span>
        </div>
        <kbd className="px-1.5 py-0.5 bg-[var(--dp-bg-elevated)] border border-[var(--dp-border)] text-[9px] font-mono text-[var(--dp-text-muted)] rounded shrink-0">
          Ctrl K
        </kbd>
      </div>

      {/* ── Right: AI Model + Context Bar + Status Controls ── */}
      <div className="flex items-center gap-2 shrink-0">

        {/* Git Branch Badge */}
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] text-[10px] text-[var(--dp-text-secondary)] font-mono">
          <GitBranch className="w-3 h-3 text-[#7C5CFF]" />
          <span className="font-semibold text-[var(--dp-text-bright)]">{statusBarBranch || 'main'}</span>
        </div>

        {/* Active AI Model Badge */}
        <div
          onClick={() => {
            setSidebarTab('profile');
            setIsSidebarOpen(true);
          }}
          title="Click to switch AI Profile & Models"
          className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg bg-[#7C5CFF]/15 border border-[#7C5CFF]/30 text-[11px] cursor-pointer hover:bg-[#7C5CFF]/25 transition-all shadow-[0_0_10px_rgba(124,92,255,0.15)]"
        >
          <Cpu className="w-3.5 h-3.5 text-[#7C5CFF]" />
          <span className="font-bold text-[var(--dp-text-bright)]">{activeProfileName || 'Groq / Claude 3.5'}</span>
        </div>

        {/* Context Progress Bar */}
        <div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-lg bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] text-[10px] font-mono text-[var(--dp-text-secondary)]"
          title={`Context Token Usage: ${formatTokens(contextTokensRaw)} / 128K (${contextPercentage}%)`}
        >
          <span>{formatTokens(contextTokensRaw)} / 128K</span>
          <div className="w-12 h-1.5 bg-[var(--dp-bg-tertiary)] rounded-full overflow-hidden border border-[var(--dp-border)]">
            <div
              className="h-full bg-gradient-to-r from-[#7C5CFF] to-blue-500 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, Math.max(5, contextPercentage || 5))}%` }}
            />
          </div>
        </div>



        {/* Notifications Bell */}
        <div className="relative">
          <NotificationBell
            onClick={() => setIsNotifOpen((v) => !v)}
            isOpen={isNotifOpen}
          />
          <NotificationCenter
            isOpen={isNotifOpen}
            onClose={() => setIsNotifOpen(false)}
          />
        </div>

        {/* Primary Sidebar Toggle */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={`p-1.5 hover:bg-white/5 rounded-lg transition-colors cursor-pointer
            ${isSidebarOpen ? 'text-white bg-white/10' : 'text-[var(--dp-text-muted)] hover:text-white'}`}
          title={isSidebarOpen ? 'Hide Primary Sidebar' : 'Show Primary Sidebar'}
        >
          <PanelLeft className="w-3.5 h-3.5" />
        </button>

        {/* AI Workspace Panel Toggle */}
        <button
          onClick={() => setIsAiPanelOpen(!isAiPanelOpen)}
          className={`p-1.5 rounded-lg transition-colors cursor-pointer
            ${isAiPanelOpen ? 'text-[#7C5CFF] bg-[#7C5CFF]/15 border border-[#7C5CFF]/30' : 'text-[var(--dp-text-muted)] hover:text-white hover:bg-white/5'}`}
          title={isAiPanelOpen ? 'Hide AI Workspace' : 'Show AI Workspace'}
        >
          <PanelRight className="w-3.5 h-3.5" />
        </button>

        {/* User avatar */}
        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#7C5CFF] to-indigo-600 flex items-center justify-center text-white text-[9px] font-bold shadow-md cursor-pointer shrink-0">
          U
        </div>
      </div>
    </div>
  );
};
