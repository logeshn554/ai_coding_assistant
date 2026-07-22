import { useRef, useState } from 'react';
import { CoreProvider } from './core/CoreProvider';
import { useWorkspace } from './core/workspace/WorkspaceContext';
import { useEditor } from './core/editor/EditorContext';
import { useUI } from './core/ui/UIContext';
import { useGit } from './core/git/GitContext';
import { useAI } from './core/ai/AIContext';
import { useSettings } from './core/settings/SettingsContext';
import { useToast } from './core/toast/ToastContext';
import { LSPProvider } from './core/lsp/LSPContext';

// Import subpanels
import { TitleBar } from './components/titlebar/TitleBar';
import { ActivityBar } from './components/activitybar/ActivityBar';
import { BottomPanel } from './components/bottompanel/BottomPanel';
import { StatusBar } from './components/statusbar/StatusBar';
import { CommandPalette } from './components/commandpalette/CommandPalette';
import Sidebar from './components/Sidebar';
import SearchSidebar from './components/SearchSidebar';
import GitSidebar from './components/GitSidebar';
import RunDebugSidebar from './components/RunDebugSidebar';
import ExtensionsSidebar from './components/ExtensionsSidebar';
import TestingSidebar from './components/TestingSidebar';
import PackagesSidebar from './components/PackagesSidebar';
import AgentsSidebar from './components/AgentsSidebar';
import WorkspaceSidebar from './components/WorkspaceSidebar';
import ProfileSidebar from './components/ProfileSidebar';
import EditorArea from './components/EditorArea';
import { AiWorkspace } from './components/chat/AiWorkspace';
import SettingsModal from './components/SettingsModal';
import QuickOpen from './components/QuickOpen';
import GoToSymbol from './components/GoToSymbol';

// Custom Hooks and standalone components
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useResizeManager } from './hooks/useResizeManager';

