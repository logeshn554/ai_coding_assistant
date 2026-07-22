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
  content?: string | Record<string, unknown>;
  tool_calls?: ToolCall[];
  diff?: { filename: string; hunks: DiffHunk[] };
  cost_usd?: number;
  agents_used?: number;
  elapsed_ms?: number;

  tool_call_id?: string;
  name?: string;
  status?: 'success' | 'error';
  isConfirmPending?: boolean;
  confirmArgs?: Record<string, unknown>;
  confirmDiff?: {
    path: string;
    original: string;
    proposed: string;
    hunks?: DiffHunk[];
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

// ── Entity interfaces replacing any[] ──────────────────────────────────────

export interface Session {
  id: string;
  title: string;
  updated_at?: string;
}

export interface ProcessEntry {
  id: string;
  name: string;
  command?: string;
  status?: 'starting' | 'running' | 'stopped' | 'error';
  pid?: number;
  port?: number;
}

export interface SubTask {
  id: number;
  agent: string;
  description: string;
  status: 'pending' | 'running' | 'done' | 'error';
  dependencies: number[];
  output?: string;
}
