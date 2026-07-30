import React, { useEffect, useRef, useState } from 'react';
import {
  Bot, Cpu, Beaker, CheckCircle2, Loader2, Sparkles,
  Shield, Zap, GitBranch, Terminal, Database, Globe,
  Layers, Code2, TestTube, Bug, FileText, Package,
  Rocket, Network, Search, ChevronDown, ChevronRight,
  Activity, Clock, X, Plus, Settings
} from 'lucide-react';
import { useAI } from '../core/ai/AIContext';
import { getAgents, getAgentPrompts, addAgent, updateAgentPrompt } from '../api';

// ── Types ──────────────────────────────────────────────────────────────────

interface SubTask {
  id: number;
  agent: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
}

interface AgentNetworkState {
  activeAgent: string;
  activeTask: string;
  subtasks: SubTask[];
  collaborationLog: string[];
}

interface AgentMeta {
  name: string;
  role: string;
  tier: string;
  icon: React.ComponentType<any>;
  color: string;
  is_custom?: boolean;
}

const TIERS = ['Planning', 'Architecture', 'Development', 'QA', 'Operations'];

const TIER_COLORS: Record<string, { label: string; dot: string; border: string; header: string }> = {
  Planning:     { label: 'text-[#4C8DFF]', dot: 'bg-[#4C8DFF]',  border: 'border-[#4C8DFF]/20', header: 'bg-[#4C8DFF]/5' },
  Architecture: { label: 'text-blue-400',   dot: 'bg-blue-400',    border: 'border-blue-500/20',   header: 'bg-blue-500/5' },
  Development:  { label: 'text-cyan-400',   dot: 'bg-cyan-400',    border: 'border-cyan-500/20',   header: 'bg-cyan-500/5' },
  QA:           { label: 'text-amber-400',  dot: 'bg-amber-400',   border: 'border-amber-500/20',  header: 'bg-amber-500/5' },
  Operations:   { label: 'text-emerald-400',dot: 'bg-emerald-400', border: 'border-emerald-500/20',header: 'bg-emerald-500/5' },
};

// Lucide icon mapping
const ICON_MAP: Record<string, React.ComponentType<any>> = {
  Bot, Cpu, Beaker, CheckCircle2, Loader2, Sparkles,
  Shield, Zap, GitBranch, Terminal, Database, Globe,
  Layers, Code2, TestTube, Bug, FileText, Package,
  Rocket, Network, Search, Activity, Clock, X
};

const ICON_OPTIONS = [
  'Bot', 'Cpu', 'Beaker', 'Sparkles', 'Shield', 'Zap', 'Terminal', 'Database',
  'Globe', 'Layers', 'Code2', 'TestTube', 'Bug', 'FileText', 'Package', 'Rocket',
  'Network', 'Search', 'Activity'
];

const COLOR_OPTIONS = ['violet', 'blue', 'cyan', 'amber', 'emerald'];

// ── Helper ─────────────────────────────────────────────────────────────────

function getAgentStatus(
  agentName: string,
  state: AgentNetworkState
): 'active' | 'completed' | 'failed' | 'idle' {
  if (state.activeAgent === agentName) return 'active';
  const task = [...state.subtasks].reverse().find(t => t.agent === agentName);
  if (!task) return 'idle';
  if (task.status === 'completed') return 'completed';
  if (task.status === 'failed') return 'failed';
  if (task.status === 'running') return 'active';
  return 'idle';
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatusDot({ status }: { status: 'active' | 'completed' | 'failed' | 'idle' }) {
  if (status === 'active') return (
    <span className="relative flex h-2 w-2 shrink-0">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--dp-accent)] opacity-75" />
      <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--dp-accent)]" />
    </span>
  );
  if (status === 'completed') return <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />;
  if (status === 'failed')    return <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />;
  return <span className="w-2 h-2 rounded-full bg-gray-600 shrink-0" />;
}

