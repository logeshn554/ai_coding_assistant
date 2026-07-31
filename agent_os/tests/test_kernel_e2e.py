import os
import pytest
import tempfile
import shutil
from unittest.mock import MagicMock
from agent_os.core.registry import ServiceRegistry
from agent_os.core.event_bus import EventBus as AOSEventBus
from agent_os.core.config import DictionaryConfig
from agent_os.core.logging import StandardLogger
from agent_os.kernel.kernel import Kernel
from agent_os.kernel.state_machine import TaskStateMachine
from agent_os.skills.scheduler import SkillScheduler
from agent_os.execution.engine import TransactionalExecutionEngine
from agent_os.compiler.prompt_compiler import PromptCompiler
from agent_os.context.virtual_memory import VirtualMemoryContextManager
from agent_os.learning.memory_kernel import MemoryKernelManager
from agent_os.learning.engine import LearningEngine
from agent_os.learning.optimizer import PerformanceOptimizer
from agent_os.repository.repository import RepositoryKernel
from agent_os.core.cache import CacheService
from agent_os.execution.lock_manager import FileLockManager
from agent_os.context.context_manager import WorkspaceContextManager
from agent_os.kernel.state_manager import StateManager

# Interfaces
from agent_os.repository.interfaces import IRepository
from agent_os.learning.interfaces import IMemoryManager, ILearningEngine, IPerformanceOptimizer
from agent_os.execution.interfaces import ITransactionalExecutionEngine
from agent_os.compiler.interfaces import IPromptCompiler
from agent_os.providers.interfaces import IModelRouter
from agent_os.kernel.interfaces import ITaskStateMachine
from agent_os.skills.interfaces import ISkillScheduler, ISkill
from agent_os.core.interfaces import ICache
from agent_os.execution.interfaces import IFileLockManager
from agent_os.context.interfaces import IContextManager

def test_kernel_collaboration_e2e():
    # Setup temp workspace dir for databases
    temp_dir = tempfile.mkdtemp()
    repo_db_path = os.path.join(temp_dir, "repo.db")
    learning_db_path = os.path.join(temp_dir, "learning.db")
    memory_json_path = os.path.join(temp_dir, "memory.json")
    
    try:
        registry = ServiceRegistry()
        aos_event_bus = AOSEventBus()
        config = DictionaryConfig({"max_turns": 10})
        logger_os = StandardLogger("AgentOS_E2E")
        
        kernel = Kernel(registry, aos_event_bus, config, logger_os)
        
        # Instantiate services
        repo_kernel = RepositoryKernel(db_path=repo_db_path)
        memory_manager = MemoryKernelManager()
        exec_engine = TransactionalExecutionEngine()
        compiler = PromptCompiler()
        router = MagicMock(spec=IModelRouter)
        state_machine = TaskStateMachine(event_bus=aos_event_bus)
        state_manager = StateManager(state_machine)
        
        scheduler = SkillScheduler()
        learning_engine = LearningEngine(db_path=learning_db_path)
        optimizer = PerformanceOptimizer()
        cache = CacheService()
        lock_manager = FileLockManager()
        context_mgr = WorkspaceContextManager(workspace_root=temp_dir)
        
        # Register singletons
        registry.register_singleton(IRepository, repo_kernel)
        registry.register_singleton(IMemoryManager, memory_manager)
        registry.register_singleton(ITransactionalExecutionEngine, exec_engine)
        registry.register_singleton(IPromptCompiler, compiler)
        registry.register_singleton(IModelRouter, router)
        registry.register_singleton(ITaskStateMachine, state_machine)
        registry.register_singleton(ISkillScheduler, scheduler)
        registry.register_singleton(ILearningEngine, learning_engine)
        registry.register_singleton(IPerformanceOptimizer, optimizer)
        registry.register_singleton(ICache, cache)
        registry.register_singleton(IFileLockManager, lock_manager)
        registry.register_singleton(IContextManager, context_mgr)
        registry.register_singleton(StateManager, state_manager)
        
        # 1. Boot Kernel
        kernel.boot()
        
        # 2. Verify state machine start
        assert state_machine.current_state == "NEW"
        state_machine.transition_to("UNDERSTAND")
        
        # 3. Verify Memory Loading/Saving
        memory_manager.set_current_task("E2E Integration Task")
        memory_manager.persist_to_disk(memory_json_path)
        assert os.path.exists(memory_json_path)
        
        # Clear and reload from disk
        memory_manager.clear_all()
        assert memory_manager.get_current_task() is None
        memory_manager.load_from_disk(memory_json_path)
        assert memory_manager.get_current_task() == "E2E Integration Task"
        
        # 4. Verify LearningEngine database and similarity search integration
        learning_engine.store_fix("SyntaxError", "app.py", "missing parenthesis", "diff content")
        similar_fixes = learning_engine.find_similar_fixes("missing parenthesis")
        assert len(similar_fixes) > 0
        assert similar_fixes[0]["error_type"] == "SyntaxError"
        
        # 5. Verify SkillScheduler prioritization and execution
        class DummySkill(ISkill):
            def __init__(self, priority=0):
                self.priority = priority
            @property
            def name(self) -> str:
                return "Dummy"
            @property
            def description(self) -> str:
                return "Dummy"
            def execute(self, ctx):
                ctx["logs"] = ctx.get("logs", []) + [f"P{self.priority}"]
                return ctx
                
        scheduler.register_skill("EDIT", DummySkill(priority=5))
        scheduler.register_skill("EDIT", DummySkill(priority=10))
        
        scheduled_ctx = scheduler.schedule_skills("EDIT", {})
        # P10 should run before P5 due to higher priority
        assert scheduled_ctx["logs"] == ["P10", "P5"]
        
        # 6. Verify Prompt Compiler packaging
        compiled = compiler.compile_prompt(
            task="Optimize DB",
            repository_objects=[{"name": "conn", "type": "db"}],
            context="SQLite open connection",
            artifacts={},
            diagnostics=[],
            system_prompt="You are an optimizer.",
            model_name="claude-3-sonnet"
        )
        assert "<system_prompt>" in compiled
        assert "<repository_objects>" in compiled
        
        # 7. Shutdown
        kernel.shutdown()
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
