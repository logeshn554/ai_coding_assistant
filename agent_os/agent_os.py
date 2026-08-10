import os
import asyncio
from typing import Any, Dict, List, Callable, Coroutine, Optional

from agent_os.core.logging import StandardLogger
from agent_os.core.config import DictionaryConfig
from agent_os.core.event_bus import EventBus
from agent_os.core.registry import ServiceRegistry
from agent_os.core.di import DIContainer
from agent_os.core.cache import CacheService

# Kernel services
from agent_os.kernel.kernel import Kernel
from agent_os.kernel.scheduler import DependencyScheduler
from agent_os.kernel.budget_manager import BudgetManager
from agent_os.kernel.health_monitor import HealthMonitor
from agent_os.kernel.cancellation_manager import CancellationManager
from agent_os.kernel.policy_engine import PolicyEngine
from agent_os.kernel.reasoning import ReasoningEngine


# Infrastructure services
from agent_os.infrastructure.distributed_tracing import DistributedTracer
from agent_os.infrastructure.durable_event_bus import DurableEventBus
from agent_os.infrastructure.workflow_store import WorkflowStore
from agent_os.infrastructure.audit_store import AuditStore
from agent_os.infrastructure.secret_store import SecretStore
from agent_os.infrastructure.metrics import MetricsCollector
from agent_os.infrastructure.observability import Observability

# Subsystems
from agent_os.context.context_manager import WorkspaceContextManager
from agent_os.repository.repository import RepositoryKernel
from agent_os.repository.file_operations import FileOperations
from agent_os.repository.interfaces import IRepositoryKnowledgeGraph, ISourceControl
from agent_os.repository.graph import RepositoryKnowledgeGraph
from agent_os.repository.git_provider import GitSourceControl
from agent_os.learning.engine import LearningEngine
from agent_os.learning.interfaces import IMemoryManager, IPerformanceOptimizer
from agent_os.learning.memory_kernel import MemoryKernelManager
from agent_os.learning.optimizer import PerformanceOptimizer
from agent_os.execution.engine import TransactionalExecutionEngine
from agent_os.execution.lock_manager import FileLockManager
from agent_os.execution.interfaces import ISandbox
from agent_os.execution.sandbox import create_sandbox
from agent_os.compiler.prompt_compiler import PromptCompiler
from agent_os.skills.orchestrator import SkillOrchestrator
from agent_os.skills.plugins import (
    RenameSymbolSkill,
    GenerateTestSkill,
    FixImportSkill,
    ReviewPatchSkill,
    RefactorMethodSkill,
    OptimizeSQLSkill,
    UpdateDependencySkill,
    SecurityScanSkill,
    IDEContext
)

class OSStatus(dict):
    """Custom dict subclass returning a clean string representation for AgentOS status."""
    def __str__(self) -> str:
        return (
            f"AgentOS Status: {self.get('status')} | "
            f"Workspace: {self.get('workspace_root')} | "
            f"Tokens: {self.get('current_tokens')}/{self.get('token_budget')}"
        )

    def __repr__(self) -> str:
        return self.__str__()


