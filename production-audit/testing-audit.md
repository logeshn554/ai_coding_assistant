# Testing Audit — DevPilot IDE Platform

This document summarizes the current test suite coverage, categorizes the existing test files, and identifies critical gaps that must be addressed for production readiness.

---

## 1. Test Suite Categorization

The test suite resides in the root `tests/` directory:

| Test File Name | Category | Scope Verified |
| :--- | :--- | :--- |
| **test_adversarial_hardening.py** | Security | Path traversal, symlink escapes, shell metacharacter blocking. |
| **test_security_fuzzing.py** | Security | Input fuzzing on file path resolutions. |
| **test_unified_agent_runtime.py** | Agent Runtime | State machine transitions and loop limits. |
| **test_agent_contracts.py** | Verification | Evaluation of goals against contract boundaries. |
| **test_event_system.py** | Infrastructure | Pub/Sub EventBus event emissions. |
| **test_checkpoint_manager.py** | Git / Workspace | File backups and Git rollback checkpoints. |
| **test_context_engine.py** | Context / RAG | AST parsing, symbol indexing, and document retrieval. |
| **test_workspace.py** | Filesystem | Directory listings and file exclusions. |

---

## 2. Gaps in Test Coverage

While the current suite has good validation for basic security escapes and parsing:

1. **Zero Concurrency / Multi-User Tests:**
   - There are no tests verifying parallel requests from two different sessions targeting two different workspaces.
   - Leakage of `WorkspaceState` or `PermissionManager` in-memory mappings is completely unvalidated under load.
2. **No PostgreSQL Concurrency Tests:**
   - All tests run against SQLite. We lack verification for PostgreSQL transactions, row locks, foreign key constraints, or optimistic concurrency handling.
3. **No Worker Crash Recovery Tests:**
   - We lack tests verifying that an interrupted agent run (e.g., simulating worker SIGKILL) can safely resume execution from the last durable checkpoint or step.
4. **No Sandbox Escape or Network Policy Tests:**
   - Playwright is used, but there are no tests verifying that browser profile sessions are strictly separated.
   - There are no automated verification checks for network policy blocks (e.g. restricting metadata endpoints).