function AgentCard({ meta, status, task, onClick }: {
  meta: AgentMeta;
  status: 'active' | 'completed' | 'failed' | 'idle';
  task?: string;
  onClick?: () => void;
}) {
  const Icon = meta.icon;
  const tierColors = TIER_COLORS[meta.tier] || TIER_COLORS.Development;

  return (
    <div 
      onClick={onClick}
      className={`flex items-start gap-2 px-2 py-1.5 rounded-md transition-all duration-200 cursor-pointer ${
        status === 'active'
          ? 'bg-[var(--dp-accent)]/8 border border-[var(--dp-accent)]/25 animate-pulse'
          : 'hover:bg-[var(--dp-bg-tertiary)] border border-transparent'
      }`}
    >
      <div className={`p-1 rounded shrink-0 bg-[var(--dp-bg-tertiary)] border ${tierColors.border}`}>
        <Icon className={`w-3 h-3 ${status === 'active' ? 'text-[var(--dp-accent)]' : tierColors.label}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] font-semibold leading-none truncate ${
            status === 'active' ? 'text-white' : 'text-gray-300'
          }`}>{meta.name}</span>
          <StatusDot status={status} />
          {meta.is_custom && (
            <span className="text-[7px] px-1 py-0.2 bg-[#4C8DFF]/25 border border-[#4C8DFF]/30 text-[#4C8DFF] rounded font-bold uppercase tracking-wider shrink-0 scale-90 origin-left">
              Custom
            </span>
          )}
        </div>
        {status === 'active' && task ? (
          <p className="text-[8.5px] text-[var(--dp-accent)] mt-0.5 truncate font-mono">{task}</p>
        ) : (
          <p className="text-[8.5px] text-gray-600 mt-0.5 truncate">{meta.role}</p>
        )}
      </div>
      {status === 'active' && (
        <Loader2 className="w-3 h-3 text-[var(--dp-accent)] animate-spin shrink-0 mt-0.5" />
      )}
      {status === 'completed' && (
        <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0 mt-0.5" />
      )}
    </div>
  );
}

