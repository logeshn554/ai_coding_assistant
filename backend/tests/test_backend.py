import os
import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app, SESSION_TOKEN
from app.files import safe_path
from app.shell_adapter import ShellAdapter
from app.workspace_index import WorkspaceIndex

def test_path_traversal():
    workspace = os.path.abspath(".")
    outside_path = os.path.join(workspace, "../../../etc/passwd")
    with pytest.raises(PermissionError):
        safe_path(outside_path, workspace)

def test_api_authentication():
    client = TestClient(app)
    
    res = client.get("/api/workspace")
    assert res.status_code == 200

def test_auth_token():
    client = TestClient(app)
    res = client.get("/auth/token")
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["token"] == SESSION_TOKEN

def test_shell_adapter():
    shell_name = ShellAdapter.get_shell_name()
    executable = ShellAdapter.get_shell_executable()
    
    exec_str = " ".join(executable) if isinstance(executable, list) else str(executable)
    
    if os.name == "nt":
        assert "powershell" in shell_name.lower() or "cmd" in shell_name.lower()
        assert "powershell" in exec_str.lower() or "cmd" in exec_str.lower()
    else:
        assert "bash" in shell_name.lower() or "sh" in shell_name.lower()
        assert "bash" in exec_str.lower() or "sh" in exec_str.lower()

@pytest.mark.asyncio
async def test_sqlite_history(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.db import Base, SessionModel, MessageModel
    import datetime

    db_path = tmp_path / "test_history.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as db:
        session = SessionModel(id="test-session-1", title="Test Session")
        db.add(session)
        await db.commit()
        
    async with async_session() as db:
        from sqlalchemy import select
        res = await db.execute(select(SessionModel).where(SessionModel.id == "test-session-1"))
        session = res.scalar()
        assert session is not None
        assert session.title == "Test Session"

def test_workspace_context_indexer(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    
    file1 = src_dir / "index.js"
    file1.write_text("console.log('hello');\n" * 10)
    
    file2 = src_dir / "ignored.pyc"
    file2.write_bytes(b"some binary data")
    
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    file_git = git_dir / "config"
    file_git.write_text("git config")
    
    indexer = WorkspaceIndex(str(tmp_path))
    indexer.update()
    
    rel_paths = list(indexer.cache.keys())
    assert "src/index.js" in rel_paths
    assert "ignored.pyc" not in rel_paths
    assert ".git/config" not in rel_paths
    
    context = indexer.get_prompt_context(max_tokens=2000)
    assert "src/index.js" in context
    assert "console.log" in context

@pytest.mark.asyncio
async def test_openai_adapter_non_stream_fallback():
    from unittest.mock import MagicMock, AsyncMock, patch
    from app.adapters.openai import OpenAIAdapter

    adapter = OpenAIAdapter(api_key="test_key", base_url="http://test", model_name="nova-micro")

    mock_msg = MagicMock()
    mock_msg.content = "Fallback response"
    mock_msg.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_choice.finish_reason = "stop"
    mock_non_stream = MagicMock()
    mock_non_stream.choices = [mock_choice]

    with patch("app.adapters.openai.AsyncOpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # First call (stream=True) raises API error, second call (stream=False) succeeds
        mock_client.chat.completions.create = AsyncMock(side_effect=[
            Exception("BedrockException - modelStreamErrorException"),
            mock_non_stream
        ])

        chunks = []
        tools = [{"name": "test_tool", "description": "test", "input_schema": {}}]
        async for chunk in adapter.stream_chat(messages=[{"role": "user", "content": "hi"}], tools=tools, system_prompt="sys"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0] == {"type": "text", "content": "Fallback response"}
        assert chunks[1] == {"type": "done", "stop_reason": "stop"}
