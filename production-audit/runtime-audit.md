# Runtime Audit — DevPilot IDE Platform

This document details the audit of the core AgentRuntime execution loops, state machine transitions, cancellation robustness, self-repair loops, and verification engines.

---

## 1. State Machine & Transitions

The agent loop transitions are governed by `VALID_TRANSITIONS` defined in [runtime.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/agent_runtime/runtime.py).

- **Strictness:** `transition_state` raises `InvalidStateTransitionError` if a violation occurs. An explicit emergency transition to `AgentState.CANCELLED` bypasses the checks.
- **Robustness Gaps:**
  - **No PAUSE state:** The state machine does not have a `PAUSED` state. Pausing is impossible.
  - **No recovery path from BLOCKED:** If a state transitions to `BLOCKED`, the execution is aborted. No resume paths exist.

---

## 2. Cancellation Mechanics

- **Trigger:** In [chat.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/routes/chat.py), `cancel_generation` triggers `session.cancel_all()`.
- **Flow:**
  - `cancel_all()` calls `self.agent_runtime.cancel(self.session_id)`.
  - It sets `cancel_event: asyncio.Event` associated with the session.
  - It attempts to kill terminal processes by calling `p.stop()` on running processes.
- **Weakness (Synchronous Blocks):** If the agent is in the middle of a blocking filesystem read/write or a sync network request, the cancellation event is not checked until the current awaitable completes.

---

## 3. Worker Crash Recovery & Job Leases

- **Authoritative state is in-memory:** All active sessions (`_sessions`), cancellation events (`_cancellation_events`), and asyncio task references (`_active_tasks`) reside in static class dictionary variables of `AgentRuntime`.
- **No Worker Leases:** There are no worker leases or heartbeat mechanisms.
- **Crash Behavior:** If a FastAPI worker process restarts or crashes:
  1. The client's WebSocket connection drops.
  2. The running `asyncio.Task` executing the agent loop is abruptly killed.
  3. When the user reconnects, they hit a blank `AgentRuntime` instance that has no memory of the previous run state. The UI remains stuck in a loading state or falls back to `IDLE`.

---

## 4. Self-Repair and Loop Detection

- **Mechanism:** If verification fails, the system transitions to `AgentState.REPAIRING` and invokes the `DebuggingAgent`.
- **Limit:** Bounded by `max_turns`. If the agent enters an infinite flip-flop cycle (fixing bug A, which creates bug B, and then fixing bug B which restores bug A), it will continue until `max_turns` (default 25) is fully exhausted.
- **Impact:** This burns significant LLM tokens.
- **Mitigation:** We need an explicit, independent `max_repair_attempts` counter (suggested threshold: 3–5 attempts) that aborts and enters `FAILED` state if exceeded.
