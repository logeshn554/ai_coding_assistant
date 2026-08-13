# Component Inventory — DevPilot IDE Platform

This document inventories the codebase components of the DevPilot platform and clarifies canonical implementations versus duplicate/legacy paths.

---

## 1. Directory Inventory

| Component Directory | Purpose / Category | Key Source Files |
| :--- | :--- | :--- |
| **backend/app/routes/** | FastAPI REST & WS Router layer | [chat.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/chat.py), [files.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/files.py), [lsp.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/lsp.py) |
| **backend/app/session/** | User session logic & queue worker | [agent_session.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/session/agent_session.py) |
| **backend/app/agent/agent_runtime/** | Canonical execution machine & tools | [runtime.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/runtime.py), [tool_executor.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/tool_executor.py) |
| **backend/app/agent/security/** | Security authority layer | [permission_engine.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/permission_engine.py), [workspace_guard.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/workspace_guard.py) |
| **backend/app/tools/** | Specialized tool actions | [terminal_tool.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/tools/terminal_tool.py), [write_tool.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/tools/write_tool.py) |
| **backend/app/adapters/** | Model routing & providers | [router.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/adapters/router.py), [llm.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/adapters/llm.py) |
| **frontend/src/** | React Frontend IDE | `core/ai/AIContext.tsx`, `components/editor/EditorArea.tsx` |
| **tests/** | Test Suite | `test_event_system.py`, `test_workspace.py` |

---

## 2. Canonical vs. Duplicate/Legacy Paths

| Component | Canonical Implementation | Duplicate / Legacy Paths | Risk |
| :--- | :--- | :--- | :--- |
| **Permission Guard** | [PermissionEngine](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/permission_engine.py) | [PermissionManager](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/permissions.py) | **Split security states:** Non-agent commands bypass `PermissionEngine` and resolve against `PermissionManager` policies. |
| **Tool Execution** | [ToolExecutor](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/tool_executor.py) | [dispatcher.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/tools/dispatcher.py) | **Partial audit logs:** Dispatcher bypasses validation and handles recovery logic natively without structured execution records. |
| **Workspace Safety** | [WorkspaceGuard](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/workspace_guard.py) | `safe_path` in [files.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/files.py) | **Directory escapes:** `safe_path` checks path hierarchy via `is_relative_to` but omits `os.path.realpath` checks for resolving external symlinks. |
| **Cost Tracking** | [CostAnalyticsTracker](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/cost_analytics.py) | `total_cost_usd` inside `AgentSession` | **State loss:** Both trackers reside in volatile memory and are lost on worker crash/restarts. |
