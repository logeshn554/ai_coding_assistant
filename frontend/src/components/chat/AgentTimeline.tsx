import React, { useState } from 'react';
import type { AgentTimelineState } from '../../core/ai/agentTimelineStore';
import { ChevronDown, ChevronRight, CheckCircle2, AlertCircle, Clock, ShieldAlert, Wrench, PlayCircle } from 'lucide-react';

interface AgentTimelineProps {
  timeline: AgentTimelineState;
  onUndoRun?: () => void;
}

export const AgentTimeline: React.FC<AgentTimelineProps> = ({ timeline, onUndoRun }) => {
  const [expandedStepIds, setExpandedStepIds] = useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedStepIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusBadge = (state: string) => {
    switch (state) {
      case 'COMPLETED_VERIFIED':
        return <span className="badge badge-success">✓ COMPLETED VERIFIED</span>;
      case 'COMPLETED_WITH_WARNINGS':
        return <span className="badge badge-warning">⚠ VERIFIED WITH WARNINGS</span>;
      case 'REPAIRING':
        return <span className="badge badge-info flex items-center gap-1"><Wrench className="w-3 h-3 animate-spin" /> REPAIRING</span>;
      case 'WAITING_FOR_APPROVAL':
        return <span className="badge badge-error flex items-center gap-1"><ShieldAlert className="w-3 h-3" /> APPROVAL REQUIRED</span>;
      case 'BLOCKED':
        return <span className="badge badge-error">● BLOCKED</span>;
      case 'FAILED':
        return <span className="badge badge-error">✗ FAILED</span>;
      case 'EXECUTING':
        return <span className="badge badge-primary flex items-center gap-1"><PlayCircle className="w-3 h-3 animate-pulse" /> EXECUTING</span>;
      default:
        return <span className="badge">{state}</span>;
    }
  };

  return (
    <div className="agent-timeline-container p-4 bg-base-200 rounded-lg border border-base-300 shadow-sm my-3">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-base-300">
        <div>
          <h3 className="font-semibold text-base text-base-content flex items-center gap-2">
            Agent Task Timeline
          </h3>
          <p className="text-xs text-base-content/70 mt-0.5">
            {timeline.activeTaskGoal || 'No active task'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge(timeline.state)}
          {onUndoRun && (timeline.state.startsWith('COMPLETED') || timeline.state === 'FAILED') && (
            <button
              onClick={onUndoRun}
              className="btn btn-xs btn-outline btn-warning"
              title="Undo all changes made in this agent run"
            >
              Undo Run
            </button>
          )}
        </div>
      </div>

      {/* Changed files pill summary */}
      {(timeline.changedFiles.modified.length > 0 || timeline.changedFiles.created.length > 0) && (
        <div className="text-xs text-base-content/80 mt-2 py-1 px-2 bg-base-300/50 rounded flex gap-3">
          <span>Files Changed: {timeline.changedFiles.modified.length + timeline.changedFiles.created.length}</span>
          <span className="text-success">+{timeline.changedFiles.created.length} created</span>
          <span className="text-info">~{timeline.changedFiles.modified.length} modified</span>
        </div>
      )}

      {/* Timeline Steps */}
      <div className="timeline-steps-list mt-3 space-y-2">
        {timeline.steps.length === 0 ? (
          <div className="text-xs text-base-content/50 italic py-2">Awaiting agent execution...</div>
        ) : (
          timeline.steps.map((step) => {
            const isExpanded = !!expandedStepIds[step.id];

            return (
              <div key={step.id} className="timeline-step-item text-xs border border-base-300 rounded bg-base-100 p-2">
                <div
                  onClick={() => toggleExpand(step.id)}
                  className="flex items-center justify-between cursor-pointer select-none"
                >
                  <div className="flex items-center gap-2">
                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    <span className="font-medium">{step.title}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    {step.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5 text-success" />}
                    {step.status === 'running' && <Clock className="w-3.5 h-3.5 text-info animate-spin" />}
                    {step.status === 'failed' && <AlertCircle className="w-3.5 h-3.5 text-error" />}
                    {step.status === 'blocked' && <ShieldAlert className="w-3.5 h-3.5 text-warning" />}
                  </div>
                </div>

                {/* Expanded Operational Details */}
                {isExpanded && (
                  <div className="step-details mt-2 pt-2 border-t border-base-200 text-base-content/80 space-y-1">
                    {step.reason && <div><span className="font-semibold">Reason:</span> {step.reason}</div>}
                    {step.files && step.files.length > 0 && (
                      <div>
                        <span className="font-semibold">Files Involved:</span>
                        <ul className="list-disc list-inside ml-2 font-mono text-[11px]">
                          {step.files.map((f, i) => <li key={i}>{f}</li>)}
                        </ul>
                      </div>
                    )}
                    {step.output && (
                      <div className="mt-1">
                        <span className="font-semibold">Operational Result:</span>
                        <pre className="bg-base-300 p-1.5 rounded font-mono text-[11px] overflow-x-auto max-h-32 mt-0.5">
                          {step.output}
                        </pre>
                      </div>
                    )}
                    {step.error && (
                      <div className="mt-1 text-error">
                        <span className="font-semibold">Error:</span> {step.error}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
