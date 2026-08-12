# Architecture Documentation — DevPilot AI-Native IDE Platform

## Overview

DevPilot is an AI-native developer environment powered by a unified, secure, fail-closed agent architecture.

## System Layers

```text
IDE UI (React / TypeScript)
        ↓
Agent Session API (FastAPI / WebSocket)
        ↓
AgentRuntime (Single Orchestration Authority)
   ├── TaskContract & ExecutionPlan (autonomous/)
   ├── ContextEngine & SymbolGraph (context_engine/)
   ├── PermissionEngine & Sandboxing (security/)
   └── ToolExecutor & Verification (tool_executor.py, verification_engine.py)
        ↓
Target Workspace Filesystem / Subprocesses / Git
```

## Key Components

1. **AgentRuntime** ([runtime.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/runtime.py)): Canonical state machine driving execution (`IDLE` → `PLANNING` → `EXECUTING` → `WAITING_FOR_APPROVAL` → `VERIFYING` → `REPAIRING` → `COMPLETED_VERIFIED`).
2. **ContextEngine** ([context_engine.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/context_engine/context_engine.py)): Layered L0–L4 context assembly with SymbolGraph, HybridRanker, and ProjectMemory.
3. **PermissionEngine** ([permission_engine.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/permission_engine.py)): Single authority enforcing fail-closed security, path traversal boundaries, secret redaction, and command risk approvals.
4. **Verification & Self-Repair** ([self_repair.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/autonomous/self_repair.py)): Bounded self-repair loop with failure classification and loop detection.
