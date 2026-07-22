import React, { useState } from 'react';
import { 
  Sparkles, LayoutDashboard, ClipboardList, CheckSquare, Clock, 
  Users, Wrench, Brain, MessageSquare, Terminal 
} from 'lucide-react';
import type { 
  ChatMessage, TimelineStep, AgentCardData, ToolExecutionItem, 
  ProjectContextInfo, ProjectMemoryItem, AiTaskItem 
} from '../../types/chat';
import { AiCommandBar } from './AiCommandBar';
import { ToolExecutionCard } from './ToolExecutionCard';
import { AiTaskBoard } from './AiTaskBoard';
import { ProjectContextPanel } from './ProjectContextPanel';
import { ProjectMemoryPanel } from './ProjectMemoryPanel';
import { MessageList } from './MessageList';

type AiWorkspaceSection = 
  | 'overview' 
  | 'planner' 
  | 'tasks' 
  | 'timeline' 
  | 'agents' 
  | 'files' 
  | 'tools' 
  | 'memory' 
  | 'chat' 
  | 'logs';

interface AiWorkspaceProps {
  messages: ChatMessage[];
  inputText: string;
  setInputText: (text: string) => void;
  onSendMessage: () => void;
  isGenerating: boolean;
  onCancelGeneration: () => void;
  mode: 'Ask' | 'Plan' | 'Agent';
  setMode: (mode: 'Ask' | 'Plan' | 'Agent') => void;
  onConfirmTool?: (toolCallId: string, approved: boolean, hunkDecisions?: Record<string, boolean>) => void;
  onConfirmPermission?: (toolCallId: string, approved: boolean, scope: 'once' | 'session' | 'project', command: string) => void;
  statusMessage?: string;
  contextTokens?: number | null;
  contextPercentage?: number | null;
}

