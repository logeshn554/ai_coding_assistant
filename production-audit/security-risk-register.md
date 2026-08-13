# Security Risk Register — DevPilot IDE Platform

This register documents current security vulnerabilities, severity levels, and proposed mitigations for the DevPilot platform.

---

## P0 — Critical Security / Data Loss / Production-Blocking

### P0-001: Host Compromise / Sandbox Escape
- **Component:** Terminal Execution & Sandboxing
- **Problem:** When `settings.USE_SANDBOX` is disabled or the Docker daemon is unreachable, the system silently falls back to running commands directly on the host operating system with control-plane privileges. Even when Docker is active, the tool mounts the entire host workspace root as a read-write volume (`-v host_root:/workspace`), allowing a malicious repository script to write files (e.g., cron jobs, ssh authorized_keys, bashrc) back to the host system.
- **Impact:** Complete host system compromise, privilege escalation, and cross-tenant server control.
- **Recommended Fix:** Enforce a hard sandbox execution constraint. Reject fallback execution on the host. Run sandbox execution in fully isolated VM containers or gVisor runtimes with strict read-only volume mounts for system files.

---

### P0-002: Path Traversal via Symlink Manipulation
- **Component:** Filesystem Utility (`safe_path` in `files.py`)
- **Problem:** `safe_path` uses `is_relative_to` on absolute paths of the target files but does not resolve symlinks using `os.path.realpath` before check. If the workspace contains a symlink pointing to an absolute host path (e.g. `/etc/` or `C:/Windows`), the agent can read and write files outside the workspace root.
- **Impact:** Sensitive host file disclosure and arbitrary file write capabilities.
- **Recommended Fix:** Use canonical realpath checks inside `safe_path` to resolve symlinks before checking boundaries, mirroring [WorkspaceGuard](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/workspace_guard.py).

---

### P0-003: Authorization Bypass in ToolExecutor
- **Component:** [tool_executor.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/tool_executor.py)
- **Problem:** If a tool call requires user approval (`decision.requires_approval` is True), `ToolExecutor.execute` sets the session state to `AgentState.WAITING_FOR_APPROVAL` (lines 230–233) but then immediately proceeds to execute the tool via `self._dispatch` without waiting for the user to approve or click anything.
- **Impact:** Complete bypass of approval policies in autonomous agent mode; high-risk tools (like command execution) run immediately without user consent.
- **Recommended Fix:** Implement an asynchronous event suspend-and-resume mechanism inside `ToolExecutor` that halts thread execution and awaits the WebSocket approval event before dispatching.

---

### P0-004: Missing Tenant Isolation & Cross-Session Access
- **Component:** Routing and State Management
- **Problem:** WebSocket connections at `/ws/chat` authorize connection tickets but do not check whether the requested `session_id` belongs to the authenticated user's organization or tenant. Furthermore, `WorkspaceState` falls back to `_default_root` if session keys are evicted or missing.
- **Impact:** Cross-user data leakage and unauthorized workspace manipulation.
- **Recommended Fix:** Introduce explicit tenant IDs (`tenant_id`) and organization boundaries on all schema endpoints and WebSocket requests. Verify session ownership on every connection.

---

## P1 — High-Impact Reliability and Architecture Issues

### P1-001: Volatile Global State & Race Conditions
- **Component:** [state.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/state.py)
- **Problem:** Global variables like `_permission_managers`, `_ws_tickets`, and `workspace_state._session_roots` are tracked in ordinary Python dictionaries. In a multi-user environment running multiple worker processes (e.g., Gunicorn/Uvicorn workers), this state is not synchronized across worker processes.
- **Impact:** Disconnected sessions, invalid connection state, and race conditions where user requests hit different workers that lack their session details.
- **Recommended Fix:** Migrate transient session states, locks, and connection tickets to Redis.

---

### P1-002: In-Memory Loss of Authoritative Agent State
- **Component:** [runtime.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/runtime.py)
- **Problem:** Active agent tasks, sessions, and cancellation states are stored in process-local class dictionaries (`_sessions`, `_active_tasks`, `_cancellation_events` in `AgentRuntime`). If a worker restarts, crashes, or times out, the entire session state is wiped.
- **Impact:** Lost agent runs, broken recovery loops, and client UI synchronization errors.
- **Recommended Fix:** Persist AgentRun, AgentTask, and AgentStep states transactionally in PostgreSQL and use Redis for job queues and heartbeats.
