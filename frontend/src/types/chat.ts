export type AgentStatus = 'idle' | 'running' | 'done' | 'error';

export interface AgentState {
  agent_type: string;
  status: AgentStatus;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

export interface DiffHunk {
  type: 'add' | 'remove' | 'context';
  content: string;
  id?: string;
  lines?: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string | any;
  tool_calls?: ToolCall[];
  diff?: { filename: string; hunks: DiffHunk[] };
  cost_usd?: number;
  agents_used?: number;
  elapsed_ms?: number;

  tool_call_id?: string;
  name?: string;
  status?: 'success' | 'error';
  isConfirmPending?: boolean;
  confirmArgs?: any;
  confirmDiff?: {
    path: string;
    original: string;
    proposed: string;
    hunks?: any[];
  };

  // Permission Request Fields
  isPermissionRequest?: boolean;
  permissionCommand?: string;
  permissionRisk?: string;
  permissionReason?: string;
  permissionExplanation?: string;

  // Port Conflict Request Fields
  isPortConflictRequest?: boolean;
  portConflictPort?: number;
  portConflictPid?: number;
  portConflictProcessName?: string;
  thinkingSteps?: string[];
}
