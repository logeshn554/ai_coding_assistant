import React from 'react';
import { Bot, Cpu, Beaker, CheckCircle2, Loader2, Sparkles } from 'lucide-react';

interface Agent {
  name: string;
  role: string;
  status: 'idle' | 'working' | 'offline';
  task?: string;
  metric?: string;
  icon: React.ComponentType<any>;
}

export default function AgentsSidebar() {
  const agents: Agent[] = [
    {
      name: 'DevPilot Orchestrator',
      role: 'Multi-agent coordinator & task router',
      status: 'idle',
      icon: Sparkles,
      metric: 'v2.5.0'
    },
    {
      name: 'Coder Agent',
      role: 'Writes and modifies files in workspace',
      status: 'working',
      task: 'Redesigning App.tsx welcome page',
      metric: '94% confidence',
      icon: Bot
    },
    {
      name: 'Architect Agent',
      role: 'Plans architecture & slash commands',
      status: 'idle',
      metric: 'Claude 3.5 Sonnet',
      icon: Cpu
    },
    {
      name: 'Testing Agent',
      role: 'Drafts unit tests and runs suites',
      status: 'idle',
      task: 'All 8 tests passing',
      metric: '82% coverage',
      icon: Beaker
    }
  ];

  const steps = [
    { text: 'Analyze workspace structure', status: 'completed' },
    { text: 'Redesign layout to 1920x1080 specs', status: 'completed' },
    { text: 'Modify index.css theme variables', status: 'completed' },
    { text: 'Upgrade EditorArea welcome page', status: 'working' },
    { text: 'Verify TypeScript compilation stability', status: 'pending' }
  ];

  return (
    <div className="h-full flex flex-col bg-[var(--dp-bg-secondary)] text-[var(--dp-text-primary)] select-none font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--dp-border)] bg-[var(--dp-bg-secondary)] shrink-0 select-none">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400">Agent Network</span>
        <span className="flex items-center gap-1 text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.2 rounded font-bold uppercase">
          Online
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Agent Cards */}
        <div className="space-y-2">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500 mb-1">Active Agents</h3>
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.name}
                className="p-2.5 bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg hover:border-[var(--dp-accent)]/30 transition-all flex flex-col gap-1.5 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-1 bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded-md text-[var(--dp-accent)]">
                      <Icon className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <h4 className="text-[11px] font-semibold text-white leading-none">{agent.name}</h4>
                      <p className="text-[9px] text-gray-500 mt-1">{agent.role}</p>
                    </div>
                  </div>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    agent.status === 'working' ? 'bg-[var(--dp-accent)] animate-pulse' :
                    agent.status === 'idle' ? 'bg-emerald-500' : 'bg-gray-600'
                  }`} />
                </div>

                {agent.task && (
                  <div className="mt-1 px-2 py-1 bg-[var(--dp-bg-primary)] border border-[var(--dp-border)] rounded text-[9px] font-mono text-gray-400 flex items-center gap-1.5">
                    {agent.status === 'working' ? (
                      <Loader2 className="w-2.5 h-2.5 text-[var(--dp-accent)] animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500" />
                    )}
                    <span className="truncate">{agent.task}</span>
                  </div>
                )}

                <div className="flex items-center justify-between text-[8px] text-gray-500 font-mono mt-0.5">
                  <span>STATUS: {agent.status.toUpperCase()}</span>
                  <span>{agent.metric}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Task Execution Log */}
        <div className="space-y-2 pt-2 border-t border-[var(--dp-border)]">
          <h3 className="text-[9px] font-bold uppercase tracking-wider text-gray-500">Execution Stack</h3>
          <div className="bg-[var(--dp-bg-tertiary)] border border-[var(--dp-border)] rounded-lg p-2.5 font-mono text-[9px] space-y-2">
            {steps.map((step, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-gray-600 font-semibold">{idx + 1}.</span>
                <span className={
                  step.status === 'completed' ? 'text-gray-400 line-through' :
                  step.status === 'working' ? 'text-white font-medium flex items-center gap-1' : 'text-gray-605'
                }>
                  {step.text}
                  {step.status === 'working' && <span className="w-1.5 h-1.5 bg-[var(--dp-accent)] rounded-full animate-ping shrink-0" />}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
