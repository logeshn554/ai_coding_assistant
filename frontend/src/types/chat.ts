export type AgentStatus = 'idle' | 'running' | 'done' | 'error' | 'waiting';

export interface AgentState {
  agent_type: string;
  status: AgentStatus;
}

export interface AgentCardData {
  id: string;
  name: 'Planner' | 'Coder' | 'Reviewer' | 'Tester' | 'Researcher';
  status: AgentStatus;
  currentTask?: string;
  progress: number; // 0..100
  cpuUsage?: string;
  tokensUsed?: number;
  lastActivity?: string;
}

export interface TimelineStep {
  id: string;
  action: string; // e.g. "Reading package.json", "Editing Login.tsx"
  icon?: string;
  timestamp: string;
  durationMs?: number;
  status: 'running' | 'completed' | 'failed' | 'pending';
  details?: string;
}

export interface ToolExecutionItem {
  id: string;
  tool: 'terminal' | 'file_read' | 'file_edit' | 'git' | 'search' | 'other';
  name: string;
  params?: Record<string, any>;
  status: 'running' | 'success' | 'error';
  durationMs?: number;
  output?: string;
}

export type FileAiDecoration = 'generated' | 'modified' | 'review_needed' | 'build_failed' | 'editing';

export interface FileAiInfo {
  path: string;
  decoration: FileAiDecoration;
  lastEditTime?: string;
  author?: string;
  summary?: string;
  linesAdded?: number;
  linesRemoved?: number;
}

export interface ProjectContextInfo {
  indexedFiles: number;
  totalFiles: number;
  architecture?: string;
  framework?: string;
  language?: string;
  database?: string;
  activeBranch?: string;
  contextSizeBytes?: number;
  tokenUsage: number;
  tokenBudget: number;
}

export interface ProjectMemoryItem {
  id: string;
  category: 'convention' | 'architecture' | 'preference' | 'instruction' | 'ignored';
  title: string;
  content: string;
  enabled: boolean;
}

export interface AiTaskItem {
  id: string;
  title: string;
  phase: 'planning' | 'coding' | 'testing' | 'review' | 'deployment';
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  owner?: string;
  estimatedTime?: string;
  dependencies?: string[];
}

export interface SlashCommand {
  name: string;
  description: string;
  example: string;
}

export interface ContextMention {
  name: string;
  type: 'file' | 'folder' | 'terminal' | 'git' | 'selection' | 'workspace';
  description: string;
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