function TierSection({ tier, agents, state, collapsed, onToggle, onAgentClick }: {
  tier: string;
  agents: AgentMeta[];
  state: AgentNetworkState;
  collapsed: boolean;
  onToggle: () => void;
  onAgentClick: (agent: AgentMeta) => void;
}) {
  const colors = TIER_COLORS[tier] || TIER_COLORS.Development;
  const activeCount = agents.filter(a => getAgentStatus(a.name, state) === 'active').length;
  const completedCount = agents.filter(a => getAgentStatus(a.name, state) === 'completed').length;

  return (
    <div className="mb-1">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-1.5 px-2 py-1 hover:bg-[var(--dp-bg-tertiary)] rounded transition-colors"
      >
        {collapsed
          ? <ChevronRight className={`w-3 h-3 ${colors.label} shrink-0`} />
          : <ChevronDown className={`w-3 h-3 ${colors.label} shrink-0`} />
        }
        <span className={`text-[9px] font-bold uppercase tracking-wider ${colors.label}`}>{tier}</span>
        <div className="flex items-center gap-1 ml-auto">
          {activeCount > 0 && (
            <span className="text-[8px] px-1 py-0.5 rounded bg-[var(--dp-accent)]/15 text-[var(--dp-accent)] font-bold">
              {activeCount} active
            </span>
          )}
          {completedCount > 0 && (
            <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-bold">
              {completedCount}✓
            </span>
          )}
        </div>
      </button>

      {!collapsed && (
        <div className="pl-1 space-y-0.5">
          {agents.map(meta => {
            const status = getAgentStatus(meta.name, state);
            const lastTask = [...state.subtasks].reverse().find(t => t.agent === meta.name);
            return (
              <AgentCard
                key={meta.name}
                meta={meta}
                status={status}
                task={status === 'active' ? state.activeTask : lastTask?.description}
                onClick={() => onAgentClick(meta)}
              />
            );
          })}
          {agents.length === 0 && (
            <p className="text-[8px] text-gray-600 italic pl-6 py-1">No agents in this tier</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function AgentsSidebar() {
  const [agentState, setAgentState] = useState<AgentNetworkState>({
    activeAgent: 'Orchestrator',
    activeTask: 'Idle — waiting for task',
    subtasks: [],
    collaborationLog: [],
  });
  const [collapsedTiers, setCollapsedTiers] = useState<Record<string, boolean>>({
    Planning: false, Architecture: false, Development: false, QA: true, Operations: true,
  });
  const [showLog, setShowLog] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  // Agent dynamic states
  const [agents, setAgents] = useState<AgentMeta[]>([]);
  const [prompts, setPrompts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentMeta | null>(null);
  const [editPromptText, setEditPromptText] = useState('');

  // Form states for new agent
  const [newAgentName, setNewAgentName] = useState('');
  const [newAgentRole, setNewAgentRole] = useState('');
  const [newAgentTier, setNewAgentTier] = useState('Planning');
  const [newAgentIcon, setNewAgentIcon] = useState('Bot');
  const [newAgentColor, setNewAgentColor] = useState('cyan');
  const [newAgentSystemPrompt, setNewAgentSystemPrompt] = useState('You are a specialized custom agent.');
  const [newAgentPromptTemplate, setNewAgentPromptTemplate] = useState('Process this coding request:\n{task_description}');

  // Fetch agents and prompts from backend
  const fetchAgentsAndPrompts = async () => {
    try {
      setLoading(true);
      const fetchedAgents = await getAgents();
      const fetchedPrompts = await getAgentPrompts();
      
      const mapped: AgentMeta[] = fetchedAgents.map(a => ({
        name: a.name,
        role: a.role,
        tier: a.tier,
        icon: ICON_MAP[a.icon] || Bot,
        color: a.color,
        is_custom: a.is_custom
      }));
      
      setAgents(mapped);
      setPrompts(fetchedPrompts);
    } catch (err) {
      console.error('Failed to load agents from backend', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgentsAndPrompts();
  }, []);

  // Listen to global WebSocket for agent_state messages (via AIContext wsRef)
  const { wsRef } = useAI();

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'agent_state') {
          setAgentState({
            activeAgent: data.active_agent || 'Orchestrator',
            activeTask: data.active_task || '',
            subtasks: data.subtasks || [],
            collaborationLog: data.collaboration_log || [],
          });
        }
      } catch {
        // ignore non-JSON
      }
    };

    const ws = wsRef.current;
    if (!ws) return;
    ws.addEventListener('message', handleMessage);
    return () => ws.removeEventListener('message', handleMessage);
  }, [wsRef.current]);

  // Auto-scroll log
  useEffect(() => {
    if (showLog && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [agentState.collaborationLog, showLog]);

  const isRunning = agentState.activeAgent !== 'Orchestrator' || agentState.subtasks.some(t => t.status === 'running');
  const totalCompleted = agentState.subtasks.filter(t => t.status === 'completed').length;
  const totalTasks = agentState.subtasks.length;

  const toggleTier = (tier: string) =>
    setCollapsedTiers(prev => ({ ...prev, [tier]: !prev[tier] }));

  // Handle agent click to edit prompt
  const handleAgentClick = (agent: AgentMeta) => {
    setSelectedAgent(agent);
    setEditPromptText(prompts[agent.name] || '');
    setShowEditModal(true);
  };

  // Submit prompt update
  const handleEditPromptSubmit = async () => {
    if (!selectedAgent) return;
    try {
      await updateAgentPrompt(selectedAgent.name, editPromptText);
      setPrompts(prev => ({ ...prev, [selectedAgent.name]: editPromptText }));
      setShowEditModal(false);
    } catch (err) {
      alert('Failed to update agent prompt: ' + err);
    }
  };

  // Submit new agent
  const handleAddAgentSubmit = async () => {
    if (!newAgentName.trim() || !newAgentRole.trim()) {
      alert('Agent Name and Role are required.');
      return;
    }
    try {
      await addAgent({
        name: newAgentName,
        role: newAgentRole,
        tier: newAgentTier,
        icon: newAgentIcon,
        color: newAgentColor,
        system_prompt: newAgentSystemPrompt,
        prompt_template: newAgentPromptTemplate
      });
      
      // Reset form
      setNewAgentName('');
      setNewAgentRole('');
      setNewAgentTier('Planning');
      setNewAgentIcon('Bot');
      setNewAgentColor('cyan');
      setNewAgentSystemPrompt('You are a specialized custom agent.');
      setNewAgentPromptTemplate('Process this coding request:\n{task_description}');
      
      setShowAddModal(false);
      // Reload agents
      await fetchAgentsAndPrompts();
    } catch (err) {
      alert('Failed to create agent: ' + err);
    }
  };

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans relative">

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] shrink-0">
        <div className="flex items-center gap-2">
          <Activity className={`w-3.5 h-3.5 ${isRunning ? 'text-[var(--dp-accent)] animate-pulse' : 'text-gray-500'}`} />
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Agent Network</span>
        </div>
        <div className="flex items-center gap-1 ml-auto mr-1.5">
          <button 
            onClick={() => setShowAddModal(true)}
            className="flex items-center justify-center p-1 rounded hover:bg-[var(--dp-bg-tertiary)] text-gray-400 hover:text-white transition-all duration-150"
            title="Add New Agent"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
        <span className={`flex items-center gap-1 text-[8px] px-1.5 py-0.5 rounded font-bold uppercase border ${
          isRunning
            ? 'bg-[var(--dp-accent)]/10 text-[var(--dp-accent)] border-[var(--dp-accent)]/20'
            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
        }`}>
          {isRunning ? 'Running' : 'Online'}
        </span>
      </div>

      {/* Active Agent Banner */}
      {isRunning && (
        <div className="px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-accent)]/5 shrink-0">
          <div className="flex items-center gap-2">
            <Loader2 className="w-3 h-3 text-[var(--dp-accent)] animate-spin shrink-0" />
            <div className="min-w-0">
              <p className="text-[9px] font-bold text-[var(--dp-accent)] truncate">{agentState.activeAgent}</p>
              <p className="text-[8px] text-gray-400 truncate">{agentState.activeTask}</p>
            </div>
          </div>
          {totalTasks > 0 && (
            <div className="mt-1.5">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[8px] text-gray-500 font-mono">{totalCompleted}/{totalTasks} tasks</span>
                <span className="text-[8px] text-gray-500 font-mono">
                  {Math.round((totalCompleted / totalTasks) * 100)}%
                </span>
              </div>
              <div className="h-0.5 bg-[var(--dp-bg-tertiary)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[var(--dp-accent)] rounded-full transition-all duration-500"
                  style={{ width: `${(totalCompleted / totalTasks) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Agent Tiers */}
      <div className="flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin text-[var(--dp-accent)]" />
            <span className="text-[9px]">Loading agents...</span>
          </div>
        ) : (
          TIERS.map(tier => {
            const tierAgents = agents.filter(a => a.tier === tier);
            return (
              <TierSection
                key={tier}
                tier={tier}
                agents={tierAgents}
                state={agentState}
                collapsed={collapsedTiers[tier] ?? false}
                onToggle={() => toggleTier(tier)}
                onAgentClick={handleAgentClick}
              />
            );
          })
        )}
      </div>

      {/* Collaboration Log */}
      <div className="border-t border-[var(--dp-border)] shrink-0">
        <button
          onClick={() => setShowLog(v => !v)}
          className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-[var(--dp-bg-tertiary)] transition-colors"
        >
          <div className="flex items-center gap-1.5">
            <Clock className="w-3 h-3 text-gray-500" />
            <span className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Agent Log</span>
            {agentState.collaborationLog.length > 0 && (
              <span className="text-[8px] px-1 py-0.5 rounded bg-gray-700 text-gray-400 font-mono">
                {agentState.collaborationLog.length}
              </span>
            )}
          </div>
          {showLog
            ? <ChevronDown className="w-3 h-3 text-gray-600" />
            : <ChevronRight className="w-3 h-3 text-gray-600" />
          }
        </button>
        {showLog && (
          <div
            ref={logRef}
            className="max-h-40 overflow-y-auto px-2 pb-2 space-y-0.5 bg-[var(--dp-bg-primary)]"
          >
            {agentState.collaborationLog.length === 0 ? (
              <p className="text-[8px] text-gray-600 italic py-2 text-center font-mono">No log entries yet.</p>
            ) : (
              agentState.collaborationLog.map((entry, i) => (
                <div key={i} className="flex gap-1.5 items-start">
                  <span className="text-[7px] text-gray-700 font-mono shrink-0 mt-0.5">{String(i + 1).padStart(2, '0')}</span>
                  <p className="text-[8px] text-gray-400 font-mono leading-snug break-all">{entry}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* ── Add Agent Modal ── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] rounded-lg w-full max-w-md shadow-2xl flex flex-col max-h-[90vh] text-[var(--dp-text-primary)]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--dp-border)] bg-[var(--dp-bg-primary)] rounded-t-lg">
              <div className="flex items-center gap-2">
                <Plus className="w-4 h-4 text-[var(--dp-accent)]" />
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-300">Add New Custom Agent</span>
              </div>
              <button onClick={() => setShowAddModal(false)} className="text-gray-400 hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              <div>
                <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">Agent Name</label>
                <input 
                  type="text" 
                  value={newAgentName}
                  onChange={e => setNewAgentName(e.target.value)}
                  className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]"
                  placeholder="e.g. Security Auditor Agent"
                />
              </div>
              <div>
                <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">Role / Description</label>
                <input 
                  type="text" 
                  value={newAgentRole}
                  onChange={e => setNewAgentRole(e.target.value)}
                  className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]"
                  placeholder="e.g. Scans source code for potential vulnerabilities"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">Tier</label>
                  <select 
                    value={newAgentTier}
                    onChange={e => setNewAgentTier(e.target.value)}
                    className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]"
                  >
                    {TIERS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">Icon</label>
                  <select 
                    value={newAgentIcon}
                    onChange={e => setNewAgentIcon(e.target.value)}
                    className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]"
                  >
                    {ICON_OPTIONS.map(ico => <option key={ico} value={ico}>{ico}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">Color</label>
                  <select 
                    value={newAgentColor}
                    onChange={e => setNewAgentColor(e.target.value)}
                    className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)]"
                  >
                    {COLOR_OPTIONS.map(col => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">System instructions</label>
                <textarea 
                  value={newAgentSystemPrompt}
                  onChange={e => setNewAgentSystemPrompt(e.target.value)}
                  className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)] h-16 font-mono"
                  placeholder="System prompt context..."
                />
              </div>
              <div>
                <label className="block text-[8.5px] uppercase font-bold text-gray-400 mb-1">Prompt template</label>
                <textarea 
                  value={newAgentPromptTemplate}
                  onChange={e => setNewAgentPromptTemplate(e.target.value)}
                  className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)] h-20 font-mono"
                  placeholder="Template text. Use {task_description} placeholder."
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-4 py-2.5 border-t border-[var(--dp-border)] bg-[var(--dp-bg-primary)] flex justify-end gap-2 rounded-b-lg">
              <button 
                onClick={() => setShowAddModal(false)}
                className="px-2.5 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-semibold transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleAddAgentSubmit}
                className="px-2.5 py-1.5 rounded bg-[var(--dp-accent)] hover:bg-[var(--dp-accent)]/80 text-white text-xs font-semibold transition-colors"
              >
                Create Agent
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Agent Prompt Modal ── */}
      {showEditModal && selectedAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-[var(--dp-bg-secondary)] border border-[var(--dp-border)] rounded-lg w-full max-w-md shadow-2xl flex flex-col max-h-[90vh] text-[var(--dp-text-primary)]">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--dp-border)] bg-[var(--dp-bg-primary)] rounded-t-lg">
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-[var(--dp-accent)]" />
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-300">
                  Edit Prompt: {selectedAgent.name}
                </span>
              </div>
              <button onClick={() => setShowEditModal(false)} className="text-gray-400 hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>
            
            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              <div>
                <p className="text-[9px] text-gray-500 mb-2 italic">
                  Modify the prompt template for this agent. Be sure to preserve placeholders like <code>{`{task_description}`}</code> or <code>{`{path}`}</code> if required.
                </p>
                {prompts[selectedAgent.name] === "deterministic_worker" ? (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded text-xs">
                    ⚠️ This is a deterministic agent that runs system operations. Its instructions are coded directly in the workspace and cannot be modified.
                  </div>
                ) : (
                  <textarea 
                    value={editPromptText}
                    onChange={e => setEditPromptText(e.target.value)}
                    className="w-full bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[var(--dp-accent)] h-64 font-mono leading-relaxed"
                  />
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-4 py-2.5 border-t border-[var(--dp-border)] bg-[var(--dp-bg-primary)] flex justify-end gap-2 rounded-b-lg">
              <button 
                onClick={() => setShowEditModal(false)}
                className="px-2.5 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-semibold transition-colors"
              >
                Cancel
              </button>
              {prompts[selectedAgent.name] !== "deterministic_worker" && (
                <button 
                  onClick={handleEditPromptSubmit}
                  className="px-2.5 py-1.5 rounded bg-[var(--dp-accent)] hover:bg-[var(--dp-accent)]/80 text-white text-xs font-semibold transition-colors"
                >
                  Save Prompt
                </button>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
