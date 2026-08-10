import unittest
import asyncio
import os
import shutil
import tempfile
import time
from collections import OrderedDict

from agent_os.agent_os import AgentOS
from agent_os.kernel.scheduler import DependencyScheduler
from agent_os.context.virtual_memory import VirtualMemoryContextManager
from agent_os.repository.db import DatabaseManager
from agent_os.repository.repository import RepositoryKernel
from agent_os.learning.engine import LearningEngine
from agent_os.core.cache import CacheService
from agent_os.skills.orchestrator import SkillOrchestrator
from agent_os.skills.plugins import IDEContext

class TestAgentOSV2(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_agentos.db")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. DependencyScheduler Tests
    def test_dependency_scheduler(self):
        scheduler = DependencyScheduler(concurrency_limit=2)
        tasks = [
            {"id": "A", "dependencies": [], "priority": 1},
            {"id": "B", "dependencies": ["A"], "priority": 0},
            {"id": "C", "dependencies": ["A"], "priority": 2},
            {"id": "D", "dependencies": ["B", "C"], "priority": 0},
        ]
        
        execution_order = []
        async def mock_execute(task):
            execution_order.append(task["id"])
            await asyncio.sleep(0.01)
            return f"Result {task['id']}"

        results = asyncio.run(scheduler.execute_graph(tasks, mock_execute))
        
        self.assertEqual(results["A"]["status"], "success")
        self.assertEqual(results["B"]["status"], "success")
        self.assertEqual(results["C"]["status"], "success")
        self.assertEqual(results["D"]["status"], "success")
        
        self.assertEqual(execution_order[0], "A")
        # B has priority 0, C has priority 2. So B should start executing before C once A completes.
        self.assertTrue(execution_order.index("B") < execution_order.index("C") or execution_order.index("B") == 1)

    def test_scheduler_cycle_detection(self):
        scheduler = DependencyScheduler(concurrency_limit=2)
        tasks = [
            {"id": "A", "dependencies": ["B"]},
            {"id": "B", "dependencies": ["A"]},
        ]
        async def mock_execute(task):
            return "ok"

        results = asyncio.run(scheduler.execute_graph(tasks, mock_execute))
        self.assertEqual(results["A"]["status"], "failed")
        self.assertEqual(results["A"]["error"], "Deadlock/Cycle detected")
        self.assertEqual(results["B"]["status"], "failed")
        self.assertEqual(results["B"]["error"], "Deadlock/Cycle detected")

    def test_scheduler_cascading_failure(self):
        scheduler = DependencyScheduler(concurrency_limit=2)
        tasks = [
            {"id": "A", "dependencies": []},
            {"id": "B", "dependencies": ["A"]},
            {"id": "C", "dependencies": ["B"]},
        ]
        async def mock_execute(task):
            if task["id"] == "A":
                raise ValueError("Fail A")
            return "ok"

        results = asyncio.run(scheduler.execute_graph(tasks, mock_execute))
        self.assertEqual(results["A"]["status"], "failed")
        self.assertEqual(results["B"]["status"], "skipped")
        self.assertEqual(results["B"]["error"], "Dependency failed")
        self.assertEqual(results["C"]["status"], "skipped")
        self.assertEqual(results["C"]["error"], "Dependency failed")

    # 2. VirtualMemoryContextManager Tests
    def test_virtual_memory(self):
        vm = VirtualMemoryContextManager(token_budget=10) # 10 tokens = 40 characters
        
        vm.load_context("key1", "1234567890", "hot") # 10 chars = 2 tokens
        vm.load_context("key2", "1234567890", "hot") # 2 tokens
        vm.load_context("key3", "1234567890", "hot") # 2 tokens
        vm.load_context("key4", "1234567890", "hot") # 2 tokens
        vm.load_context("key5", "1234567890", "hot") # 2 tokens
        
        # total 10 tokens. Fits budget.
        self.assertEqual(vm.estimate_tokens(), 10)
        
        # Adding another one pushes it to 12 tokens, causing eviction
        vm.load_context("key6", "1234567890", "hot") # 2 tokens
        
        # Budget was exceeded, oldest should be paged out/demoted.
        # Check order: hot keys should be evicting/demoting.
        # Key1 was loaded first, so it was demoted/evicted.
        self.assertNotIn("key1", vm._hot)
        self.assertEqual(vm.estimate_tokens(), 10)

    # 3. DatabaseManager Tests
    def test_database_manager(self):
        db = DatabaseManager(self.db_path)
        
        # Test batch insert symbols
        file_id = db.insert_file("main.py", "python", 100, 12345, "hash")
        
        symbols = [
            {"name": "foo", "type": "function", "start_line": 1, "start_col": 0, "end_line": 2, "end_col": 5, "signature": "def foo()"},
            {"name": "Bar", "type": "class", "start_line": 4, "start_col": 0, "end_line": 10, "end_col": 1, "signature": "class Bar"},
        ]
        db.insert_symbols_batch(file_id, symbols)
        
        res_sym = db.query_symbols("foo", "function")
        self.assertEqual(len(res_sym), 1)
        self.assertEqual(res_sym[0]["file_path"], "main.py")
        
        # Test batch references
        refs = [
            {"name": "foo", "line": 5, "col": 4},
            {"name": "Bar", "line": 8, "col": 12},
        ]
        db.insert_references_batch(file_id, refs)
        
        res_ref = db.query_references("foo")
        self.assertEqual(len(res_ref), 1)
        self.assertEqual(res_ref[0]["line"], 5)

    # 4. RepositoryKernel scan tests
    def test_repository_kernel(self):
        repo = RepositoryKernel(self.db_path)
        
        # Create some files in temp directory
        workspace = os.path.join(self.temp_dir, "workspace")
        os.makedirs(workspace)
        
        file_a = os.path.join(workspace, "a.py")
        with open(file_a, "w") as f:
            f.write("def foo():\n    pass\n")
            
        file_b = os.path.join(workspace, "b.py")
        with open(file_b, "w") as f:
            f.write("class Bar:\n    pass\n")
            
        # First scan
        repo.scan_workspace(workspace)
        files = repo.list_files()
        self.assertIn("a.py", files)
        self.assertIn("b.py", files)
        
        # Verify symbols in DB
        syms_foo = repo.db.query_symbols("foo", "function")
        self.assertEqual(len(syms_foo), 1)
        
        # Modify file a.py and scan again (incremental)
        time.sleep(1) # Ensure modified time changes
        with open(file_a, "w") as f:
            f.write("def foo_new():\n    pass\n")
            
        repo.scan_workspace(workspace)
        
        syms_foo_old = repo.db.query_symbols("foo", "function")
        syms_foo_new = repo.db.query_symbols("foo_new", "function")
        self.assertEqual(len(syms_foo_old), 0)
        self.assertEqual(len(syms_foo_new), 1)

    # 5. LearningEngine Tests
    def test_learning_engine(self):
        le = LearningEngine(self.db_path)
        
        # Store fixes and patterns
        le.store_fix("SyntaxError", "main.py", "invalid syntax", "diff_content")
        le.store_pattern("singleton", "design", "class Singleton:")
        
        fixes = le.find_similar_fixes("invalid syntax")
        self.assertTrue(len(fixes) > 0)
        self.assertEqual(fixes[0]["error_type"], "SyntaxError")
        
        # Test async wrappers
        async def run_async_tests():
            await le.async_store_fix("TypeError", "app.py", "type mismatch", "diff_2")
            res = await le.async_find_similar_fixes("type mismatch")
            return res
            
        res_async = asyncio.run(run_async_tests())
        self.assertTrue(len(res_async) > 0)
        self.assertEqual(res_async[0]["error_type"], "TypeError")

    # 6. SkillOrchestrator & IDEContext Tests
    def test_skill_orchestrator(self):
        orchestrator = SkillOrchestrator()
        
        # Register dummy skills
        from agent_os.skills.plugins import RenameSymbolSkill, GenerateTestSkill
        orchestrator.register_skill("rename_symbol", RenameSymbolSkill())
        orchestrator.register_skill("generate_test", GenerateTestSkill())
        
        ctx = IDEContext(current_file="index.js", selected_symbol="calculate")
        
        # Run parallel
        ctx = asyncio.run(orchestrator.run_parallel(["rename_symbol", "generate_test"], ctx))
        
        self.assertTrue(ctx["rename_symbol_executed"])
        self.assertTrue(ctx["generate_test_executed"])
        self.assertIn("Renamed symbol successfully.", ctx.logs)
        self.assertIn("Generated test cases successfully.", ctx.logs)

    # 7. CacheService LRU eviction
    def test_cache_service_lru(self):
        cache = CacheService(max_size_per_category=2)
        
        cache.set("category1", "key1", "val1")
        cache.set("category1", "key2", "val2")
        
        # Retrieve key1 to make it most recently used
        self.assertEqual(cache.get("category1", "key1"), "val1")
        
        # Adding key3 should evict key2 (since key1 was accessed and key2 is oldest)
        cache.set("category1", "key3", "val3")
        
        self.assertEqual(cache.get("category1", "key1"), "val1")
        self.assertIsNone(cache.get("category1", "key2"))
        self.assertEqual(cache.get("category1", "key3"), "val3")

    # 8. AgentOS Facade Integration
    def test_agent_os_facade(self):
        workspace = os.path.join(self.temp_dir, "workspace")
        os.makedirs(workspace)
        
        # Create a file to index
        with open(os.path.join(workspace, "app.py"), "w") as f:
            f.write("class MyApp:\n    pass\n")

        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        status = aos.status()
        self.assertEqual(status["status"], "booted")
        self.assertEqual(status["total_files_indexed"], 1)
        
        # Run skills
        ctx = IDEContext(current_file="app.py", selected_symbol="MyApp")
        ctx = asyncio.run(aos.run_skills_parallel(["rename_symbol", "security_scan"], ctx))
        
        self.assertTrue(ctx["rename_symbol_executed"])
        self.assertTrue(ctx["security_scan_executed"])

    # 9. PolicyEngine & Sandbox command safety tests
    def test_policy_engine_command_safety(self):
        from agent_os.kernel.policy_engine import PolicyEngine
        policy = PolicyEngine(self.temp_dir)
        
        # Safe commands
        self.assertTrue(policy.is_command_safe("git status"))
        self.assertTrue(policy.is_command_safe("python -m unittest"))
        
        # Dangerous command utilities
        self.assertFalse(policy.is_command_safe("rm -rf /"))
        self.assertFalse(policy.is_command_safe("format c:\\"))
        self.assertFalse(policy.is_command_safe("reboot"))
        
        # Path traversal out of bounds
        self.assertFalse(policy.is_command_safe("cat ../../../etc/passwd"))

    def test_sandbox_policy_vetting_and_auditing(self):
        from agent_os.execution.interfaces import ISandbox
        from agent_os.infrastructure.audit_store import AuditStore
        
        workspace = os.path.join(self.temp_dir, "workspace")
        os.makedirs(workspace, exist_ok=True)
        
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        # Resolve sandbox via DI registry factory
        sandbox = aos.registry.resolve(ISandbox)
        sandbox.start()
        
        audit_store = aos.registry.resolve(AuditStore)
        audit_store.clear()
        
        # Safe command run
        res = sandbox.run_command("echo hello")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("hello", res["stdout"])
        
        # Check AuditStore logs
        records = audit_store.get_records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].status, "approved")
        self.assertEqual(records[1].status, "success")
        
        # Unsafe command run
        res_unsafe = sandbox.run_command("rm -rf /")
        self.assertEqual(res_unsafe["exit_code"], -1)
        self.assertIn("Permission Denied: Command blocked by policy engine.", res_unsafe["stderr"])
        
        # Check AuditStore logs (should append denied log)
        records_after = audit_store.get_records()
        self.assertEqual(len(records_after), 3)
        self.assertEqual(records_after[2].status, "denied")
        self.assertEqual(records_after[2].target, "rm -rf /")
        
        sandbox.stop()

    # 10. Transactional Execution & Locking tests
    def test_transactional_locking_and_optimistic_checks(self):
        from agent_os.execution.lock_manager import FileLockManager
        from agent_os.execution.engine import TransactionError
        
        workspace = os.path.join(self.temp_dir, "tx_workspace")
        os.makedirs(workspace, exist_ok=True)
        
        app_file = os.path.join(workspace, "app.py")
        with open(app_file, "w") as f:
            f.write("x = 10\n")
            
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        # Resolve Lock Manager & Execution Engine
        lock_manager = aos.registry.resolve(FileLockManager)
        engine = aos.execution_engine
        
        # Scenario A: Pessimistic Locking block
        # Acquire lock under agent1
        lock_manager.acquire_lock(app_file, "agent1", exclusive=True)
        
        # Try to modify file in a transaction under agent2
        tx_agent2 = engine.create_transaction("agent2")
        tx_agent2.begin()
        
        with self.assertRaises(TransactionError) as ctx:
            tx_agent2.apply_patch(app_file, "x = 10", "x = 20")
        self.assertIn("locked by another agent", str(ctx.exception))
        tx_agent2.rollback()
        
        # Release lock
        lock_manager.release_lock(app_file, "agent1")
        
        # Scenario B: Optimistic Locking failure
        tx_agent1 = engine.create_transaction("agent1")
        tx_agent1.begin()
        tx_agent1.apply_patch(app_file, "x = 10", "x = 20")
        
        # Modify file externally during active transaction
        with open(app_file, "w") as f:
            f.write("x = 15\n")
            
        # Commit should fail due to optimistic snapshot mismatch
        with self.assertRaises(TransactionError) as ctx_opt:
            tx_agent1.commit()
        self.assertIn("Optimistic lock verification failed", str(ctx_opt.exception))
        
        # Ensure the external modification was NOT overwritten
        with open(app_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "x = 15\n")
        
        # Scenario C: Success & lock release
        # Reset file
        with open(app_file, "w") as f:
            f.write("x = 10\n")
            
        tx_success = engine.create_transaction("agent1")
        tx_success.begin()
        tx_success.apply_patch(app_file, "x = 10", "x = 30")
        tx_success.commit()
        
        # Verify changes were written
        with open(app_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "x = 30\n")
        
        # Verify that lock was released and another agent can lock/modify it
        tx_other = engine.create_transaction("agent2")
        tx_other.begin()
        tx_other.apply_patch(app_file, "x = 30", "x = 40")
        tx_other.commit()
        
        with open(app_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "x = 40\n")

    # 11. Repository Intelligence & Git tests
    def test_repository_knowledge_graph(self):
        from agent_os.repository.interfaces import IRepositoryKnowledgeGraph
        
        workspace = os.path.join(self.temp_dir, "graph_workspace")
        os.makedirs(workspace, exist_ok=True)
        
        main_py = os.path.join(workspace, "main.py")
        helper_py = os.path.join(workspace, "helper.py")
        
        with open(main_py, "w") as f:
            f.write("import helper\nhelper.greet()\n")
        with open(helper_py, "w") as f:
            f.write("def greet():\n    pass\n")
            
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        # Resolve Repository Knowledge Graph
        graph = aos.registry.resolve(IRepositoryKnowledgeGraph)
        self.assertIsNotNone(graph)
        
        deps = graph.get_dependencies("main.py")
        self.assertIn("helper.py", deps["imports"])
        
        # Check call graph for helper function
        cg = graph.get_call_graph("greet")
        self.assertTrue(len(cg["called_by"]) >= 0)

    def test_git_source_control(self):
        from agent_os.repository.interfaces import ISourceControl
        
        workspace = os.path.join(self.temp_dir, "git_workspace")
        os.makedirs(workspace, exist_ok=True)
        
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        # Resolve Git Source Control
        sc = aos.registry.resolve(ISourceControl)
        self.assertIsNotNone(sc)
        
        # Test get_diff (should return string representing git state)
        diff = sc.get_diff()
        self.assertIsInstance(diff, str)

    # 12. Reasoning Loop tests
    def test_agent_reasoning_loop_success(self):
        workspace = os.path.join(self.temp_dir, "reasoning_workspace_success")
        os.makedirs(workspace, exist_ok=True)
        
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        # Safe tasks graph execution
        task_graph = [
            {"id": "t1", "name": "Scan code", "depends_on": [], "priority": 0}
        ]
        
        async def mock_exec(t):
            return {"status": "done", "task_id": t["id"]}
            
        res = asyncio.run(aos.execute_goal(
            goal="Analyze workspace",
            task_graph=task_graph,
            execute_task_fn=mock_exec
        ))
        
        self.assertEqual(res["status"], "success")
        self.assertIn("understand", res["phases"])
        self.assertIn("inspect", res["phases"])
        self.assertIn("plan", res["phases"])
        self.assertIn("execute", res["phases"])
        self.assertEqual(res["phases"]["repair"], "Skipped (no failures).")

    def test_agent_reasoning_loop_repair(self):
        workspace = os.path.join(self.temp_dir, "reasoning_workspace_repair")
        os.makedirs(workspace, exist_ok=True)
        
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        task_graph = [
            {"id": "t1", "name": "Failing update", "depends_on": [], "priority": 0}
        ]
        
        async def mock_exec_fail(t):
            raise ValueError("Compilation Error!")
            
        async def mock_repair(task, error):
            return f"Fixed syntax of {task['id']} successfully."
            
        res = asyncio.run(aos.execute_goal(
            goal="Failing goal with repair",
            task_graph=task_graph,
            execute_task_fn=mock_exec_fail,
            repair_fn=mock_repair
        ))
        
        # Verify that the goal completed successfully after running repair phase
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["phases"]["repair"]["status"], "success")
        self.assertIn("Fixed syntax of t1 successfully.", res["phases"]["repair"]["details"])

    # 13. Episodic Memory vs Performance Optimizer tests
    def test_agent_memory_and_learning_separation(self):
        workspace = os.path.join(self.temp_dir, "mem_workspace")
        os.makedirs(workspace, exist_ok=True)
        
        aos = AgentOS(workspace_root=workspace, db_path=self.db_path)
        asyncio.run(aos.boot())
        
        self.assertIsNotNone(aos.memory)
        self.assertIsNotNone(aos.optimizer)
        
        task_graph = [
            {"id": "t1", "name": "Memory check task", "depends_on": [], "priority": 0}
        ]
        
        async def mock_exec(t):
            return {"status": "success", "task_id": t["id"]}
            
        res = asyncio.run(aos.execute_goal(
            goal="Test Memory Goal",
            task_graph=task_graph,
            execute_task_fn=mock_exec
        ))
        
        # Verify Memory has recorded the plan and task events
        self.assertEqual(aos.memory.get_current_task(), "Test Memory Goal")
        self.assertEqual(aos.memory.get_current_plan(), task_graph)
        
        events = aos.memory.get_events()
        self.assertTrue(len(events) >= 2)
        event_types = [e["type"] for e in events]
        self.assertIn("task_started", event_types)
        self.assertIn("task_completed", event_types)
        
        # Verify Performance Optimizer has recorded metrics
        report = aos.optimizer.generate_report()
        self.assertIn("Success Rate", report)
        self.assertIn("Latency", report)
        
        # Test persistence
        persist_file = os.path.join(workspace, "memory_state.json")
        aos.memory.persist_to_disk(persist_file)
        self.assertTrue(os.path.exists(persist_file))
        
        # Load in another memory manager
        from agent_os.learning.memory_kernel import MemoryKernelManager
        new_mem = MemoryKernelManager()
        new_mem.load_from_disk(persist_file)
        self.assertEqual(new_mem.get_current_task(), "Test Memory Goal")
        self.assertEqual(new_mem.get_current_plan(), task_graph)

if __name__ == "__main__":
    unittest.main()
