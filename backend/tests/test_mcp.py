"""Tests for MCP Client & Routes (Feature 4)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from app.mcp_client import MCP_DISCOVERED_TOOLS, global_mcp_manager
from app.tools.dispatcher import dispatch_tool


class _MockSession:
    def __init__(self, mcp_rules=None):
        self.workspace_root = "/fake/workspace"
        self.permission_manager = MagicMock()
        self.permission_manager.check_permission.return_value = (False, "medium", "permission needed")
        self.permission_manager.config.get_mcp_tool_rules.return_value = mcp_rules or []


@pytest.mark.asyncio
async def test_mcp_client_connect_and_tool_discovery():
    """Connecting to an MCP server registers its tools into dispatcher."""
    server_cfg = {
        "id": "github-mcp",
        "name": "GitHub MCP Server",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
    }

    discovered = await global_mcp_manager.connect_server(server_cfg)
    assert len(discovered) >= 1

    tool_name = discovered[0]["name"]
    assert tool_name in MCP_DISCOVERED_TOOLS
    assert MCP_DISCOVERED_TOOLS[tool_name]["server_id"] == "github-mcp"


@pytest.mark.asyncio
async def test_mcp_permission_block():
    """MCP tool execution is blocked when mcp_tool_rules denies it."""
    tool_name = "mcp_test_deny_tool"
    MCP_DISCOVERED_TOOLS[tool_name] = {
        "server_id": "test-server",
        "server_name": "Test Server",
        "name": tool_name,
        "description": "Test tool",
    }

    # Session with deny rule for tool_name
    deny_rules = [{"target": tool_name, "action": "deny"}]
    session = _MockSession(mcp_rules=deny_rules)

    res = await dispatch_tool(session, "tc-100", tool_name, {"query": "test"}, auto_apply=True)
    assert "Action blocked" in res
    assert "denied by mcp_tool_rules" in res


def test_mcp_routes_list_and_add():
    """GET and POST /api/mcp/servers routes work correctly."""
    from unittest.mock import AsyncMock, patch
    client = TestClient(app)

    # 1. GET /api/mcp/servers
    res1 = client.get("/api/mcp/servers")
    assert res1.status_code == 200
    data1 = res1.json()
    assert "servers" in data1

    # 2. POST /api/mcp/servers
    new_srv = {
        "id": "test-srv-1",
        "name": "Test Server 1",
        "command": "python",
        "args": ["-m", "mcp_server"],
    }
    mock_tools = [{"name": "mcp_tool_1", "description": "Mock Tool", "input_schema": {}}]
    with patch("app.routes.mcp_route.global_mcp_manager.connect_server", new_callable=AsyncMock, return_value=mock_tools):
        res2 = client.post("/api/mcp/servers", json=new_srv)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert data2["tools_count"] >= 1
