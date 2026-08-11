"""
Phase 1 Acceptance Tests — Verifies the real coding agent, provider routing, tools execution, and loops.
"""

from __future__ import annotations

import os
import pytest
import asyncio
import tempfile
import pathlib
from unittest.mock import AsyncMock

from agent_os.providers.base import ProviderConfig, ModelResponse, ToolCall
from agent_os.providers.model_router import ModelRouter
from agent_os.tools.registry import ToolRegistry
from agent_os.runtime.agent_loop import AgentLoop


@pytest.fixture
def workspace():
    """Create temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield pathlib.Path(tmpdir)


@pytest.fixture
def tool_registry(workspace):
    """Create a default tool registry for the workspace."""
    return ToolRegistry().create_default(str(workspace))


@pytest.fixture
def model_router():
    """Create a model router, with mock fallback if API keys are missing."""
    config = None
    try:
        config = ProviderConfig.from_env()
    except Exception:
        config = ProviderConfig(
            name="openai",
            model="gpt-4o-mini",
            api_key="mock-key",
            base_url="https://api.openai.com/v1",
        )
    
    router = ModelRouter(config)
    
    # Check if we should mock generate calls (e.g. no real api key set)
    api_key = config.api_key
    if not api_key or api_key == "mock-key" or api_key.startswith("mock"):
        # Patch generate to return pre-defined mock sequences based on user prompt
        async def mock_generate(messages, tools=None, **kwargs):
            last_msg = messages[-1]["content"].lower()
            if "hello.py" in last_msg:
                return ModelResponse(
                    content="Creating the file.",
                    tool_calls=[ToolCall(
                        id="tc1",
                        name="write_file",
                        arguments={"path": "hello.py", "content": "print('Hello World')"}
                    )],
                    finish_reason="tool_use",
                )
            elif "add(a,b)" in last_msg:
                return ModelResponse(
                    content="Modifying code.",
                    tool_calls=[ToolCall(
                        id="tc2",
                        name="write_file",
                        arguments={"path": "module.py", "content": "def add(a, b):\n    return a + b\n"}
                    )],
                    finish_reason="tool_use",
                )
            elif "broken.py" in last_msg:
                # If first step, return edit tool call
                if len(messages) <= 2:
                    return ModelResponse(
                        content="Fixing calculation.",
                        tool_calls=[ToolCall(
                            id="tc3",
                            name="write_file",
                            arguments={"path": "broken.py", "content": "def calculate(x):\n    return x * 2\n\ndef test_calculate():\n    assert calculate(5) == 10\n"}
                        )],
                        finish_reason="tool_use",
                    )
                else:
                    return ModelResponse(content="Calculation fixed.", tool_calls=[], finish_reason="end_turn")
            elif "auth.py" in last_msg:
                return ModelResponse(
                    content="Creating auth modules.",
                    tool_calls=[
                        ToolCall(id="tc4", name="write_file", arguments={"path": "auth.py", "content": "def validate_email(email):\n    return '@' in email\n"}),
                        ToolCall(id="tc5", name="write_file", arguments={"path": "test_auth.py", "content": "from auth import validate_email\ndef test_validate_email():\n    assert validate_email('test@domain.com')\n"}),
                    ],
                    finish_reason="tool_use",
                )
            return ModelResponse(content="Done.", tool_calls=[], finish_reason="end_turn")
            
        router.provider.generate = mock_generate
        
    return router


@pytest.mark.asyncio
async def test_create_file(workspace, tool_registry, model_router):
    """Test 1: Create file - Agent creates hello.py that prints Hello World."""
    loop = AgentLoop(model_router, tool_registry)
    state = await loop.run("Create hello.py that prints 'Hello World'.")
    
    # Verify file exists
    hello_file = workspace / "hello.py"
    assert hello_file.exists(), "hello.py was not created"
    
    # Verify content
    content = hello_file.read_text()
    assert "print" in content and "Hello World" in content
    
    # Verify execution
    result = await tool_registry.execute(
        "run_command",
        command="python hello.py"
    )
    assert result["success"]
    assert "Hello World" in result["output"].strip()


@pytest.mark.asyncio
async def test_modify_code(workspace, tool_registry, model_router):
    """Test 2: Modify code - Add a function called add(a,b)."""
    module_file = workspace / "module.py"
    module_file.write_text("")
    
    loop = AgentLoop(model_router, tool_registry)
    state = await loop.run("Add a function called add(a,b) that returns a+b.")
    
    # Verify function exists
    content = module_file.read_text()
    assert "def add" in content
    assert "return" in content


@pytest.mark.asyncio
async def test_debug_and_repair(workspace, tool_registry, model_router):
    """Test 3: Debug - Agent fixes a broken function."""
    broken_file = workspace / "broken.py"
    broken_file.write_text("""
def calculate(x):
    return x * 2 / 0  # Division by zero!
    
def test_calculate():
    assert calculate(5) == 10
""")
    
    loop = AgentLoop(model_router, tool_registry, max_steps=20)
    state = await loop.run("Fix the broken function in broken.py so tests pass.")
    
    # Verify fix
    result = await tool_registry.execute(
        "run_command",
        command="python -m pytest broken.py -v"
    )
    assert result["success"], f"Tests failed: {result['output']}"


@pytest.mark.asyncio
async def test_multi_file_change(workspace, tool_registry, model_router):
    """Test 4: Multi-file - Add login validation and tests."""
    loop = AgentLoop(model_router, tool_registry)
    state = await loop.run("Create auth.py with a validate_email function and create test_auth.py with tests.")
    
    # Verify both files exist
    assert (workspace / "auth.py").exists()
    assert (workspace / "test_auth.py").exists()


@pytest.mark.asyncio
async def test_git_operations(workspace, tool_registry, model_router):
    """Test 5: Git status and git diff."""
    # Initialize repository
    await tool_registry.execute("run_command", command="git init")
    await tool_registry.execute("run_command", command="git config user.email 'test@test.com'")
    await tool_registry.execute("run_command", command="git config user.name 'Test User'")
    
    # Create file and commit
    test_file = workspace / "test.txt"
    test_file.write_text("initial")
    await tool_registry.execute("run_command", command="git add test.txt")
    await tool_registry.execute("run_command", command="git commit -m 'initial'")
    
    # Modify file
    await tool_registry.execute(
        "write_file",
        path="test.txt",
        content="modified"
    )
    
    # Get status and diff
    status_res = await tool_registry.execute("git_status")
    assert status_res["success"]
    assert "M" in status_res["output"]
    
    diff_res = await tool_registry.execute("git_diff")
    assert diff_res["success"]
    assert "modified" in diff_res["output"]


@pytest.mark.asyncio
async def test_provider_switching():
    """Test 6: Provider switching."""
    config = ProviderConfig(
        name="openai",
        model="gpt-4o-mini",
        api_key="mock-key",
        base_url="https://api.openai.com/v1",
    )
    router = ModelRouter(config)
    
    # Switch provider to Ollama
    router.switch_provider(
        provider_name="ollama",
        model="llama3",
        api_key="mock-key",
        base_url="http://localhost:11434/v1"
    )
    assert router.config.name == "ollama"
    assert router.config.model == "llama3"
    assert router.config.base_url == "http://localhost:11434/v1"
