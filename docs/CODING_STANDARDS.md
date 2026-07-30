# AgentOS Developer Coding Standards

This document establishes the patterns, code conventions, and safety guidelines for the AgentOS project.

## 1. Type Annotations & Declarations
*   All methods must be fully typed (arguments and return types).
*   Enforce type checking: avoid usage of `Any` where generic structures (e.g. `Dict[str, Any]` or `List[str]`) are more appropriate.

## 2. Decoupling & Interfaces
*   Subsystems must never communicate directly. Every module must query dependency bindings through the DI container (`IContainer`) and interfaces.
*   Class components must declare camelCase compatibility aliases alongside standard snake_case operations.

## 3. Transaction Safety (Never Write Directly)
*   Edits must be buffered in-memory within a transaction block (`ITransaction`).
*   Always perform a syntax check on modified code blocks (e.g. `ast.parse` for python files) before executing disk replacements.
*   Transactions must execute atomically via temporary files and `os.replace`.

## 4. Testing
*   Every feature must be covered by a dedicated unit test suite in `agent_os/tests/`.
*   Verify code runs cleanly under `pytest` with zero warnings or errors.