export const AiWorkspace: React.FC<AiWorkspaceProps> = ({
  messages,
  inputText,
  setInputText,
  onSendMessage,
  isGenerating,
  onCancelGeneration,
  mode,
  setMode,
  onConfirmTool,
  onConfirmPermission,
  statusMessage: _statusMessage,
  contextTokens = 0,
  contextPercentage: _contextPercentage = 0
}) => {
  const [activeTab, setActiveTab] = useState<AiWorkspaceSection>('chat');
  const [hunkDecisions, setHunkDecisions] = useState<Record<string, Record<string, boolean>>>({});

  const handleToggleHunk = (msgId: string, hunkId: string, accepted: boolean) => {
    setHunkDecisions(prev => ({
      ...prev,
      [msgId]: {
        ...(prev[msgId] || {}),
        [hunkId]: accepted
      }
    }));
  };

  // Simulated multi-agent telemetry
  const agents: AgentCardData[] = [
    { id: '1', name: 'Planner', status: 'idle', currentTask: 'Architecture mapping', progress: 100, cpuUsage: '0.2%', tokensUsed: 4200, lastActivity: '2m ago' },
    { id: '2', name: 'Coder', status: isGenerating ? 'running' : 'idle', currentTask: isGenerating ? 'Generating code changes' : 'Waiting for prompt', progress: isGenerating ? 65 : 100, cpuUsage: isGenerating ? '3.4%' : '0.1%', tokensUsed: 12400, lastActivity: 'Just now' },
    { id: '3', name: 'Reviewer', status: 'idle', currentTask: 'Code quality analysis', progress: 100, cpuUsage: '0.1%', tokensUsed: 1800, lastActivity: '5m ago' },
    { id: '4', name: 'Tester', status: 'idle', currentTask: 'Unit test verification', progress: 100, cpuUsage: '0.1%', tokensUsed: 2100, lastActivity: '8m ago' },
    { id: '5', name: 'Researcher', status: 'idle', currentTask: 'Dependency search', progress: 100, cpuUsage: '0.0%', tokensUsed: 950, lastActivity: '12m ago' }
  ];

  // Timeline events feed
  const timeline: TimelineStep[] = [
    { id: '1', action: 'Initialized Workspace Session', timestamp: '16:45:00', status: 'completed' },
    { id: '2', action: 'Indexed Workspace Dependencies (package.json)', timestamp: '16:45:02', status: 'completed' },
    { id: '3', action: 'Analyzed System Architecture & Routes', timestamp: '16:45:05', status: 'completed' }
  ];

  // Sample tasks for Kanban board
  const tasks: AiTaskItem[] = [
    { id: 't1', title: 'Parse request and build architecture plan', phase: 'planning', status: 'completed', progress: 100, owner: 'Planner', estimatedTime: '5s' },
    { id: 't2', title: 'Generate & edit core application components', phase: 'coding', status: isGenerating ? 'in_progress' : 'completed', progress: isGenerating ? 70 : 100, owner: 'Coder', estimatedTime: '15s' },
    { id: 't3', title: 'Verify TypeScript types and syntax', phase: 'testing', status: 'pending', progress: 0, owner: 'Tester', estimatedTime: '8s' },
    { id: 't4', title: 'Security and code quality review', phase: 'review', status: 'pending', progress: 0, owner: 'Reviewer', estimatedTime: '10s' },
    { id: 't5', title: 'Deploy production bundle', phase: 'deployment', status: 'pending', progress: 0, owner: 'Coder', estimatedTime: '12s' }
  ];

  // Sample tool calls
  const tools: ToolExecutionItem[] = [
    { id: 'tc1', tool: 'file_read', name: 'Read file package.json', params: { path: 'package.json' }, status: 'success', durationMs: 120, output: '{\n  "name": "devpilot",\n  "version": "2.4.0"\n}' },
    { id: 'tc2', tool: 'search', name: 'Search codebase for "useAI"', params: { query: 'useAI' }, status: 'success', durationMs: 340, output: 'Found 14 occurrences in 6 files.' }
  ];

  // Project context state
  const contextInfo: ProjectContextInfo = {
    indexedFiles: 142,
    totalFiles: 156,
    architecture: 'Modular React + FastAPI',
    framework: 'React / Vite / Tailwind',
    language: 'TypeScript / Python',
    database: 'SQLite / Redis',
    activeBranch: 'main',
    tokenUsage: contextTokens || 14200,
    tokenBudget: 128000
  };

  // Persistent Project Memories
  const [memories, setMemories] = useState<ProjectMemoryItem[]>([
    { id: 'm1', category: 'convention', title: 'Dark-first 8px Spacing System', content: 'Always use 8px grid spacing (p-2, p-4, p-6), 120ms transitions, and sleek dark background tokens.', enabled: true },
    { id: 'm2', category: 'architecture', title: 'Strict Component Modularization', content: 'Keep component files clean and focused under 300 lines; extract UI subpanels.', enabled: true }
  ]);

  const handleAddMemory = (item: Omit<ProjectMemoryItem, 'id'>) => {
    const newItem: ProjectMemoryItem = {
      ...item,
      id: `m_${Date.now()}`
    };
    setMemories(prev => [newItem, ...prev]);
  };

  const handleToggleMemory = (id: string) => {
    setMemories(prev => prev.map(m => m.id === id ? { ...m, enabled: !m.enabled } : m));
  };

  const handleDeleteMemory = (id: string) => {
    setMemories(prev => prev.filter(m => m.id !== id));
  };

  const tabs: Array<{ id: AiWorkspaceSection; label: string; icon: any }> = [
    { id: 'chat', label: 'Chat', icon: MessageSquare },
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'planner', label: 'Plan', icon: ClipboardList },
    { id: 'tasks', label: 'Tasks', icon: CheckSquare },
    { id: 'timeline', label: 'Timeline', icon: Clock },
    { id: 'agents', label: 'Agents', icon: Users },
    { id: 'tools', label: 'Tool Calls', icon: Wrench },
    { id: 'memory', label: 'Memory', icon: Brain },
    { id: 'logs', label: 'Logs', icon: Terminal },
  ];

  return (
    <div className="h-full flex flex-col bg-[#0d0f15] text-[var(--dp-text-primary)] font-sans border-l border-white/10 select-none overflow-hidden">
      {/* Top Header & Navigation Bar */}
      <div className="bg-[#12141d] border-b border-white/10 px-3 py-2 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-violet-600/20">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <span className="font-bold text-white text-xs tracking-tight">AI Workspace</span>
            {isGenerating && (
              <span className="flex items-center gap-1 text-[10px] text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full border border-violet-500/20 font-medium animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-400"></span> Active Execution
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-400 font-mono bg-white/5 px-2 py-0.5 rounded border border-white/5">
              {(contextTokens || 0).toLocaleString()} tokens
            </span>
          </div>
        </div>

        {/* Section Navigation Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar pt-1">
          {tabs.map((t) => {
            const Icon = t.icon;
            const isActive = activeTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all shrink-0 cursor-pointer ${
                  isActive 
                    ? 'bg-violet-600/20 text-violet-300 border border-violet-500/30 font-semibold' 
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/5'
                }`}
              >
                <Icon className="w-3 h-3" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content Area per Tab */}
      <div className="flex-1 overflow-y-auto p-3 min-h-0 space-y-3">
        {/* Chat Section */}
        {activeTab === 'chat' && (
          <div className="h-full flex flex-col justify-between space-y-3">
            <div className="flex-1 overflow-y-auto min-h-0">
              <MessageList
                messages={messages}
                onConfirmTool={onConfirmTool || (() => {})}
                onConfirmPermission={onConfirmPermission}
                hunkDecisions={hunkDecisions}
                onToggleHunk={handleToggleHunk}
              />
            </div>
            <div className="shrink-0 pt-2">
              <AiCommandBar
                inputText={inputText}
                setInputText={setInputText}
                onSend={onSendMessage}
                isGenerating={isGenerating}
                onCancel={onCancelGeneration}
                mode={mode}
                setMode={setMode}
              />
            </div>
          </div>
        )}

        {/* Overview Section */}
        {activeTab === 'overview' && (
          <div className="space-y-3">
            <ProjectContextPanel contextInfo={contextInfo} />
            <ProjectMemoryPanel
              memories={memories}
              onAddMemory={handleAddMemory}
              onToggleMemory={handleToggleMemory}
              onDeleteMemory={handleDeleteMemory}
            />
          </div>
        )}

        {/* Tasks Section (Kanban) */}
        {activeTab === 'tasks' && (
          <div className="h-full min-h-[350px]">
            <AiTaskBoard tasks={tasks} />
          </div>
        )}

        {/* Timeline Section */}
        {activeTab === 'timeline' && (
          <div className="bg-[#12141c] border border-white/10 rounded-xl p-3 text-xs space-y-3 shadow-md">
            <h4 className="font-bold text-white text-xs flex items-center gap-1.5 border-b border-white/5 pb-2">
              <Clock className="w-4 h-4 text-violet-400" /> Action Execution Timeline
            </h4>
            <div className="space-y-2 relative before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-white/10 pl-6">
              {timeline.map((step) => (
                <div key={step.id} className="relative flex items-center justify-between p-2 rounded-lg bg-black/20 border border-white/5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span className="font-medium text-white text-[11px]">{step.action}</span>
                  </div>
                  <span className="text-[9px] text-gray-500 font-mono">{step.timestamp}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Agents Section */}
        {activeTab === 'agents' && (
          <div className="space-y-2">
            <h4 className="font-bold text-white text-xs flex items-center gap-1.5 mb-2">
              <Users className="w-4 h-4 text-indigo-400" /> Multi-Agent Swarm Telemetry
            </h4>
            <div className="grid grid-cols-1 gap-2.5">
              {agents.map((agent) => (
                <div key={agent.id} className="bg-[#141722] border border-white/10 rounded-xl p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-xs">{agent.name} Agent</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      agent.status === 'running' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-800 text-gray-400'
                    }`}>
                      {agent.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-400 font-mono">{agent.currentTask}</p>
                  <div className="w-full bg-black/40 h-1.5 rounded-full overflow-hidden">
                    <div className="bg-indigo-500 h-full" style={{ width: `${agent.progress}%` }} />
                  </div>
                  <div className="flex justify-between text-[9px] text-gray-500 font-mono pt-1 border-t border-white/5">
                    <span>CPU: {agent.cpuUsage}</span>
                    <span>Tokens: {agent.tokensUsed?.toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tools Section */}
        {activeTab === 'tools' && (
          <div className="space-y-2">
            <h4 className="font-bold text-white text-xs flex items-center gap-1.5 mb-2">
              <Wrench className="w-4 h-4 text-amber-400" /> Tool Execution Calls
            </h4>
            {tools.map((t) => (
              <ToolExecutionCard key={t.id} toolItem={t} />
            ))}
          </div>
        )}

        {/* Memory Section */}
        {activeTab === 'memory' && (
          <ProjectMemoryPanel
            memories={memories}
            onAddMemory={handleAddMemory}
            onToggleMemory={handleToggleMemory}
            onDeleteMemory={handleDeleteMemory}
          />
        )}

        {/* Logs Section */}
        {activeTab === 'logs' && (
          <div className="bg-black/80 border border-white/10 rounded-xl p-3 font-mono text-[10px] text-emerald-400 h-64 overflow-y-auto space-y-1">
            <div className="text-gray-500">[SYSTEM] DevPilot AI Engine v2.4 initialized</div>
            <div className="text-gray-500">[LOG] Loaded workspace state & memory rules</div>
            <div className="text-blue-400">[ROUTER] Active model router initialized with profile</div>
            <div className="text-emerald-400">[EXEC] Agent pipeline ready</div>
          </div>
        )}
      </div>
    </div>
  );
};