function EditorShell() {
  const [chatInputText, setChatInputText] = useState('');
  const [chatMode, setChatMode] = useState<'Ask' | 'Plan' | 'Agent'>('Agent');
  const { toasts, removeToast } = useToast();

  const {
    isQuickOpenOpen,
    setIsQuickOpenOpen,
    isGoToSymbolOpen,
    setIsGoToSymbolOpen
  } = useKeyboardShortcuts();

  const {
    terminalHeight,
    sidebarWidth,
    aiPanelWidth,
    setIsResizingSidebar,
    setIsResizingTerminal,
    setIsResizingAiPanel
  } = useResizeManager();

  // Live Monaco editor instance forwarded from EditorArea
  const editorInstanceRef = useRef<any>(null);

  // Reveal a line in Monaco when Go to Symbol selects a result
  const handleRevealLine = (line: number, col: number = 1) => {
    const editor = editorInstanceRef.current;
    if (!editor) return;
    try {
      editor.revealLineInCenter(line);
      editor.setPosition({ lineNumber: line, column: col });
      editor.focus();
    } catch {}
  };
  const {
    workspacePath,
    handleOpenWorkspaceFolder,
    refreshTrigger
  } = useWorkspace();

  const {
    openFiles,
    activeFilePath,
    proposedDiff,
    handleCloseFile,
    handleSelectFile
  } = useEditor();

  const {
    isSidebarOpen,
    sidebarTab,
    isAiPanelOpen
  } = useUI();

  const { gitChanges } = useGit();
  const { isSettingsOpen, setIsSettingsOpen, handleSettingsChanged } = useSettings();

  const {
    messages,
    handleSendMessage,
    handleConfirmTool,
    handleConfirmPermission,
    isGenerating,
    statusMessage,
    handleCancelGeneration,
    contextTokens,
    contextPercentage
  } = useAI();

  return (
    <div className="h-screen w-screen flex flex-col bg-[var(--dp-bg-primary)] text-[var(--dp-text-primary)] overflow-hidden font-sans select-none">
      <TitleBar />

      {/* Main Grid */}
      <div className="flex-1 flex overflow-hidden">
        <ActivityBar />

        {/* Workspace Central Panels (separated by 8px grid gaps) */}
        <div className="flex-1 flex gap-2 p-2 overflow-hidden min-w-0 bg-[var(--dp-bg-primary)]">
          
          {/* Left Sidebar tab selection */}
          {isSidebarOpen && (
            <div style={{ width: `${sidebarWidth}px` }} className="h-full shrink-0 relative flex">
              <div className="flex-1 h-full min-w-0 border border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] rounded-lg overflow-hidden flex flex-col shadow-lg shadow-black/20">
                {sidebarTab === 'explorer' && (
                  <Sidebar
                    onSelectFile={handleSelectFile}
                    selectedFilePath={activeFilePath}
                    refreshTrigger={refreshTrigger}
                    workspacePath={workspacePath}
                    onOpenFolder={handleOpenWorkspaceFolder}
                    gitChanges={gitChanges}
                  />
                )}
                {sidebarTab === 'search' && <SearchSidebar onSelectFile={handleSelectFile} />}
                {sidebarTab === 'git' && <GitSidebar />}
                {sidebarTab === 'debug' && <RunDebugSidebar />}
                {sidebarTab === 'extensions' && <ExtensionsSidebar />}
                {sidebarTab === 'testing' && <TestingSidebar />}
                {sidebarTab === 'packages' && <PackagesSidebar />}
                {sidebarTab === 'agents' && <AgentsSidebar />}
                {sidebarTab === 'workspace' && <WorkspaceSidebar />}
                {sidebarTab === 'profile' && <ProfileSidebar />}
              </div>
              <div
                onMouseDown={() => setIsResizingSidebar(true)}
                className="dp-resize-handle-h absolute -right-1 top-0 bottom-0 w-2 z-50 select-none cursor-col-resize hover:bg-[var(--dp-accent)]/20 transition-colors"
              />
            </div>
          )}

          {/* Workspace Central area (Editor & Terminal) */}
          <div className="flex-1 h-full flex flex-col gap-2 min-w-0">
            <div className="flex-1 border border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] rounded-lg overflow-hidden relative shadow-lg shadow-black/20">
              <EditorArea
                activeFilePath={activeFilePath}
                openFiles={openFiles}
                onFileClose={handleCloseFile}
                onFileSelect={handleSelectFile}
                proposedDiff={proposedDiff}
                onRefreshWorkspace={() => {}}
                refreshTrigger={refreshTrigger}
                onOpenFolder={handleOpenWorkspaceFolder}
                workspacePath={workspacePath}
                onEditorRef={(ed) => { editorInstanceRef.current = ed; }}
              />
            </div>

            {/* Resizable Terminal Panel */}
            <div
              style={{ height: `${terminalHeight}px` }}
              className="shrink-0 border border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] rounded-lg overflow-hidden flex flex-col relative shadow-lg shadow-black/20"
            >
              <div
                onMouseDown={() => setIsResizingTerminal(true)}
                className="dp-resize-handle-v absolute -top-1 left-0 right-0 h-2 z-50 select-none cursor-row-resize hover:bg-[var(--dp-accent)]/20 transition-colors"
              />
              <BottomPanel />
            </div>
          </div>

          {/* AI Sidebar panel (width controlled by aiPanelWidth) */}
          {isAiPanelOpen && (
            <div style={{ width: `${aiPanelWidth}px` }} className="h-full shrink-0 relative flex">
              {/* Horizontal Resize handle for AI Panel */}
              <div
                onMouseDown={() => setIsResizingAiPanel(true)}
                className="dp-resize-handle-h absolute -left-1 top-0 bottom-0 w-2 z-50 select-none cursor-col-resize hover:bg-[var(--dp-accent)]/20 transition-colors"
              />
              <div className="flex-1 h-full min-w-0 border border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] rounded-lg overflow-hidden flex flex-col shadow-lg shadow-black/20">
                    <AiWorkspace
                      messages={messages}
                      inputText={chatInputText}
                      setInputText={setChatInputText}
                      onSendMessage={() =>
                        handleSendMessage(
                          chatInputText,
                          chatMode === 'Plan' ? 'Plan' : chatMode === 'Ask' ? 'Ask' : 'Agent/Write',
                          false
                        )
                      }
                      isGenerating={isGenerating}
                      onCancelGeneration={handleCancelGeneration}
                      mode={chatMode}
                      setMode={setChatMode}
                      onConfirmTool={(toolCallId, approved, hunkDecisions) =>
                        handleConfirmTool(toolCallId, approved, 'once', hunkDecisions)
                      }
                      onConfirmPermission={handleConfirmPermission}
                      statusMessage={statusMessage ?? undefined}
                      contextTokens={typeof contextTokens === 'number' ? contextTokens : undefined}
                      contextPercentage={typeof contextPercentage === 'number' ? contextPercentage : undefined}
                    />
              </div>
            </div>
          )}

        </div>
      </div>

      <StatusBar />

      <CommandPalette />

      {/* ── Quick Open overlay (Ctrl+P) ── */}
      <QuickOpen
        isOpen={isQuickOpenOpen}
        onClose={() => setIsQuickOpenOpen(false)}
        onOpenFile={handleSelectFile}
        recentFiles={openFiles}
      />

      {/* ── Go to Symbol overlay (Ctrl+Shift+O) ── */}
      <GoToSymbol
        isOpen={isGoToSymbolOpen}
        onClose={() => setIsGoToSymbolOpen(false)}
        activeFilePath={activeFilePath}
        onRevealLine={handleRevealLine}
      />

      {/* Settings Modal overlay */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onProfileChanged={handleSettingsChanged}
      />



      {/* Toast Overlay */}
      <div className="fixed bottom-8 right-6 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            onClick={() => removeToast(t.id)}
            className={`pointer-events-auto px-3.5 py-2 text-xs border shadow-lg flex items-center gap-2 select-text cursor-pointer transition-all duration-300 transform translate-y-0 rounded-none animate-slide-in ${
              t.type === 'success'
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : t.type === 'error'
                ? 'bg-red-500/10 text-red-400 border-red-500/20'
                : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
            }`}
          >
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <CoreProvider>
      <LSPProvider>
        <EditorShell />
      </LSPProvider>
    </CoreProvider>
  );
}