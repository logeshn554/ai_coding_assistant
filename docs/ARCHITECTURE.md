# AgentOS System Architecture

AgentOS is a modular operating system core for AI Coding Agents. It abstracts IDE systems into clean, decoupled layers, ensuring type safety, predictable execution boundaries, event-driven integrations, and resource containment.

## 1. High-Level Architectural Flow

The execution cycle of AgentOS requests follows a strict hierarchical layout:

```text
       ┌────────────────────────┐
       │      Kernel Core       │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │   Repository Kernel    │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │    Knowledge Graph     │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │ Context Virtual Memory │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │    Prompt Compiler     │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │      Model Router      │
       └───────────┬────────────┘
                   │
                   ▼
       ┌────────────────────────┐
       │   Execution Engine     │
       └────────────────────────┘
```

---

## 2. Core Architectural Layers

### A. Kernel & Foundation Layer
Manages the lifecycle of services (`IKernelService`), DI bindings (`DIContainer`), standard settings (`IConfig`), event-driven communication (`IEventBus`), and service resolution (`IServiceRegistry`).

### B. Repository Kernel & Knowledge Graph Layer
Responsible for recursion limits, ignoring temp folder directories, detecting language profiles, AST symbol indexing, SQLite caches, imports tracking, and transitive impact-analysis graph trees.

### C. Context & Compiler Layer
Implements virtual memory paging (Hot/Warm/Cold memory pools), LRU evictions to protect token budgets, keyword relevance prioritizing, formatting templates (XML/JSON), and content deduplication.

### D. Provider Router Layer
Selects optimal LLMs (Groq, OpenAI, Anthropic, Gemini, Ollama), handles exponential backoffs, tracks request RPM rate-limit metrics, manages dynamic fallbacks, and executes streams.

### E. Execution & Learning Layer
Enforces transactional edits. Changes are buffered in-memory, parsed with AST checks for syntax correctness, verified for merge conflicts, committed atomically, or rolled back. Learns from successful fixes, conventions, patterns, and run metrics.
