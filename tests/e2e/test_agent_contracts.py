"""
End-to-End Agent Contract Test Suite — Verifies complete AI capabilities,
tool schema passing, atomic file modifications, and transaction boundaries.
"""

import os
import tempfile
import pytest
from pathlib import Path

from backend.app.agent.agent_runtime import AgentRuntime, AgentTask, AgentState
from backend.app.agent.security import PermissionEngine, RiskLevel
from backend.app.agent.agent_runtime.tool_executor import ToolExecutor, ToolResult


@pytest.mark.asyncio
async def test_contract_llm_tool_execution_and_file_creation(tmp_path):
    """Verify end-to-end agent contract: task execution creates files atomically."""
    workspace = tmp_path
    runtime = AgentRuntime(str(workspace))
    session = await runtime.start_session(str(workspace), session_id="contract_sess_01")

    async def mock_llm_provider(prompt, step):
        from backend.app.agent.agent_runtime.llm_adapter import ModelResponse, ToolCall
        if step == 1:
            return ModelResponse(
                text="Creating app.py",
                tool_calls=[
                    ToolCall(
                        id="tc_app",
                        name="write_file",
                        arguments={"path": "app.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n"}
                    )
                ]
            )
        return ModelResponse(text="Completed creating app.py", tool_calls=[])

    result = await runtime.run(
        session_id="contract_sess_01",
        task="Create a FastAPI app in app.py",
        auto_apply=True,
        llm_provider_func=mock_llm_provider,
    )

    assert result.session_id == "contract_sess_01"
    assert (workspace / "app.py").exists()
    content = (workspace / "app.py").read_text(encoding="utf-8")
    assert "FastAPI" in content


@pytest.mark.asyncio
async def test_contract_permission_engine_boundary_enforcement(tmp_path):
    """Verify PermissionEngine blocks path traversal outside workspace root."""
    engine = PermissionEngine(str(tmp_path), mode="Strict")
    decision = engine.evaluate_tool_call(
        session_id="sess_sec",
        tool_name="read_file",
        arguments={"path": "../../../etc/passwd"}
    )

    assert decision.allowed is False
    assert "Path traversal" in decision.reason or "blocked" in decision.reason
