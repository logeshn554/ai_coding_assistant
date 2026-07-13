import React, { useEffect } from 'react';
import { Search, Play, Wifi, Circle, MessageSquare } from 'lucide-react';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useEditor } from '../../core/editor/EditorContext';
import { useUI } from '../../core/ui/UIContext';
import { useGit } from '../../core/git/GitContext';
import { useTerminal } from '../../core/terminal/TerminalContext';
import { useAI } from '../../core/ai/AIContext';
import { useCommand } from '../../core/command/CommandContext';

interface MenuItem {
  label: string;
  shortcut?: string;
  action: () => void;
  danger?: boolean;
  dividerAfter?: boolean;
}

const MenuDropdown: React.FC<{ items: MenuItem[]; onClose: () => void }> = ({ items, onClose }) => (
  <div className="absolute left-0 mt-0.5 w-56 bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] shadow-2xl py-1 z-40 text-xs text-gray-300 rounded animate-fade-in">
    {items.map((item, i) => (
      <React.Fragment key={i}>
        <button
          onClick={() => { onClose(); item.action(); }}
          className={`w-full text-left px-4 py-[6px] flex items-center justify-between transition-colors cursor-pointer font-sans
            ${item.danger
              ? 'hover:bg-red-600/15 hover:text-red-400'
              : 'hover:bg-[var(--dp-accent-dim)] hover:text-white'
            }`}
        >
          <span>{item.label}</span>
          {item.shortcut && (
            <span className="text-[10px] text-gray-500 font-mono">{item.shortcut}</span>
          )}
        </button>
        {item.dividerAfter && <div className="border-t border-[var(--dp-border)] my-1" />}
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
  const { handleSendMessage } = useAI();
  const { setIsCommandPaletteOpen } = useCommand();

  const getWorkspaceFolderBasename = () => {
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

  // Close menus on click outside
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
      { label: 'Agents', action: () => { setSidebarTab('agents'); setIsSidebarOpen(true); } },
      { label: 'Workspace Insights', action: () => { setSidebarTab('workspace'); setIsSidebarOpen(true); }, dividerAfter: true },
      { label: 'Terminal', shortcut: 'Ctrl+`', action: () => setBottomTab('terminal') },
      { label: 'Problems', shortcut: 'Ctrl+Shift+M', action: () => setBottomTab('problems') },
      { label: 'Output', action: () => setBottomTab('output') },
    ],
    terminal: [
      { label: 'New Terminal', shortcut: 'Ctrl+Shift+`', action: () => setBottomTab('terminal'), dividerAfter: true },
      { label: statusBarDebug === 'Running' ? 'Stop Running' : 'Start Project', shortcut: 'F5', action: handleStartStopDebug },
    ],
    help: [
      { label: 'Documentation', action: () => window.open('https://github.com', '_blank') },
      { label: 'Welcome Screen', action: () => {
        // Clear active file tab selection to show welcome screen
        window.dispatchEvent(new CustomEvent('show-welcome-screen'));
      }}
    ],
  };

  const renderMenuButton = (id: MenuId, label: string) => (
    <div className="relative font-sans" key={id}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setActiveMenu(activeMenu === id ? null : id);
        }}
        onMouseEnter={() => { if (activeMenu && activeMenu !== id) setActiveMenu(id); }}
        className={`px-2.5 py-1 text-xs transition-colors cursor-pointer hover:bg-white/5 flex items-center gap-1 rounded
          ${activeMenu === id ? 'bg-white/5 text-white' : 'text-gray-400 hover:text-[var(--dp-text-primary)]'}`}
      >
        {label}
      </button>
      {activeMenu === id && menus[id].length > 0 && (
        <MenuDropdown items={menus[id]} onClose={() => setActiveMenu(null)} />
      )}
    </div>
  );

  return (
    <div className="h-[40px] border-b border-[var(--dp-border)] bg-[var(--dp-bg-tertiary)] flex items-center px-3 justify-between shrink-0 select-none z-30 font-sans">
      {/* Left: Logo + Menus */}
      <div className="flex items-center gap-1">
        <span className="text-xs font-semibold text-[var(--dp-text-primary)] flex items-center gap-2 select-none font-sans mr-3">
          <div className="w-5 h-5 rounded-md bg-gradient-to-tr from-[#8B5CF6] to-[#3B82F6] flex items-center justify-center text-[10px] font-black text-white shrink-0 shadow-sm shadow-[#8B5CF6]/20">
            DP
          </div>
          <span className="font-bold tracking-tight">DevPilot</span>
        </span>

        {renderMenuButton('file', 'File')}
        {renderMenuButton('edit', 'Edit')}
        {renderMenuButton('view', 'View')}
        {renderMenuButton('terminal', 'Terminal')}
        {renderMenuButton('help', 'Help')}
      </div>

      {/* Center: Search / Folder Bar */}
      <div 
        onClick={() => setIsCommandPaletteOpen(true)}
        className="flex items-center gap-2 px-3 py-1 bg-black/15 border border-[var(--dp-border)] rounded-lg w-[420px] text-gray-500 hover:text-gray-300 hover:border-white/10 hover:bg-black/25 cursor-pointer text-[11px] font-mono transition-all justify-between"
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-1">
          <Search className="w-3.5 h-3.5 text-gray-500 shrink-0" />
          <span className="truncate text-gray-400 text-left">
            {getWorkspaceFolderBasename()} {activeFilePath ? ` › ${activeFilePath.split('/').pop()}` : ''}
          </span>
        </div>
        <kbd className="px-1.5 py-0.2 bg-white/5 border border-white/10 text-[9px] font-mono text-gray-500 rounded-sm shrink-0 select-none">
          Ctrl+P
        </kbd>
      </div>

      {/* Right: Status Indicators + Window Actions */}
      <div className="flex items-center gap-3">
        {/* Network & Online Status */}
        <div className="flex items-center gap-3 text-[10px] text-gray-500 pr-2 border-r border-white/5">
          <div className="flex items-center gap-1" title="Network Latency to AI router">
            <Wifi className="w-3 h-3 text-emerald-400" />
            <span className="font-mono text-gray-400">4ms</span>
          </div>
          <div className="flex items-center gap-1.5" title="Agent system status: online">
            <Circle className="w-1.5 h-1.5 fill-emerald-500 stroke-none animate-pulse-subtle" />
            <span className="text-gray-400 font-semibold uppercase tracking-wider text-[8px] bg-emerald-500/10 text-emerald-400 px-1 rounded-sm">Connected</span>
          </div>
        </div>

        {/* Start / Stop Debug button */}
        <button
          onClick={handleStartStopDebug}
          className={`p-1.5 hover:bg-white/5 rounded-md transition-colors cursor-pointer flex items-center justify-center
            ${statusBarDebug === 'Running' ? 'text-[var(--dp-success)] bg-emerald-500/10' : 'text-gray-400 hover:text-white'}`}
          title={statusBarDebug === 'Running' ? 'Stop Running' : 'Start Project'}
        >
          <Play className="w-3.5 h-3.5" />
        </button>

        {/* Toggle AI Panel button */}
        <button
          onClick={() => setIsAiPanelOpen(!isAiPanelOpen)}
          className={`p-1.5 hover:bg-white/5 rounded-md transition-colors cursor-pointer flex items-center justify-center
            ${isAiPanelOpen ? 'text-violet-400 bg-violet-500/10' : 'text-gray-400 hover:text-white'}`}
          title={isAiPanelOpen ? 'Hide AI Chat Panel' : 'Show AI Chat Panel'}
        >
          <MessageSquare className="w-3.5 h-3.5" />
        </button>

        {/* Window controls (standard Desktop appearance) */}
        <div className="flex items-center gap-1 ml-1 text-gray-500">
          <button className="w-6 h-6 hover:bg-white/5 flex items-center justify-center rounded-md cursor-pointer transition-colors text-xs">
            —
          </button>
          <button className="w-6 h-6 hover:bg-white/5 flex items-center justify-center rounded-md cursor-pointer transition-colors text-[9px]">
            ⬜
          </button>
          <button className="w-6 h-6 hover:bg-red-500/15 hover:text-red-400 flex items-center justify-center rounded-md cursor-pointer transition-colors text-xs">
            ✕
          </button>
        </div>
      </div>
    </div>
  );
};

