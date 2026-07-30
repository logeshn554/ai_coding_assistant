# AgentOS Interface Declarations

This document logs the public interfaces defined under `agent_os/` to enforce decoupling.

## 1. Core Interfaces (`agent_os/core/interfaces.py`)
*   `IServiceRegistry`: Singleton & factory registries.
*   `IEventBus`: Async event pub-sub.
*   `ILogger`: Standard levels formatting.
*   `IConfig`: Dictionary config parameters.

## 2. Repository Interfaces (`agent_os/repository/interfaces.py`)
*   `IRepository`: Workspace scanner symbol queries.
*   `ISourceControl`: Git status files lookups.

## 3. Context Interfaces (`agent_os/context/interfaces.py`)
*   `IContextEngine`: Token budget estimators.
*   `IContextManager`: Virtual memory context management.

## 4. Compiler Interfaces (`agent_os/compiler/interfaces.py`)
*   `IPromptCompiler`: Deduplication and model profile formatting.

## 5. Providers Interfaces (`agent_os/providers/interfaces.py`)
*   `IModelRouter`: Provider selectors, retries, and RPM limiters.

## 6. Kernel Interfaces (`agent_os/kernel/interfaces.py`)
*   `IKernel`: System bootstrap operations.
*   `ITaskStateMachine`: Task state progressions and rollbacks.
*   `ITaskStateObserver`: Transition notifications.

## 7. Skills Interfaces (`agent_os/skills/interfaces.py`)
*   `ISkill`: Specialist plugin executing logic.
*   `ISkillScheduler`: Mapping and launching plugins.

## 8. Execution Interfaces (`agent_os/execution/interfaces.py`)
*   `ITransaction`: Transaction editing buffers.
*   `ITransactionalExecutionEngine`: Validation engines.

## 9. Learning Interfaces (`agent_os/learning/interfaces.py`)
*   `ILearningEngine`: Storing and querying structured cache items.
*   `IMemoryManager`: Managing active plans, tasks, diagnostics.
*   `IPerformanceOptimizer`: Tracking latencies and suggestions.
