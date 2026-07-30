# AgentOS Development Roadmap

This document outlines the phased progress and future objectives for the AgentOS system.

## Phased Achievements

### Phase 1: Architectural Foundation
*   Established standard dependency injection (`DIContainer`), configuration systems, event buses, logging interfaces, and service registries.

### Phase 2: Repository Parsing & Scanning
*   Coded AST and regex scanners storing repository file structures and import trees in SQLite.

### Phase 3: Knowledge Graph Relationships
*   Mapped Call Graphs, imports, and recursive Transitive Impact Analyses.

### Phase 4: Structured Memory Kernel
*   Coded memory management for plans, events, diagnostics, patches, and atomic JSON persistence.

### Phase 5: Prioritized Virtual Memory Context
*   Developed Hot, Warm, Cold context pools with LRU evictions to fit token budgets.

### Phase 6: Prompt Optimizations & Deduplication
*   Added keyword relevance scoring and skip-duplicates logic in Prompt Compiler.

### Phase 7: Dynamic Provider Routing
*   Created model capability router supporting Groq, OpenAI, Anthropic, Gemini, and Ollama, with RPM limits and fallback channels.

### Phase 8: Task State Machine
*   Enforced task states (`NEW`, `PLAN`, `EDIT`, `DONE`, etc.) with transition rules and rollback stacks.

### Phase 9: Specialist Skill Scheduler
*   Coded state-based skill execution pipelines (Rename Symbol, Generate Test, SQL Optimizer, etc.).

### Phase 10: Transactional Execution Engine
*   Enforced syntax AST validations and atomic file replacements.

### Phase 11: Learning Engine
*   Mapped SQLite fix caches and Jaccard overlap similarity retrieval.

### Phase 12: Performance Optimizer
*   Monitored latency, sizes, retries, and generated suggestions.

### Phase 13: End-To-End API AI Integration
*   Unified all subsystems.

---

## Future Goals

1.  **LSP Integration**: Hook the Repository Kernel AST indexing directly to active Language Server Protocol diagnostics.
2.  **Sandbox Isolation**: Connect the Execution Engine to dockerized container runtime environments for safe code compilation.
