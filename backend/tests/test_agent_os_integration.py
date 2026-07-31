import os
import sys
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure backend root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.orchestrator import AgentOrchestrator

@pytest.mark.asyncio
async def test_agent_os_orchestration_lifecycle():
    # 1. Initialize Orchestrator
    orchestrator = AgentOrchestrator()

    # 2. Setup mock session & profile
    session = MagicMock()
    session.profile = {
        "api_format": "openai",
        "api_key": "mock_key",
        "base_url": "http://mock-api.com",
        "model_name": "gpt-4o"
    }
    session.send_ws_message = AsyncMock()
    session.conversation_history = []
    session._execute_tool_with_guardrails = AsyncMock(return_value="success")
    
    # Simple query runner
    async def mock_run_query(sys_p, user_c, agent_name=None):
        return "mock summary result"
    session._run_llm_query = mock_run_query

    # 3. Create a temporary workspace root
    with tempfile.TemporaryDirectory() as tmpdir:
        session.workspace_root = tmpdir
        # Create a sample file to be indexed
        sample_file = os.path.join(tmpdir, "main.py")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("def dummy():\n    pass\n")

        # 4. Patch the LLM calls to return structured routing plans
        with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
            # First call (Planner): return plan
            # Second call (Summary): return summary
            async def dynamic_completion(*args, **kwargs):
                task_type = args[4] if len(args) > 4 else kwargs.get("task_type", "")
                task_type_lower = (task_type or "").lower()
                
                messages = args[1] if len(args) > 1 else kwargs.get("messages", [])
                user_msg = messages[-1]["content"].lower() if messages else ""
                system_prompt = args[2] if len(args) > 2 else kwargs.get("system_prompt", "")
                sys_prompt_lower = (system_prompt or "").lower()
                
                if "planner" in task_type_lower or ("planner" in sys_prompt_lower and "requirement" not in sys_prompt_lower):
                    return '[{"id": 1, "agent": "Coding Agent", "description": "Write basic code", "dependencies": []}]'
                elif "requirement" in task_type_lower or "requirement" in sys_prompt_lower:
                    return '["main.py"]'
                elif "summarize" in sys_prompt_lower or "summary" in task_type_lower:
                    return "Summary: task finished successfully"
                else:
                    return "Success/Completed"
            mock_comp.side_effect = dynamic_completion

            # 5. Patch Coding Agent to return successfully
            coding_agent = orchestrator.agents["Coding Agent"]
            with patch.object(coding_agent, "execute", new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = "Completed"

                # Run Orchestrator task
                res = await orchestrator.run_task("refactor main.py dummy function", session)
                assert "completed" in res.lower()

                # Verify subtask execution and WebSocket status updates
                mock_execute.assert_called_once()
                
                # Check that WebSocket events were sent
                assert session.send_ws_message.call_count > 0
                sent_types = [call.args[0]["type"] for call in session.send_ws_message.call_args_list]
                assert "agent_state" in sent_types
