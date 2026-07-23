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
    contextPercentage,
    activeSessionId,
    handleSelectSession,
  } = useAI();

  return (
    <div className="h-screen w-screen flex flex-col bg-[var(--dp-bg-primary)] text-[var(--dp-text-primary)] overflow-hidden font-sans select-none">
      <TitleBar />

      {/* Main Grid */}
      <div className="flex-1 flex overflow-hidden">
        <ActivityBar />

        {/* Workspace Central Panels — seamless, no gap */}
        <div className="flex-1 flex overflow-hidden min-w-0 bg-[var(--dp-bg-primary)]">
          
          {/* Left Sidebar tab selection */}
          {isSidebarOpen && (
            <div style={{ width: `${sidebarWidth}px` }} className="h-full shrink-0 relative flex">
              <div className="flex-1 h-full min-w-0 overflow-hidden flex flex-col" style={{ background: 'var(--dp-bg-secondary)', borderRight: '1px solid var(--dp-border)' }}>
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
                className="dp-resize-handle-h absolute right-0 top-0 bottom-0 w-[3px] z-50 select-none cursor-col-resize"
              />
            </div>
          )}

          {/* Workspace Central area (Editor & Terminal) */}
          <div className="flex-1 h-full flex flex-col min-w-0" style={{ borderRight: '1px solid var(--dp-border)' }}>
            <div className="flex-1 overflow-hidden relative">
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
              className="shrink-0 overflow-hidden flex flex-col relative"
              style={{ borderTop: '1px solid var(--dp-border)', height: `${terminalHeight}px` }}
            >
              <div
                onMouseDown={() => setIsResizingTerminal(true)}
                className="dp-resize-handle-v absolute top-0 left-0 right-0 h-[3px] z-50 select-none cursor-row-resize"
              />
              <BottomPanel />
            </div>
          </div>

          {/* AI Sidebar panel (width controlled by aiPanelWidth) */}
          {isAiPanelOpen && (
            <div style={{ width: `${aiPanelWidth}px` }} className="h-full shrink-0 relative flex">
              <div
                onMouseDown={() => setIsResizingAiPanel(true)}
                className="dp-resize-handle-h absolute left-0 top-0 bottom-0 w-[3px] z-50 select-none cursor-col-resize"
              />
              <div className="flex-1 h-full min-w-0 overflow-hidden flex flex-col">
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
                      activeSessionId={activeSessionId}
                      onResumeSession={handleSelectSession}
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
      <div className="fixed bottom-6 right-5 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            onClick={() => removeToast(t.id)}
            className={`pointer-events-auto px-4 py-2.5 text-[12px] shadow-[var(--dp-shadow-float)] flex items-center gap-2.5 select-text cursor-pointer transition-all duration-300 animate-slide-in rounded-xl border backdrop-blur-sm ${
              t.type === 'success'
                ? 'bg-[var(--dp-success)]/10 text-[var(--dp-success)] border-[var(--dp-success)]/20'
                : t.type === 'error'
                ? 'bg-[var(--dp-error)]/10 text-[var(--dp-error)] border-[var(--dp-error)]/20'
                : 'bg-[var(--dp-info)]/10 text-[var(--dp-info)] border-[var(--dp-info)]/20'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full shrink-0 ${
              t.type === 'success' ? 'bg-[var(--dp-success)]' :
              t.type === 'error'   ? 'bg-[var(--dp-error)]'   :
              'bg-[var(--dp-info)]'
            }" />
            <span className="font-medium">{t.message}</span>
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