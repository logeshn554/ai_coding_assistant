export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string | any;
  tool_calls?: any[];
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
}