class AgentOS:
    """Unified AgentOS v2 Facade coordinating IDE, Parallel DAG Scheduler, and Repository scanning."""
    def __init__(
        self,
        workspace_root: str,
        db_path: str = ":memory:",
        token_budget: int = 8000,
        concurrency_limit: int = 4
    ) -> None:
        self.workspace_root = workspace_root
        self.db_path = db_path
        self.token_budget = token_budget
        self.concurrency_limit = concurrency_limit

        # Core Utilities
        self.logger = StandardLogger()
        self.config = DictionaryConfig({
            "workspace_root": workspace_root,
            "db_path": db_path,
            "token_budget": token_budget,
            "concurrency_limit": concurrency_limit
        })
        self.event_bus = EventBus()
        self.registry = ServiceRegistry()
        self.di_container = DIContainer(self.registry)

        # Architectural Subsystems
        self.cache = CacheService()
        self.scheduler = DependencyScheduler(concurrency_limit)
        self.context_manager = WorkspaceContextManager(workspace_root, token_budget)
        self.repository = RepositoryKernel(db_path)
        self.file_operations = FileOperations(workspace_root)
        self.knowledge_graph = RepositoryKnowledgeGraph(self.repository)
        self.source_control = GitSourceControl(workspace_root)
        self.learning_engine = LearningEngine(db_path)
        self.execution_engine = TransactionalExecutionEngine(self.registry)
        self.prompt_compiler = PromptCompiler()
        self.skill_orchestrator = SkillOrchestrator()

        # Kernel & Infrastructure Services (Clean DI instantiation)
        self.budget_manager = BudgetManager()
        self.health_monitor = HealthMonitor()
        self.cancellation_manager = CancellationManager()
        self.policy_engine = PolicyEngine(workspace_root)
        self.distributed_tracer = DistributedTracer()
        self.durable_event_bus = DurableEventBus()
        self.workflow_store = WorkflowStore()
        self.audit_store = AuditStore()
        self.secret_store = SecretStore()
        self.metrics_collector = MetricsCollector()
        self.observability = Observability()
        self.lock_manager = FileLockManager()
        self.memory_manager = MemoryKernelManager()
        self.performance_optimizer = PerformanceOptimizer()
        
        # Facade aliases for explicit Memory vs Learning separation
        self.memory = self.memory_manager
        self.optimizer = self.performance_optimizer

        self.reasoning_engine = ReasoningEngine(self.registry)



        self._booted = False

    async def boot(self) -> None:
        if self._booted:
            return

        self.logger.info("Booting AgentOS v2 Facade...")

        # 1. Register Singletons in DI Container
        self.registry.register_singleton(StandardLogger, self.logger)
        self.registry.register_singleton(DictionaryConfig, self.config)
        self.registry.register_singleton(EventBus, self.event_bus)
        self.registry.register_singleton(CacheService, self.cache)
        self.registry.register_singleton(DependencyScheduler, self.scheduler)
        self.registry.register_singleton(WorkspaceContextManager, self.context_manager)
        self.registry.register_singleton(RepositoryKernel, self.repository)
        self.registry.register_singleton(FileOperations, self.file_operations)
        self.registry.register_singleton(LearningEngine, self.learning_engine)
        self.registry.register_singleton(TransactionalExecutionEngine, self.execution_engine)
        self.registry.register_singleton(PromptCompiler, self.prompt_compiler)
        self.registry.register_singleton(SkillOrchestrator, self.skill_orchestrator)

        # Register Kernel & Infrastructure Singletons
        self.registry.register_singleton(BudgetManager, self.budget_manager)
        self.registry.register_singleton(HealthMonitor, self.health_monitor)
        self.registry.register_singleton(CancellationManager, self.cancellation_manager)
        self.registry.register_singleton(PolicyEngine, self.policy_engine)
        self.registry.register_singleton(DistributedTracer, self.distributed_tracer)
        self.registry.register_singleton(DurableEventBus, self.durable_event_bus)
        self.registry.register_singleton(WorkflowStore, self.workflow_store)
        self.registry.register_singleton(AuditStore, self.audit_store)
        self.registry.register_singleton(SecretStore, self.secret_store)
        self.registry.register_singleton(MetricsCollector, self.metrics_collector)
        self.registry.register_singleton(Observability, self.observability)
        self.registry.register_singleton(FileLockManager, self.lock_manager)
        self.registry.register_singleton(IRepositoryKnowledgeGraph, self.knowledge_graph)
        self.registry.register_singleton(RepositoryKnowledgeGraph, self.knowledge_graph)
        self.registry.register_singleton(ISourceControl, self.source_control)
        self.registry.register_singleton(GitSourceControl, self.source_control)
        self.registry.register_singleton(ReasoningEngine, self.reasoning_engine)
        self.registry.register_singleton(IMemoryManager, self.memory_manager)
        self.registry.register_singleton(MemoryKernelManager, self.memory_manager)
        self.registry.register_singleton(IPerformanceOptimizer, self.performance_optimizer)
        self.registry.register_singleton(PerformanceOptimizer, self.performance_optimizer)





        # Register Sandbox factory for auto-wiring ISandbox instances
        self.registry.register_factory(ISandbox, lambda: create_sandbox(
            use_docker=None,
            workspace_root=self.workspace_root,
            registry=self.registry
        ))

        # 2. Boot up core Kernel services
        self.kernel = Kernel(self.registry, self.event_bus, self.config, self.logger)
        self.kernel.boot()

        # Update PolicyEngine workspace root
        self.policy_engine.workspace_root = self.workspace_root

        # 3. Register default IDE specialist skills
        self.skill_orchestrator.register_skill("rename_symbol", RenameSymbolSkill())
        self.skill_orchestrator.register_skill("generate_test", GenerateTestSkill())
        self.skill_orchestrator.register_skill("fix_import", FixImportSkill())
        self.skill_orchestrator.register_skill("review_patch", ReviewPatchSkill())
        self.skill_orchestrator.register_skill("refactor_method", RefactorMethodSkill())
        self.skill_orchestrator.register_skill("optimize_sql", OptimizeSQLSkill())
        self.skill_orchestrator.register_skill("update_dependency", UpdateDependencySkill())
        self.skill_orchestrator.register_skill("security_scan", SecurityScanSkill())

        # 4. Perform parallel workspace index scan
        if self.workspace_root and os.path.exists(self.workspace_root):
            self.logger.info(f"Scanning workspace: {self.workspace_root}")
            await self.repository.scan_workspace_parallel(self.workspace_root)

        self._booted = True
        self.logger.info("AgentOS v2 successfully booted.")

    def status(self) -> OSStatus:
        return OSStatus({
            "status": "booted" if self._booted else "pending",
            "workspace_root": self.workspace_root,
            "token_budget": self.token_budget,
            "current_tokens": self.context_manager.estimate_tokens(),
            "concurrency_limit": self.concurrency_limit,
            "total_files_indexed": len(self.repository.list_files()) if self._booted else 0
        })

    async def run_skills_parallel(self, skill_names: List[str], context: IDEContext) -> IDEContext:
        """Runs multiple skills concurrently with deep-copied contexts."""
        if not self._booted:
            raise RuntimeError("AgentOS is not booted. Call await boot() first.")
        return await self.skill_orchestrator.run_parallel(skill_names, context)

    async def run_tasks(
        self,
        tasks: List[Dict[str, Any]],
        execute_task_fn: Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]
    ) -> Dict[str, Any]:
        """Schedules and runs tasks concurrently respecting their DAG dependencies."""
        if not self._booted:
            raise RuntimeError("AgentOS is not booted. Call await boot() first.")
        return await self.scheduler.execute_graph(tasks, execute_task_fn)

    async def execute_goal(
        self,
        goal: str,
        task_graph: Optional[List[Dict[str, Any]]] = None,
        execute_task_fn: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, Any]]] = None,
        repair_fn: Optional[Callable[[Dict[str, Any], Exception], Coroutine[Any, Any, Any]]] = None
    ) -> Dict[str, Any]:
        """Runs the complete step-by-step reasoning loop for the user goal."""
        if not self._booted:
            raise RuntimeError("AgentOS is not booted. Call await boot() first.")
        return await self.reasoning_engine.run_goal(
            goal=goal,
            task_graph=task_graph,
            execute_task_fn=execute_task_fn,
            repair_fn=repair_fn
        )


    def shutdown(self) -> None:
        if not self._booted:
            return
        self.kernel.shutdown()
        self.cache.clear()
        self._booted = False
