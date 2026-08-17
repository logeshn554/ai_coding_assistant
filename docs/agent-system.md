# Loopix Universal Agent System

Loopix provides a unified multi-agent orchestrator capable of operating across 8 dedicated agent modes with visual timeline execution and self-repair.

## Agent Modes

1. **Ask**: Read-only codebase understanding and technical Q&A.
2. **Plan**: Detailed implementation plan generation without modifying code files.
3. **Assist**: Targeted inline edit suggestions and interactive assistance.
4. **Code**: Feature implementation and code writing.
5. **Debug**: Stack trace analysis, variable inspection, and bug resolution.
6. **Review**: Staff-engineer level code review evaluating security, performance, and correctness.
7. **Architect**: High-level system design and API contract definition.
8. **Autonomous**: End-to-end multi-step task execution with automated verification & repair.

## Execution Lifecycle

```text
UNDERSTAND → PLAN → APPROVAL → EXECUTE → VERIFY → REPAIR → REVIEW → FINAL VERIFY → COMPLETE
```

## Agent Timeline & Observability

The `AgentTimeline` component (`frontend/src/components/chat/AgentTimeline.tsx`) renders real-time progress:
- Live step status (`COMPLETED_VERIFIED`, `REPAIRING`, `WAITING_FOR_APPROVAL`).
- Executed tool commands and changed files.
- Token consumption and USD cost.
- Instant controls to pause, resume, cancel, or rollback tasks.
