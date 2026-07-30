# Phase 2: Repository Kernel

## Goal
Build index parsing engines scanning the workspace into metadata caches.

## Achievements
*   Implemented SQLite cache schema manager (`DatabaseManager`) in `agent_os/repository/db.py`.
*   Implemented Python AST parser and fallback regex parsers in `agent_os/repository/parser.py`.
*   Implemented `RepositoryKernel` workspace walking and exclusion rules in `agent_os/repository/repository.py`.

## Verification
*   `test_repository.py`
