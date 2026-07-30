# AgentOS Subsystem Modules

This document details the code directories and modules inside `agent_os/`.

## 1. Directory Structure

```text
agent_os/
├── core/             # Base config, event bus, registry, logger, DI container
├── repository/       # Repository scanning, AST parsers, SQL db, knowledge graph
├── context/          # Virtual memory, Hot/Warm/Cold pools, LRU eviction manager
├── compiler/         # Prompt compilation, deduplication, relevance scoring
├── providers/        # LLM connections, fallbacks, retries, RPM rate limiters
├── kernel/           # Operating system bootstrap kernel, Task state machine
├── skills/           # Independent plugins (Rename, TestGen, FixImport, etc.)
├── execution/        # Transactional engine, merge conflicts, syntax verification
└── learning/         # Performance optimizer, learning engine, fixes cache database
```

---

## 2. Module Responsibilities

| Module | Purpose | Key Classes |
|---|---|---|
| **core** | Low-level OS dependencies | `DIContainer`, `EventBus`, `ServiceRegistry`, `StandardLogger` |
| **repository** | Structural parsing | `RepositoryKernel`, `DatabaseManager`, `RepositoryKnowledgeGraph` |
| **context** | Memory budget containment | `VirtualMemoryContextManager` |
| **compiler** | Prompt optimizations | `PromptCompiler` |
| **providers** | External APIs routing | `ModelRouter` |
| **kernel** | OS lifecycle control | `Kernel`, `TaskStateMachine` |
| **skills** | Task plugins execution | `SkillScheduler`, `RenameSymbolSkill`, `GenerateTestSkill` |
| **execution** | Safe file transaction edits | `TransactionalExecutionEngine`, `FileTransaction` |
| **learning** | Execution stats and cache queries | `LearningEngine`, `PerformanceOptimizer`, `MemoryKernelManager` |
