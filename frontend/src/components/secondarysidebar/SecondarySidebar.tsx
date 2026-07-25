import React, { useState, useEffect } from 'react';
import {
  Bot,
  ListTree,
  History,
  Layers,
  ShieldAlert,
  ListChecks,
  X,
  Box,
  FunctionSquare,
  Code,
  Type,
  Hash,
  Braces,
  GitCommit,
  Search,
  Loader2,
  RefreshCw
} from 'lucide-react';
import { useUI, type SecondaryTabType } from '../../core/ui/UIContext';
import { useEditor } from '../../core/editor/EditorContext';
import { useGit } from '../../core/git/GitContext';
import { AiWorkspace } from '../chat/AiWorkspace';
import { VisualWorkspaceGraph } from '../graph/VisualWorkspaceGraph';
import { WorkspaceReviewPanel } from '../review/WorkspaceReviewPanel';
import { TaskQueuePanel } from '../tasks/TaskQueuePanel';
import type { ChatMessage, ChatMode } from '../../types/chat';

interface WorkspaceSymbol {
  name: string;
  kindName: string;
  line: number;
  col: number;
}

interface SecondarySidebarProps {
  messages: ChatMessage[];
  inputText: string;
  setInputText: (text: string) => void;
  onSendMessage: () => void;
  isGenerating: boolean;
  onCancelGeneration: () => void;
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  onConfirmTool?: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  statusMessage?: string;
  contextTokens?: number | null;
  contextPercentage?: number | null;
  activeSessionId?: string;
  onResumeSession?: (sessionId: string) => Promise<void>;
  onRevealLine?: (line: number, col?: number) => void;
}

function SymbolIcon({ kindName }: { kindName: string }) {
  switch (kindName) {
    case 'class':
      return <Box className="w-3.5 h-3.5 text-yellow-400 shrink-0" />;
    case 'function':
      return <FunctionSquare className="w-3.5 h-3.5 text-blue-400 shrink-0" />;
    case 'method':
      return <Code className="w-3.5 h-3.5 text-green-400 shrink-0" />;
    case 'interface':
    case 'type':
      return <Type className="w-3.5 h-3.5 text-cyan-400 shrink-0" />;
    case 'variable':
      return <Hash className="w-3.5 h-3.5 text-orange-400 shrink-0" />;
    default:
      return <Braces className="w-3.5 h-3.5 text-violet-400 shrink-0" />;
  }
}

