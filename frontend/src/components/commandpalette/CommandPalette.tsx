import React from 'react';
import { Search } from 'lucide-react';
import { useCommand } from '../../core/command/CommandContext';
import { useWorkspace } from '../../core/workspace/WorkspaceContext';
import { useSettings } from '../../core/settings/SettingsContext';
import { useAI } from '../../core/ai/AIContext';
import { useGit } from '../../core/git/GitContext';
import { useUI } from '../../core/ui/UIContext';

export const CommandPalette: React.FC = () => {
  const {
    isCommandPaletteOpen,
    setIsCommandPaletteOpen,
    commandSearch,
    setCommandSearch
  } = useCommand();

  const { handleOpenWorkspaceFolder } = useWorkspace();
  const { setIsSettingsOpen } = useSettings();
  const { setMessages, handleSendMessage } = useAI();
  const { updateStatusBarInfo } = useGit();
  const { setSidebarTab, setIsSidebarOpen } = useUI();

  if (!isCommandPaletteOpen) return null;

  const handleScanForBugs = () => {
    handleSendMessage('Scan the full workspace for bugs and provide a concise bug report.', 'Ask', false);
  };

  const commands = [
    {
      label: 'Go to File…  (Quick Open)',
      shortcut: 'Ctrl+P',
      action: () => {
        setIsCommandPaletteOpen(false);
        // Dispatch a synthetic Ctrl+P — App.tsx intercepts this
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'p', ctrlKey: true, bubbles: true }));
      }
    },
    {
      label: 'Go to Symbol in File…',
      shortcut: 'Ctrl+Shift+O',
      action: () => {
        setIsCommandPaletteOpen(false);
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'o', ctrlKey: true, shiftKey: true, bubbles: true }));
      }
    },
    { label: 'File: Open Workspace Folder', action: () => { setIsCommandPaletteOpen(false); handleOpenWorkspaceFolder(); } },
    { label: 'AI: Configure Model Profile Settings', action: () => { setIsCommandPaletteOpen(false); setIsSettingsOpen(true); } },
    { label: 'AI: Clear Assistant Chat Logs', action: () => { setIsCommandPaletteOpen(false); setMessages([]); } },
    { label: 'Debug: Start Project Execution', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/debug/start', { method: 'POST' }); await updateStatusBarInfo(); } },
    { label: 'Debug: Stop Project Execution', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/debug/stop', { method: 'POST' }); await updateStatusBarInfo(); } },
    { label: 'Git: Pull latest updates', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/git/action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({action:'pull'}) }); } },
    { label: 'Git: Push local commits', action: async () => { setIsCommandPaletteOpen(false); await fetch('/api/git/action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({action:'push'}) }); } },
    { label: 'View: Open File Explorer Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('explorer'); setIsSidebarOpen(true); } },
    { label: 'View: Open Code Search Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('search'); setIsSidebarOpen(true); } },
    { label: 'View: Open Git Control Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('git'); setIsSidebarOpen(true); } },
    { label: 'View: Open Run/Debug Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('debug'); setIsSidebarOpen(true); } },
    { label: 'View: Open Extensions Sidebar', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('extensions'); setIsSidebarOpen(true); } },
    { label: 'View: Open Testing Explorer', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('testing'); setIsSidebarOpen(true); } },
    { label: 'View: Open Dependencies manager', action: () => { setIsCommandPaletteOpen(false); setSidebarTab('packages'); setIsSidebarOpen(true); } },
    { label: 'Tools: Scan for Bugs in Workspace', action: () => { setIsCommandPaletteOpen(false); handleScanForBugs(); } }
  ];


  const filteredCommands = commands.filter(cmd =>
    cmd.label.toLowerCase().includes(commandSearch.toLowerCase())
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[80px]"
      onClick={() => setIsCommandPaletteOpen(false)}
    >
      <div
        className="w-[500px] bg-[#181818] border border-[#2d2d2d] shadow-2xl overflow-hidden rounded-none"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input search */}
        <div className="p-2 bg-[#131313] border-b border-[#2d2d2d] flex items-center gap-2">
          <Search className="w-4 h-4 text-violet-400 shrink-0" />
          <input
            autoFocus
            type="text"
            value={commandSearch}
            onChange={(e) => setCommandSearch(e.target.value)}
            placeholder="Search commands (e.g. Open Folder, Start Debug)..."
            className="w-full bg-transparent text-xs text-white focus:outline-none placeholder:text-gray-655 font-mono"
          />
          <span className="text-[9px] bg-white/5 text-gray-500 px-1.5 py-0.2 rounded font-mono shrink-0">
            ESC to close
          </span>
        </div>

        {/* List */}
        <div className="max-h-72 overflow-y-auto py-1 scrollbar-thin">
          {filteredCommands.map((cmd, idx) => (
            <button
              key={idx}
              onClick={cmd.action}
              className="w-full text-left px-4 py-1.5 hover:bg-[#8b5cf6]/10 hover:text-white transition-colors text-xs text-gray-300 font-mono cursor-pointer font-sans flex items-center justify-between"
            >
              <span>{cmd.label}</span>
              {(cmd as any).shortcut && (
                <span className="text-[9px] bg-white/5 text-gray-500 px-1.5 py-0.5 rounded font-mono shrink-0 ml-3">
                  {(cmd as any).shortcut}
                </span>
              )}
            </button>
          ))}
          {filteredCommands.length === 0 && (
            <div className="px-4 py-3 text-xs text-gray-500 italic font-sans">
              No command matches search.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
