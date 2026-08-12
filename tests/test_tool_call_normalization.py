import pathlib
import tempfile
import pytest
from backend.app.agent.agent_runtime.llm_adapter import (
    ModelResponseNormalizer,
)
from backend.app.agent.agent_runtime import (
    AgentRuntime,
    AgentState,
)


def test_normalize_dict_response_preserves_tool_calls():
    response = {
        "content": "",
        "tool_calls": [
            {
                "id": "call_123",
                "name": "write_file",
                "arguments": {
                    "path": "hello.py",
                    "content": "print('Hello World')",
                },
            }
        ],
    }

    result = ModelResponseNormalizer.normalize_response(response)

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_123"
    assert result.tool_calls[0].name == "write_file"
    assert result.tool_calls[0].arguments["path"] == "hello.py"
    assert result.tool_calls[0].arguments["content"] == "print('Hello World')"


@pytest.mark.asyncio
async def test_agent_dict_provider_creates_hello_py():
    """Verify that a dict response from an LLM provider reaches ToolExecutor and creates hello.py."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = pathlib.Path(tmpdir)
        runtime = AgentRuntime(str(ws_path))
        session = await runtime.start_session(str(ws_path), session_id="test_hello_sess")

        async def dict_llm_provider(prompt, step):
            if step == 1:
                # Simulates AgentSession.agent_llm_provider returning canonical dict
                return {
                    "content": "Creating hello.py",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "name": "write_file",
                            "arguments": {
                                "path": "hello.py",
                                "content": "print('Hello World')",
                            },
                        }
                    ],
                }
            return {
                "content": "Done creating hello.py",
                "tool_calls": [],
            }

        result = await runtime.run(
            "test_hello_sess",
            "Create hello.py containing print('Hello World')",
            llm_provider_func=dict_llm_provider,
        )

        assert result.success is True
        assert (ws_path / "hello.py").exists()
        assert (ws_path / "hello.py").read_text().strip() == "print('Hello World')"
        assert "hello.py" in result.changed_files["created_files"]
