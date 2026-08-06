"""Integration tests for the complete AgentOS microkernel architectural lifecycle."""
import os
import sys
import pytest
import tempfile
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.orchestrator import AgentOrchestrator
from app.intelligence.intent_compiler import intent_compiler
from app.intelligence.contract_generator import contract_generator
from app.brain.symbol_graph import symbol_graph
from app.brain.test_graph import test_graph
from app.analysis.prediction_engine import prediction_engine
from app.work_graph.dag_generator import dag_generator
from app.patch.patch_store import patch_store
from app.debate.debate_engine import debate_engine
from app.outcome.outcome_classifier import outcome_classifier
from app.outcome.release_gate import release_gate

@pytest.mark.asyncio
async def test_architectural_lifecycle_components():
    # 1. Test Ingress & Intelligence Layer
    intent = intent_compiler.compile("Create a new api route in app/routes/chat.py. Must be secure. Security is critical.")
    assert intent.goal is not None
    assert len(intent.constraints) > 0
    assert intent.estimated_risk == "medium"
    assert "app/routes/chat.py" in intent.affected_components

    contract = contract_generator.generate_contract(intent, "chat_route")
    assert contract.contract_type == "api"
    assert "GET /api/v1/chat-route" in contract.signatures

    # 2. Test Living Project Brain & Change Analysis
    test_graph.scan_project_tests(["app/routes/chat.py", "tests/test_chat.py"])
    associated = test_graph.get_tests_for_file("app/routes/chat.py")
    assert "tests/test_chat.py" in associated

    symbol_graph.parse_file("dummy.py", "def process_dummy():\n    pass")
    assert "process_dummy" in symbol_graph.nodes
    assert symbol_graph.nodes["process_dummy"].symbol_type == "function"

    prediction = prediction_engine.predict_change_impact(intent)
    assert "app/routes/chat.py" in prediction.predicted_files
    assert prediction.estimated_cost_usd > 0.0

    # 3. Test Work Graph Compiler
    dag_tasks = dag_generator.generate_dag(intent, ["code", "test", "review"])
    assert len(dag_tasks) >= 3
    assert dag_tasks[0].agent_type == "code"

    # 4. Test Debate & Consensus
    critiques = debate_engine.hold_debate("def process():\n    eval('x')")
    assert any(c.is_blocking for c in critiques)

    # 5. Test Outcome & Release Gate
    classification = outcome_classifier.classify_outcome(
        test_failures=0,
        lint_passed=True,
        type_checks_passed=True,
        security_passed=True,
        contract_violations=[]
    )
    assert classification.grade.value == "success"

    should_release = release_gate.should_auto_release(classification)
    assert should_release is True

@pytest.mark.asyncio
async def test_orchestrator_architectural_lifecycle_integration():
    # Setup temp workspace dir to avoid scanning host repository
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Mock session
        session = MagicMock()
        session.workspace_root = temp_dir
        session._execute_tool_with_guardrails = AsyncMock()
        session._execute_tool_with_guardrails.return_value = "mocked terminal execution result"
        session.profile = {
            "api_format": "openai",
            "api_key": "mock_key",
            "base_url": "http://mock-api.com",
            "model_name": "gpt-4o"
        }
        session.send_ws_message = AsyncMock()
        session.conversation_history = []
        
        orchestrator = AgentOrchestrator(session=session)
        
        # Simple query runner
        async def mock_run_query(sys_p, user_c, agent_name=None):
            return "mock result summary"
        session._run_llm_query = mock_run_query

        # Patch ModelRouter.completion dynamically based on agent task_type
        async def mock_completion(profile, messages, system_prompt=None, is_agent=True, task_type=None, **kwargs):
            if task_type == "Requirement Analysis Agent":
                return '{"report": "analyzed", "target_files": ["app/main.py"]}'
            elif task_type == "Planner Agent":
                return '[{"id": 1, "agent": "Coding Agent", "description": "Write basic code", "dependencies": []}]'
            return "mocked agent output"

        with patch("app.adapters.router.ModelRouter.completion", side_effect=mock_completion), \
             patch("app.verification.test_runner.TestRunner.run_tests") as mock_run_tests, \
             patch("app.verification.security_scanner.SecurityScanner.scan_files") as mock_scan_files, \
             patch("app.release.git_committer.GitCommitter.commit_changes") as mock_commit_changes:
            
            mock_run_tests.return_value = MagicMock(success=True, exit_code=0)
            mock_scan_files.return_value = True
            mock_commit_changes.return_value = "Changes successfully committed (mocked)"

            # Patch the actual Coding Agent execution to prevent LLM network calls
            coding_agent = orchestrator.agents["Coding Agent"]
            with patch.object(coding_agent, "execute", new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = "Completed"
                
                # Run Orchestrator task
                await orchestrator.run_task("refactor app/main.py. Must compile correctly. Security check.", session)
                mock_execute.assert_called_once()
                assert len(session.send_ws_message.call_args_list) > 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
