# Security Risk Register — DevPilot IDE Platform

This register documents security evaluations, verified mitigations, and current resolution statuses for the DevPilot platform.

---

## Risk Status Summary

| Risk ID | Title | Severity | Status | Verified Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **P0-001** | Host Compromise / Sandbox Escape | P0 (Critical) | ✅ **MITIGATED** | `terminal_tool.py` strictly enforces container sandboxing via `global_sandbox_manager`. Fail-closed on Docker daemon failure without host fallback. |
| **P0-002** | Path Traversal via Symlink Manipulation | P0 (Critical) | ✅ **MITIGATED** | `SecureFileSystem.resolve_safe_path()` resolves canonical `os.path.realpath()` and validates workspace boundary before all reads/writes. |
| **P0-003** | Authorization Bypass in ToolExecutor | P0 (Critical) | ✅ **MITIGATED** | `ToolExecutor` halts execution with `request_tool_confirmation()`, transitions through `WAITING_FOR_APPROVAL` -> `EXECUTING`, and fails closed in headless/unattended modes. |
| **P0-004** | Missing Tenant Isolation & Cross-Session Access | P0 (Critical) | ✅ **MITIGATED** | Workspaces and sessions are strictly scoped to verified `workspace_root` and `session_id`; cross-tenant path escapes are rejected. |
| **P1-001** | Volatile Global State & Race Conditions | P1 (High) | ✅ **MITIGATED** | Distributed job queue (`AgentQueue`), distributed run lock lease (`RunLock`), and event broadcast (`EventPublisher`) are backed by Redis. |
| **P1-002** | In-Memory Loss of Authoritative Agent State | P1 (High) | ✅ **MITIGATED** | `AgentRuntime` transactionally persists state transitions and checkpoints to PostgreSQL (`AgentRun`, `AgentCheckpoint`) with `load_checkpoint` restoration. |

---

## Detailed Vulnerability & Mitigation Records

### P0-001: Host Compromise / Sandbox Escape
- **Status:** ✅ **MITIGATED**
- **Component:** [terminal_tool.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/tools/terminal_tool.py)
- **Mitigation:** Command execution is wrapped in ephemeral container sandboxes using `ExecutionPolicy`. If container initialization fails or Docker is unreachable, the system fails closed with a clear error rather than executing with host privileges.

---

### P0-002: Path Traversal via Symlink Manipulation
- **Status:** ✅ **MITIGATED**
- **Component:** [secure_fs.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/secure_fs.py) & [files.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/files.py)
- **Mitigation:** `safe_path()` delegates to `SecureFileSystem.resolve_safe_path()`, which calls `os.path.realpath()` to resolve all symlink indirection *before* verifying that the target path begins with the canonical workspace root. Traversal attempts raise `PermissionError`.

---

### P0-003: Authorization Bypass in ToolExecutor
- **Status:** ✅ **MITIGATED**
- **Component:** [tool_executor.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/tool_executor.py)
- **Mitigation:** High-risk tool calls evaluate `PermissionEngine`. When approval is required, execution pauses while awaiting user confirmation via `request_tool_confirmation()`. If denied or no interactive confirmation callback is registered, the call fails closed without execution. State transitions cleanly to `AgentState.EXECUTING`.

---

### P0-004: Missing Tenant Isolation & Cross-Session Access
- **Status:** ✅ **MITIGATED**
- **Component:** [runtime.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/runtime.py) & [worker.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/infrastructure/worker.py)
- **Mitigation:** Every session and worker execution strictly binds to an explicit `session_id`, `workspace_root`, and database `AgentRun` entity. Arbitrary file path escapes and undefined workspaces fail closed.

---

### P1-001: Distributed Session State & Distributed Locking
- **Status:** ✅ **MITIGATED**
- **Component:** [worker.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/infrastructure/worker.py) & [queue.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/infrastructure/queue.py)
- **Mitigation:** Multi-worker deployments coordinate via Redis `AgentQueue` and lease distributed `RunLock` tokens. Jobs and events are published and consumed without in-process singleton bottlenecks.

---

### P1-002: Checkpoint & State Persistence
- **Status:** ✅ **MITIGATED**
- **Component:** [runtime.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/runtime.py)
- **Mitigation:** State transitions update the database `AgentRun` row and persist full state JSON (including `error_code`, `verification_status`, and `changed_files`) in `AgentCheckpoint`.
