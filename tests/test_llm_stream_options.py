import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.adapters.llm import LLMAdapter

@pytest.mark.asyncio
async def test_stream_openai_fallback_removes_stream_options():
    adapter = LLMAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
        provider="openai",
    )
    
    # Mock client
    mock_client = MagicMock()
    
    # Streaming call fails with an error
    stream_mock = AsyncMock(side_effect=Exception("Streaming failed"))
    mock_client.chat.completions.create = stream_mock
    
    # Non-streaming response mock
    mock_choice = MagicMock()
    mock_choice.message.content = "Fallback response"
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"
    non_stream_response = MagicMock(choices=[mock_choice], usage=None)
    
    calls = []
    async def create_side_effect(**kwargs):
        calls.append(dict(kwargs))
        if kwargs.get("stream") is True:
            raise Exception("Streaming failed")
        return non_stream_response
    
    mock_client.chat.completions.create = AsyncMock(side_effect=create_side_effect)
    
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"name": "test_tool", "description": "test", "input_schema": {}}]
    
    with patch("backend.app.adapters.llm._get_openai_client", return_value=mock_client):
        chunks = []
        async for chunk in adapter._stream_openai(messages, tools, "system"):
            chunks.append(chunk)
            
    assert len(calls) == 2
    # First call was streaming with stream_options
    assert calls[0]["stream"] is True
    assert "stream_options" in calls[0]
    
    # Fallback call was non-streaming WITHOUT stream_options
    assert calls[1]["stream"] is False
    assert "stream_options" not in calls[1]
    
    # Verify we got the text chunk and done chunk
    text_chunks = [c for c in chunks if c.get("type") == "text"]
    assert len(text_chunks) == 1
    assert text_chunks[0]["content"] == "Fallback response"


@pytest.mark.asyncio
async def test_stream_openai_stream_options_rejection_retried():
    adapter = LLMAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
        provider="openai",
    )
    
    mock_client = MagicMock()
    calls = []
    
    class AsyncStream:
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not hasattr(self, "_yielded"):
                self._yielded = True
                mock_delta = MagicMock(content="Hello streamed", tool_calls=None)
                mock_choice = MagicMock(delta=mock_delta)
                return MagicMock(choices=[mock_choice], usage=None)
            raise StopAsyncIteration
            
    async def create_side_effect(**kwargs):
        calls.append(dict(kwargs))
        if "stream_options" in kwargs:
            raise Exception("Validation: The 'stream_options' field is only allowed when 'stream' is set to true.")
        return AsyncStream()
        
    mock_client.chat.completions.create = AsyncMock(side_effect=create_side_effect)
    
    messages = [{"role": "user", "content": "hello"}]
    tools = [{"name": "test_tool", "description": "test", "input_schema": {}}]
    
    with patch("backend.app.adapters.llm._get_openai_client", return_value=mock_client):
        chunks = []
        async for chunk in adapter._stream_openai(messages, tools, "system"):
            chunks.append(chunk)
            
    assert len(calls) == 2
    # First call failed due to stream_options
    assert calls[0]["stream"] is True
    assert "stream_options" in calls[0]
    
    # Second call retried streaming WITHOUT stream_options
    assert calls[1]["stream"] is True
    assert "stream_options" not in calls[1]
    
    text_chunks = [c for c in chunks if c.get("type") == "text"]
    assert len(text_chunks) == 1
    assert text_chunks[0]["content"] == "Hello streamed"
