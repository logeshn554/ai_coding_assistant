"""HTTP routes for managing Model Context Protocol (MCP) servers."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..mcp_client import global_mcp_manager
from ..state import config_manager

logger = logging.getLogger("loopix.routes.mcp")
router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class MCPServerRequest(BaseModel):
    """Payload for adding or updating an MCP server."""

    id: str = Field(..., description="Unique server identifier")
    name: str = Field(..., description="Display name of the MCP server")
    command: str | None = ""
    args: list[str] | None = Field(default_factory=list)
    env: dict[str, str] | None = Field(default_factory=dict)
    url: str | None = ""


@router.get("/servers")
def list_mcp_servers():
    """List configured MCP servers and their connection statuses."""
    return {"servers": global_mcp_manager.list_servers()}


@router.post("/servers")
async def add_mcp_server(req: MCPServerRequest):
    """Add a new MCP server configuration and attempt tool discovery connection."""
    server_data = req.model_dump()
    try:
        config_manager.add_mcp_server(server_data)
        discovered_tools = await global_mcp_manager.connect_server(server_data)
        return {
            "success": True,
            "server": server_data,
            "tools_count": len(discovered_tools),
            "tools": discovered_tools,
        }
    except Exception as exc:
        logger.error("Failed to connect new MCP server '%s': %s", req.id, exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/servers/{server_id}")
async def delete_mcp_server(server_id: str):
    """Remove an MCP server configuration and unregister its tools."""
    try:
        await global_mcp_manager.disconnect_server(server_id)
        config_manager.delete_mcp_server(server_id)
        return {"success": True, "server_id": server_id}
    except Exception as exc:
        logger.error("Failed to delete MCP server '%s': %s", server_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
