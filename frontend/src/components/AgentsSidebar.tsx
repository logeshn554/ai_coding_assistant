import React, { useEffect, useRef, useState } from 'react';
import {
  Bot, Cpu, Beaker, CheckCircle2, Loader2, Sparkles,
  Shield, Zap, GitBranch, Terminal, Database, Globe,
  Layers, Code2, TestTube, Bug, FileText, Package,
  Rocket, Network, Search, ChevronDown, ChevronRight,
  Activity, Clock
} from 'lucide-react';
import { useAI } from '../core/ai/AIContext';

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

// ── Agent tier metadata ────────────────────────────────────────────────────

interface AgentMeta {
  name: string;
  role: string;
  tier: string;
  icon: React.ComponentType<any>;
  color: string;
}

const AGENT_CATALOG: AgentMeta[] = [
  // Tier 1: Planning
  { name: 'Planner Agent',          role: 'Master task planner & dependency graph',    tier: 'Planning',      icon: Sparkles,   color: 'violet' },
  { name: 'Frontend Planner Agent', role: 'UI architecture, components, design system', tier: 'Planning',      icon: Layers,     color: 'violet' },
  { name: 'Backend Planner Agent',  role: 'API structure, DB schema, auth strategy',   tier: 'Planning',      icon: Package,    color: 'violet' },
  { name: 'Requirement Analysis Agent', role: 'Identifies target files & requirements', tier: 'Planning',     icon: Search,     color: 'violet' },
  // Tier 2: Architecture
  { name: 'Software Architect Agent', role: 'Folder structure, patterns, event flows',  tier: 'Architecture',  icon: Cpu,        color: 'blue' },
  // Tier 3: Development
  { name: 'File System Agent',      role: 'Reads workspace files for other agents',    tier: 'Development',   icon: FileText,   color: 'cyan' },
  { name: 'Coding Agent',           role: 'General-purpose file modifications',        tier: 'Development',   icon: Code2,      color: 'cyan' },
  { name: 'Frontend Developer Agent', role: 'React/TS UI, components, hooks, SEO',    tier: 'Development',   icon: Globe,      color: 'cyan' },
  { name: 'Backend Developer Agent',  role: 'REST APIs, auth, services, middleware',  tier: 'Development',   icon: Bot,        color: 'cyan' },
  { name: 'Database Agent',         role: 'Schema, migrations, indexes, seed data',   tier: 'Development',   icon: Database,   color: 'cyan' },
  { name: 'API Agent',              role: 'OpenAPI 3.0, validation, rate limiting',    tier: 'Development',   icon: Network,    color: 'cyan' },
  // Tier 4: QA
  { name: 'Integration Agent',      role: 'Frontend↔Backend↔DB integration checks',  tier: 'QA',            icon: Layers,     color: 'amber' },
  { name: 'Testing Agent',          role: 'Unit, integration & E2E test suites',      tier: 'QA',            icon: TestTube,   color: 'amber' },
  { name: 'Debugging Agent',        role: 'Log analysis, bug detection & fixes',      tier: 'QA',            icon: Bug,        color: 'amber' },
  { name: 'Security Agent',         role: 'OWASP Top 10, XSS, CSRF, JWT, RBAC',      tier: 'QA',            icon: Shield,     color: 'amber' },
  { name: 'Performance Agent',      role: 'Bundles, N+1 queries, caching, memory',   tier: 'QA',            icon: Zap,        color: 'amber' },
  { name: 'Code Review Agent',      role: 'Code quality, naming, architecture',       tier: 'QA',            icon: Beaker,     color: 'amber' },
  { name: 'AI Reviewer Agent',      role: 'Staff Engineer: algorithms, tech debt',    tier: 'QA',            icon: Sparkles,   color: 'amber' },
  // Tier 5: Operations
  { name: 'Documentation Agent',    role: 'README, API docs, developer guide',        tier: 'Operations',    icon: FileText,   color: 'emerald' },
  { name: 'Git Agent',              role: 'Git status, diff summaries, changelogs',   tier: 'Operations',    icon: GitBranch,  color: 'emerald' },
  { name: 'Terminal Agent',         role: 'Runs builds, tests, migrations, Docker',   tier: 'Operations',    icon: Terminal,   color: 'emerald' },
  { name: 'DevOps Agent',           role: 'Dockerfile, CI/CD, NGINX, monitoring',     tier: 'Operations',    icon: Rocket,     color: 'emerald' },
  { name: 'Release Agent',          role: 'Semver, release notes, rollback plan',     tier: 'Operations',    icon: Package,    color: 'emerald' },
];

const TIERS = ['Planning', 'Architecture', 'Development', 'QA', 'Operations'];

const TIER_COLORS: Record<string, { label: string; dot: string; border: string; header: string }> = {
  Planning:     { label: 'text-violet-400', dot: 'bg-violet-400',  border: 'border-violet-500/20', header: 'bg-violet-500/5' },
  Architecture: { label: 'text-blue-400',   dot: 'bg-blue-400',    border: 'border-blue-500/20',   header: 'bg-blue-500/5' },
  Development:  { label: 'text-cyan-400',   dot: 'bg-cyan-400',    border: 'border-cyan-500/20',   header: 'bg-cyan-500/5' },
  QA:           { label: 'text-amber-400',  dot: 'bg-amber-400',   border: 'border-amber-500/20',  header: 'bg-amber-500/5' },
  Operations:   { label: 'text-emerald-400',dot: 'bg-emerald-400', border: 'border-emerald-500/20',header: 'bg-emerald-500/5' },
};

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

function AgentCard({ meta, status, task }: {
  meta: AgentMeta;
  status: 'active' | 'completed' | 'failed' | 'idle';
  task?: string;
}) {
  const Icon = meta.icon;
  const tierColors = TIER_COLORS[meta.tier];

  return (
    <div className={`flex items-start gap-2 px-2 py-1.5 rounded-md transition-all duration-200 ${
      status === 'active'
        ? 'bg-[var(--dp-accent)]/8 border border-[var(--dp-accent)]/25'
        : 'hover:bg-[var(--dp-bg-tertiary)] border border-transparent'
    }`}>
      <div className={`p-1 rounded shrink-0 bg-[var(--dp-bg-tertiary)] border ${tierColors.border}`}>
        <Icon className={`w-3 h-3 ${status === 'active' ? 'text-[var(--dp-accent)]' : tierColors.label}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] font-semibold leading-none truncate ${
            status === 'active' ? 'text-white' : 'text-gray-300'
          }`}>{meta.name}</span>
          <StatusDot status={status} />
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

function TierSection({ tier, agents, state, collapsed, onToggle }: {
  tier: string;
  agents: AgentMeta[];
  state: AgentNetworkState;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const colors = TIER_COLORS[tier];
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
              />
            );
          })}
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

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] shrink-0">
        <div className="flex items-center gap-2">
          <Activity className={`w-3.5 h-3.5 ${isRunning ? 'text-[var(--dp-accent)] animate-pulse' : 'text-gray-500'}`} />
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Agent Network</span>
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
        {TIERS.map(tier => {
          const tierAgents = AGENT_CATALOG.filter(a => a.tier === tier);
          return (
            <TierSection
              key={tier}
              tier={tier}
              agents={tierAgents}
              state={agentState}
              collapsed={collapsedTiers[tier] ?? false}
              onToggle={() => toggleTier(tier)}
            />
          );
        })}
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
    </div>
  );
}