export const SecondarySidebar: React.FC<SecondarySidebarProps> = (props) => {
  const { secondarySidebarTab, setSecondarySidebarTab, setIsSecondarySidebarOpen } = useUI();
  const { activeFilePath } = useEditor();
  const { gitChangesList } = useGit();

  const [symbols, setSymbols] = useState<WorkspaceSymbol[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(false);
  const [symbolQuery, setSymbolQuery] = useState('');

  // Fetch symbols for Outline tab
  const fetchSymbols = async () => {
    if (!activeFilePath) {
      setSymbols([]);
      return;
    }
    setSymbolsLoading(true);
    try {
      const res = await fetch(`/api/workspace/symbols?file=${encodeURIComponent(activeFilePath)}`);
      if (res.ok) {
        const data = await res.json();
        setSymbols(data.symbols || []);
      }
    } catch (e) {
      console.error('Failed to fetch outline symbols:', e);
    } finally {
      setSymbolsLoading(false);
    }
  };

  useEffect(() => {
    if (secondarySidebarTab === 'outline') {
      fetchSymbols();
    }
  }, [activeFilePath, secondarySidebarTab]);

  const filteredSymbols = symbols.filter(s =>
    !symbolQuery || s.name.toLowerCase().includes(symbolQuery.toLowerCase())
  );

  const tabs: Array<{ id: SecondaryTabType; label: string; icon: React.FC<{ className?: string }> }> = [
    { id: 'ai',       label: 'AI Chat',   icon: Bot },
    { id: 'graph',    label: 'Graph',     icon: Layers },
    { id: 'review',   label: 'Review',    icon: ShieldAlert },
    { id: 'queue',    label: 'Tasks',     icon: ListChecks },
    { id: 'outline',  label: 'Outline',   icon: ListTree },
    { id: 'timeline', label: 'Timeline',  icon: History },
  ];

  return (
    <div className="h-full flex flex-col font-sans select-none overflow-hidden bg-[var(--dp-bg-secondary)] border-l border-[var(--dp-border)]">
      {/* ── Top Secondary Header ── */}
      <div className="px-2 pt-2 pb-0 shrink-0 border-b border-[var(--dp-border)] flex items-center justify-between overflow-x-auto">
        {/* Navigation Tabs */}
        <div className="flex items-center gap-0.5 overflow-x-auto py-0.5">
          {tabs.map(t => {
            const Icon = t.icon;
            const isActive = secondarySidebarTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setSecondarySidebarTab(t.id)}
                className={`flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer whitespace-nowrap ${
                  isActive
                    ? 'bg-[var(--dp-accent-dim)] text-[var(--dp-accent)] border border-[var(--dp-accent)]/20 shadow-xs'
                    : 'text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>

        {/* Close Button */}
        <button
          onClick={() => setIsSecondarySidebarOpen(false)}
          className="w-6 h-6 flex items-center justify-center rounded text-[var(--dp-text-muted)] hover:text-[var(--dp-text-primary)] hover:bg-white/5 cursor-pointer transition-colors shrink-0 ml-1"
          title="Close Secondary Sidebar"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ── Panel Content ── */}
      <div className="flex-1 overflow-hidden min-h-0 relative p-1">
        {/* AI Tab */}
        {secondarySidebarTab === 'ai' && (
          <AiWorkspace
            messages={props.messages}
            inputText={props.inputText}
            setInputText={props.setInputText}
            onSendMessage={props.onSendMessage}
            isGenerating={props.isGenerating}
            onCancelGeneration={props.onCancelGeneration}
            mode={props.mode}
            setMode={props.setMode}
            onConfirmTool={props.onConfirmTool}
            onConfirmPermission={props.onConfirmPermission}
            statusMessage={props.statusMessage}
            contextTokens={props.contextTokens}
            contextPercentage={props.contextPercentage}
            activeSessionId={props.activeSessionId}
            onResumeSession={props.onResumeSession}
          />
        )}

        {/* Visual Graph Tab */}
        {secondarySidebarTab === 'graph' && <VisualWorkspaceGraph />}

        {/* Code Review Tab */}
        {secondarySidebarTab === 'review' && <WorkspaceReviewPanel />}

        {/* Agent Queue Tab */}
        {secondarySidebarTab === 'queue' && <TaskQueuePanel />}

        {/* Outline Tab */}
        {secondarySidebarTab === 'outline' && (
          <div className="h-full flex flex-col p-3 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                  <ListTree className="w-4 h-4 text-violet-400" /> File Outline
                </h4>
                <p className="text-[10px] text-gray-400 mt-0.5 truncate max-w-[240px]">
                  {activeFilePath ? activeFilePath.split(/[\\/]/).pop() : 'No active file'}
                </p>
              </div>
              <button
                onClick={fetchSymbols}
                disabled={symbolsLoading}
                className="p-1 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors cursor-pointer disabled:opacity-40"
                title="Refresh symbols"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${symbolsLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            {/* Filter Input */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-500" />
              <input
                type="text"
                value={symbolQuery}
                onChange={e => setSymbolQuery(e.target.value)}
                placeholder="Filter symbols..."
                className="w-full bg-black/40 border border-white/10 rounded-lg pl-8 pr-2 py-1.5 text-xs text-white placeholder-gray-500 outline-none focus:border-violet-500/50"
              />
            </div>

            {/* Symbols List */}
            <div className="flex-1 overflow-y-auto space-y-1 pr-1">
              {symbolsLoading ? (
                <div className="flex items-center justify-center py-8 text-xs text-gray-500 gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-violet-400" /> Parsing symbols...
                </div>
              ) : filteredSymbols.length === 0 ? (
                <div className="text-center py-8 text-xs text-gray-500 italic">
                  {activeFilePath ? 'No symbols found in this file.' : 'Open a file to view outline symbols.'}
                </div>
              ) : (
                filteredSymbols.map((sym, idx) => (
                  <div
                    key={idx}
                    onClick={() => props.onRevealLine?.(sym.line, sym.col)}
                    className="flex items-center justify-between p-2 rounded-lg bg-black/20 hover:bg-white/5 border border-white/5 cursor-pointer group transition-colors"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <SymbolIcon kindName={sym.kindName} />
                      <span className="text-xs font-mono text-gray-200 group-hover:text-white truncate font-medium">
                        {sym.name}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-gray-500 shrink-0">
                      L{sym.line}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Timeline Tab */}
        {secondarySidebarTab === 'timeline' && (
          <div className="h-full flex flex-col p-3 space-y-3">
            <div>
              <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                <History className="w-4 h-4 text-blue-400" /> Git Timeline & Changes
              </h4>
              <p className="text-[10px] text-gray-400 mt-0.5">
                {gitChangesList.length} modified files in current branch
              </p>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {gitChangesList.length === 0 ? (
                <div className="text-center py-8 text-xs text-gray-500 italic">
                  No uncommitted Git changes detected.
                </div>
              ) : (
                gitChangesList.map((change: any, idx: number) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-black/30 border border-white/5 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <GitCommit className="w-3.5 h-3.5 text-orange-400 shrink-0" />
                      <span className="font-mono text-gray-300 truncate">{change.path || change.file || String(change)}</span>
                    </div>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${
                      change.status === 'M' ? 'bg-amber-500/20 text-amber-300' : 'bg-emerald-500/20 text-emerald-300'
                    }`}>
                      {change.status === 'M' ? 'Modified' : 'Added'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
