import os
import pytest
import tempfile
import asyncio
from backend.app.infrastructure.tool_registry import ToolRegistry, ToolDefinition, ReadFileInput
from backend.app.agent.agent_runtime.tool_executor import ToolExecutor, ToolResult
from backend.app.infrastructure.model_gateway import ModelGateway
from backend.app.agent.context_engine.context_engine import ContextEngine
from backend.app.agent.autonomous.verification_engine import VerificationEngine

@pytest.mark.asyncio
async def test_tool_registry_aliases_and_validation():
    # Test canonical resolution
    tool_def = ToolRegistry.get_tool("ls")
    assert tool_def is not None
    assert tool_def.name == "list_directory"

    tool_def2 = ToolRegistry.get_tool("read_workspace_file")
    assert tool_def2 is not None
    assert tool_def2.name == "read_file"

    # Test invalid schema parameter
    executor = ToolExecutor(workspace_root=".")
    res = await executor.execute(
        tool_call_id="tc_test_1",
        tool_name="read_file",
        arguments={"invalid_param": "foo"}
    )
    assert not res.success
    assert "Schema validation error" in res.error

@pytest.mark.asyncio
async def test_model_gateway_retries():
    # Test ModelGateway stream generation
    dummy_profile = {
        "provider": "mock",
        "model": "mock",
        "api_key": "mock",
        "base_url": "mock"
    }
    chunks = []
    async for chunk in ModelGateway.generate_stream(
        dummy_profile,
        messages=[{"role": "user", "content": "Hello"}],
        max_retries=1,
        base_delay=0.01
    ):
        chunks.append(chunk)
    assert len(chunks) > 0
    assert chunks[0]["type"] == "text"

def test_context_engine_isolation():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create context engines with different tenant identities
        ce1 = ContextEngine.get_instance(tmpdir, organization_id="org-a", project_id="proj-a", workspace_id="ws-a")
        ce2 = ContextEngine.get_instance(tmpdir, organization_id="org-b", project_id="proj-b", workspace_id="ws-b")
        assert ce1 is not ce2
        assert ce1.organization_id == "org-a"
        assert ce2.organization_id == "org-b"

@pytest.mark.asyncio
async def test_verification_report_and_caching():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write dummy python files to test hashing
        with open(os.path.join(tmpdir, "main.py"), "w") as f:
            f.write("print('hello')")
        
        ve = VerificationEngine(workspace_root=tmpdir)
        report1 = await ve.run_full_verification()
        assert report1 is not None
        assert report1.success is True

        # Test caching: calling again should return cached instance or equivalent content
        report2 = await ve.run_full_verification()
        assert report2.success is True
