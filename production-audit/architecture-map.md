# Architecture Map — DevPilot IDE Platform

This document diagrams and traces the lifecycle of user prompts, agent decisions, and tool executions throughout the DevPilot codebase.

---

## 1. Request Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as Frontend IDE (React)
    participant API as FastAPI Gateway
    participant Session as AgentSession (Queue Worker)
    participant Runtime as AgentRuntime (State Machine)
    participant Context as ContextEngine (Chroma/Parser)
    participant LLM as ModelRouter / ModelGateway
    participant Executor as ToolExecutor
    participant Policy as PermissionEngine / WorkspaceGuard
    participant Sandbox as Sandbox Worker (Docker / Local OS)

    User->>API: Connect WebSocket /ws/chat (Ticket/Token Auth)
    API->>Session: Instantiate AgentSession & load history
    User->>API: Send "user_message" event
    API->>Session: Enqueue message in Sequential FIFO Queue
    Note over Session: sequential worker wakes up

    alt Mode Heuristics or Classifier selects "Ask" / "Plan"
        Session->>LLM: Stream turn-based completion
        LLM->>User: Stream text deltas (live feedback)
    else Mode Classifier selects "Agent" / "Goal"
        Session->>Runtime: Trigger AgentRuntime.run()
        Runtime->>Context: Build workspace symbol & text context
        Context-->>Runtime: Return token-bounded context
        
        loop turns <= max_turns
            Runtime->>LLM: Request next action step (prompt + tools schema)
            LLM-->>Runtime: Return thought + structured ToolCall(s)
            
            Runtime->>Executor: execute(tool_call_id, arguments)
            Executor->>Policy: evaluate_tool_call()
            Note over Policy: Enforce WorkspaceGuard boundary check & sandbox rules
            
            alt Policy Denied
                Policy-->>Executor: Return Security Block
                Executor-->>Runtime: ToolResult(success=False, error="Security Policy Denied")
            else Policy Approved
                Executor->>Sandbox: Execute Tool (e.g. read_file, run_command)
                Sandbox-->>Executor: Return stderr/stdout/file content
                Executor-->>Runtime: ToolResult(success=True, output=str)
            end
            
            Runtime-->>Session: Emit AgentEvent (EVENT_TOOL_COMPLETED)
            Session-->>User: Broadcast WebSocket status & tool results
        end
    end
    
    Session->>User: Broadcast "session_done" with cost & wasted turns
```

---

## 2. Alternate Execution Paths (Audited)

We audited the codebase for paths that bypass the canonical flow:

1. **Bypassing `AgentRuntime`:**
   - **Heuristic routing in `AgentSession.handle_user_message`:** When the user query is classified as `"Ask"` or `"Plan"`, the session executes a local tool-calling loop directly inside `agent_session.py` (lines 1238–1300).
   - **Impact:** This bypasses the canonical `AgentRuntime` state machine (e.g. `AgentState` transition validations are omitted or handled loosely), leading to inconsistent event emissions.
2. **Bypassing `ToolExecutor` / `PermissionEngine`:**
   - **Direct tool imports inside other tools:** For example, `dispatcher.py` handles some MCP and agent delegation calls locally instead of piping them through `ToolExecutor.execute()`. This bypasses `PermissionEngine`'s pre-evaluation checks.
3. **Bypassing `WorkspaceGuard`:**
   - **Direct file access in routers:** Route handlers like [routes/files.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/files.py) and [routes/git.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/git.py) use `safe_path` from [files.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/files.py) to resolve paths, which resolves relative paths but does not perform symlink checks or use the canonical `WorkspaceGuard` object.

---

## 3. Asynchronous Execution & Event Routing

- **WebSocket Connection:** Established via `APIRouter.websocket("/ws/chat")` in [chat.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/chat.py). Events are serialized to JSON.
- **FIFO Task Queue:** `AgentSession` implements `asyncio.Queue(maxsize=10)` to buffer client messages. A dedicated worker task runs sequentially to prevent overlapping agent calls.
- **Event Bus:** An `EventBus` class in [orchestrator.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/orchestrator.py) handles pub/sub events locally in memory.
