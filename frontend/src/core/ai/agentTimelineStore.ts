/**
 * Central IDE State & Agent Timeline Store — Step 3, 4, 37 requirements.
 *
 * Manages full AgentState lifecycle (IDLE, PLANNING, EXECUTING, WAITING_FOR_APPROVAL,
 * VERIFYING, REPAIRING, REVIEWING, COMPLETED_VERIFIED, COMPLETED_WITH_WARNINGS, BLOCKED, FAILED, CANCELLED)
 * and processes structured AgentEvents into a reactive timeline.
 */

export type AgentState =
  | 'IDLE'
  | 'PLANNING'
  | 'EXECUTING'
  | 'WAITING_FOR_TOOL'
  | 'VERIFYING'
  | 'REPAIRING'
  | 'WAITING_FOR_APPROVAL'
  | 'REVIEWING'
  | 'COMPLETED_VERIFIED'
  | 'COMPLETED_WITH_WARNINGS'
  | 'BLOCKED'
  | 'FAILED'
  | 'CANCELLED';

export interface AgentTimelineStep {
  id: string;
  type: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'blocked';
  timestamp: string;
  durationMs?: number;
  files?: string[];
  toolName?: string;
  toolArgs?: Record<string, any>;
  output?: string;
  error?: string;
  reason?: string;
}

export interface AgentTimelineState {
  sessionId: string | null;
  state: AgentState;
  activeTaskGoal: string | null;
  steps: AgentTimelineStep[];
  tokensEstimate: number;
  changedFiles: {
    created: string[];
    modified: string[];
    deleted: string[];
  };
  verificationStatus: 'NOT_RUN' | 'RUNNING' | 'PASSED' | 'FAILED';
  approvalRequired: boolean;
  approvalPayload: any | null;
}

export const initialTimelineState: AgentTimelineState = {
  sessionId: null,
  state: 'IDLE',
  activeTaskGoal: null,
  steps: [],
  tokensEstimate: 0,
  changedFiles: { created: [], modified: [], deleted: [] },
  verificationStatus: 'NOT_RUN',
  approvalRequired: false,
  approvalPayload: null,
};

export function agentTimelineReducer(
  state: AgentTimelineState,
  event: { type: string; payload: any; timestamp?: string }
): AgentTimelineState {
  const ts = event.timestamp || new Date().toISOString();

  switch (event.type) {
    case 'agent.started':
      return {
        ...state,
        sessionId: event.payload.session_id || state.sessionId,
        state: 'PLANNING',
        activeTaskGoal: event.payload.description || 'Executing coding task',
        steps: [],
      };

    case 'agent.contract.created':
      return {
        ...state,
        activeTaskGoal: event.payload.contract?.goal || state.activeTaskGoal,
      };

    case 'agent.plan.created':
      return {
        ...state,
        state: 'EXECUTING',
        tokensEstimate: event.payload.tokens_estimate || 0,
        steps: [
          ...state.steps,
          {
            id: `plan_${Date.now()}`,
            type: 'plan',
            title: 'Build Plan & Retrieve Context',
            status: 'completed',
            timestamp: ts,
            files: event.payload.context_files || [],
            reason: 'Analyzed workspace and retrieved L0-L4 context',
          },
        ],
      };

    case 'tool.started':
      return {
        ...state,
        state: 'EXECUTING',
        steps: [
          ...state.steps,
          {
            id: event.payload.tool_call_id || `tool_${Date.now()}`,
            type: 'tool',
            title: `Executing ${event.payload.name}`,
            status: 'running',
            timestamp: ts,
            toolName: event.payload.name,
            toolArgs: event.payload.arguments,
          },
        ],
      };

    case 'tool.completed':
      return {
        ...state,
        steps: state.steps.map((step) =>
          step.id === event.payload.tool_call_id
            ? {
                ...step,
                status: event.payload.success ? 'completed' : 'failed',
                output: event.payload.output,
                error: event.payload.error,
              }
            : step
        ),
      };

    case 'file.changed':
      return {
        ...state,
        changedFiles: {
          created: event.payload.change_set?.created_files || state.changedFiles.created,
          modified: event.payload.change_set?.modified_files || state.changedFiles.modified,
          deleted: event.payload.change_set?.deleted_files || state.changedFiles.deleted,
        },
      };

    case 'verification.started':
      return {
        ...state,
        state: 'VERIFYING',
        verificationStatus: 'RUNNING',
        steps: [
          ...state.steps,
          {
            id: `verif_${Date.now()}`,
            type: 'verification',
            title: 'Running Scoped Verification',
            status: 'running',
            timestamp: ts,
          },
        ],
      };

    case 'verification.completed':
      return {
        ...state,
        verificationStatus: event.payload.status === 'PASSED' ? 'PASSED' : 'FAILED',
        steps: state.steps.map((step) =>
          step.type === 'verification' && step.status === 'running'
            ? {
                ...step,
                status: event.payload.status === 'PASSED' ? 'completed' : 'failed',
                output: event.payload.command,
              }
            : step
        ),
      };

    case 'agent.repair.started':
      return {
        ...state,
        state: 'REPAIRING',
        steps: [
          ...state.steps,
          {
            id: `repair_${Date.now()}`,
            type: 'repair',
            title: `Self-Repair Round ${event.payload.round}`,
            status: 'running',
            timestamp: ts,
            reason: event.payload.failure?.message || 'Analyzing test failure',
          },
        ],
      };

    case 'agent.repair.loop_detected':
      return {
        ...state,
        state: 'BLOCKED',
        steps: [
          ...state.steps,
          {
            id: `loop_${Date.now()}`,
            type: 'repair',
            title: 'Repeated Failure Loop Detected',
            status: 'blocked',
            timestamp: ts,
            error: 'Self-repair stopped to prevent infinite loop.',
          },
        ],
      };

    case 'agent.review.completed':
      return {
        ...state,
        steps: [
          ...state.steps,
          {
            id: `review_${Date.now()}`,
            type: 'review',
            title: 'Agent Reviewer Evaluation',
            status: event.payload.review?.approved ? 'completed' : 'failed',
            timestamp: ts,
            reason: `Confidence: ${(event.payload.review?.confidence || 1.0) * 100}%`,
          },
        ],
      };

    case 'agent.approval_required':
      return {
        ...state,
        state: 'WAITING_FOR_APPROVAL',
        approvalRequired: true,
        approvalPayload: event.payload,
      };

    case 'agent.completed':
      return {
        ...state,
        state: event.payload.verified ? 'COMPLETED_VERIFIED' : 'COMPLETED_WITH_WARNINGS',
        approvalRequired: false,
      };

    case 'agent.error':
      return {
        ...state,
        state: 'FAILED',
        approvalRequired: false,
      };

    case 'agent.cancelled':
      return {
        ...state,
        state: 'CANCELLED',
        approvalRequired: false,
      };

    default:
      return state;
  }
}
