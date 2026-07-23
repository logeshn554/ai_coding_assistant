import React, { useEffect, useState } from 'react';
import { Search, Play, Cpu, Zap, MessageSquare } from 'lucide-react';
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
  <div className="absolute left-0 top-full mt-0.5 w-52 bg-[var(--dp-bg-elevated)] border border-[var(--dp-border-mid)] shadow-[var(--dp-shadow-float)] py-1.5 z-50 text-xs text-[var(--dp-text-primary)] rounded-xl animate-fade-in">
    {items.map((item, i) => (
      <React.Fragment key={i}>
        <button
          onClick={() => { onClose(); item.action(); }}
          className={`w-full text-left px-3.5 py-1.5 flex items-center justify-between transition-colors cursor-pointer gap-3 font-sans rounded-none
            ${item.danger
              ? 'hover:bg-red-500/10 hover:text-red-400'
              : 'hover:bg-[var(--dp-bg-active)] hover:text-[var(--dp-text-bright)]'
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
  const { activeMenu, setActiveMenu, setSidebarTab, setIsSidebarOpen, isAiPanelOpen, setIsAiPanelOpen } = useUI();
  const { statusBarDebug, updateStatusBarInfo } = useGit();
  const { setBottomTab } = useTerminal();
  const { handleSendMessage, isGenerating, isWsConnected } = useAI();
  const { setIsCommandPaletteOpen } = useCommand();
  const { activeProfileName } = useSettings();

  const [latency] = useState(4);
  const [isNotifOpen, setIsNotifOpen] = useState(false);

  const getWorkspaceName = () => {
    if (!workspacePath) return 'DevPilot';
    const normalized = workspacePath.replace(/\\/g, '/');
    return normalized.split('/').pop() || 'DevPilot';
  };

  const handleStartStopDebug = async () => {
    const method = statusBarDebug === 'Running' ? 'stop' : 'start';
    await fetch(`/api/debug/${method}`, { method: 'POST' });
    await updateStatusBarInfo();
    setBottomTab('output');
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
    <div className="relative" key={id}>
      <button
        onClick={(e) => { e.stopPropagation(); setActiveMenu(activeMenu === id ? null : id); }}
        onMouseEnter={() => { if (activeMenu && activeMenu !== id) setActiveMenu(id); }}
        className={`px-2.5 py-1 text-[11px] transition-colors cursor-pointer rounded-md font-sans
          ${activeMenu === id
            ? 'bg-white/6 text-[var(--dp-text-bright)]'
            : 'text-[var(--dp-text-secondary)] hover:text-[var(--dp-text-primary)] hover:bg-white/4'
          }`}
      >
        {label}
      </button>
      {activeMenu === id && menus[id].length > 0 && (
        <MenuDropdown items={menus[id]} onClose={() => setActiveMenu(null)} />
      )}
    </div>
  );

  return (
    <div className="h-9 bg-[var(--dp-bg-secondary)] border-b border-[var(--dp-border)] flex items-center justify-between px-3 select-none shrink-0 z-30 font-sans">

      {/* ── Left: Branding + Menus ── */}
      <div className="flex items-center gap-2">
        {/* DevPilot Logo Icon */}
        <div className="w-5 h-5 rounded-md bg-gradient-to-tr from-[#7C6AF0] to-[#50E3C2] flex items-center justify-center text-white text-[10px] font-bold shadow-sm shadow-[#7C6AF0]/30 shrink-0">
          DP
        </div>

        {/* Menu Items */}
        <div className="flex items-center gap-0.5 ml-1">
          {renderMenu('file', 'File')}
          {renderMenu('edit', 'Edit')}
          {renderMenu('view', 'View')}
          {renderMenu('terminal', 'Terminal')}
          {renderMenu('help', 'Help')}
        </div>
      </div>

      {/* ── Center: Search / Command Trigger Bar ── */}
      <div
        onClick={() => setIsCommandPaletteOpen(true)}
        className="flex items-center justify-between w-96 max-w-md h-6 px-2.5 bg-[var(--dp-bg-tertiary)] hover:bg-white/[0.06] border border-[var(--dp-border)] rounded-md text-xs text-[var(--dp-text-muted)] cursor-pointer transition-colors"
      >
        <div className="flex items-center gap-2 truncate">
          <Search className="w-3.5 h-3.5 text-[var(--dp-text-muted)] shrink-0" />
          <span className="truncate text-[11px]">
            {activeFilePath
              ? `${getWorkspaceName()} › ${activeFilePath.replace(/\\/g, '/').split('/').pop()}`
              : 'Search files, symbols, commands...'
            }
          </span>
        </div>
        <kbd className="px-1.5 py-0.5 bg-white/5 border border-white/8 text-[9px] font-mono text-[var(--dp-text-muted)] rounded shrink-0">
          Ctrl K
        </kbd>
      </div>

      {/* ── Right: Status + Controls ── */}
      <div className="flex items-center gap-2 shrink-0">

        {/* Model badge */}
        <div
          onClick={() => {
            setSidebarTab('profile');
            setIsSidebarOpen(true);
          }}
          title="Click to view & switch AI Profile"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--dp-accent-dim)] border border-[var(--dp-accent)]/20 text-[11px] cursor-pointer hover:bg-[var(--dp-accent-dim)]/80 transition-colors"
        >
          <Cpu className="w-3 h-3 text-[var(--dp-accent)]" />
          <span className="font-semibold text-[var(--dp-accent)]">{activeProfileName || 'GPT-5.5'}</span>
        </div>

        {/* Context tokens */}
        <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-white/4 border border-[var(--dp-border)] text-[10px] font-mono text-[var(--dp-text-secondary)] cursor-default">
          <span>128K</span>
          <span className="text-[var(--dp-text-muted)]">Context</span>
        </div>

        {/* Latency */}
        <div className="flex items-center gap-1 text-[10px] text-[var(--dp-text-muted)]" title="Network latency">
          <div className="w-2 h-2 rounded-full bg-[var(--dp-success)] animate-status-pulse" />
          <span className="font-mono">{latency}ms</span>
        </div>

        {/* WS connected / AI generating */}
        {isGenerating ? (
          <div className="flex items-center gap-1 text-[var(--dp-accent)] animate-pulse-subtle">
            <Zap className="w-3.5 h-3.5" />
          </div>
        ) : (
          !isWsConnected && (
            <div className="w-2 h-2 rounded-full bg-[var(--dp-error)] animate-pulse" title="Disconnected" />
          )
        )}

        {/* Bell + Notification Center */}
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

        {/* Play / Stop */}
        <button
          onClick={handleStartStopDebug}
          className={`p-1.5 hover:bg-white/5 rounded-md transition-colors cursor-pointer
            ${statusBarDebug === 'Running' ? 'text-[var(--dp-success)]' : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)]'}`}
          title={statusBarDebug === 'Running' ? 'Stop Running' : 'Start Project'}
        >
          <Play className="w-3.5 h-3.5" />
        </button>

        {/* AI Panel toggle */}
        <button
          onClick={() => setIsAiPanelOpen(!isAiPanelOpen)}
          className={`p-1.5 hover:bg-white/5 rounded-md transition-colors cursor-pointer
            ${isAiPanelOpen ? 'text-[var(--dp-accent)] bg-[var(--dp-accent-dim)]' : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)]'}`}
          title={isAiPanelOpen ? 'Hide AI Panel' : 'Show AI Panel'}
        >
          <MessageSquare className="w-3.5 h-3.5" />
        </button>

        {/* User avatar */}
        <div className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-[9px] font-bold shadow-sm cursor-pointer shrink-0">
          U
        </div>
      </div>
    </div>
  );
};
