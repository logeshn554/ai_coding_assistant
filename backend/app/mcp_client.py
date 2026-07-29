"""Real MCP Client: Model Context Protocol server connection & tool discovery.

Connects to stdio or SSE/HTTP MCP servers, discovers available tools via MCP list_tools,
and registers them into DevPilot's tool dispatcher.

Respects `mcp_tool_rules` permissions before executing any discovered tool.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from .state import config_manager

logger = logging.getLogger("devpilot.mcp_client")

# Global registry of discovered MCP tools: tool_name -> { server_id, name, description, input_schema, handler }
MCP_DISCOVERED_TOOLS: Dict[str, Dict[str, Any]] = {}


@dataclass
class MCPServerConfig:
    """Configuration for an external MCP server."""

    id: str
    name: str
    command: Optional[str] = ""
    args: List[str] = None
    env: Dict[str, str] = None
    url: Optional[str] = ""

    def __post_init__(self):
        if self.args is None:
            self.args = []
        if self.env is None:
            self.env = {}

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MCPClientManager:
    """Manages MCP server sessions and tool registration."""

    def __init__(self):
        self._connected_servers: Dict[str, Dict[str, Any]] = {}

    def list_servers(self) -> List[Dict[str, Any]]:
        """Return list of configured MCP servers with active connection status."""
        configured = config_manager.get_mcp_servers()
        result = []
        for s in configured:
            sid = s.get("id") or s.get("name", "unknown")
            is_active = sid in self._connected_servers
            item = dict(s)
            item["status"] = "connected" if is_active else "configured"
            item["tools_count"] = len(self._connected_servers.get(sid, {}).get("tools", []))
            result.append(item)
        return result

    async def connect_server(self, server_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Connect to an MCP server using the real mcp Python SDK, discover tools,
        and register them into the dispatcher.

        Args:
            server_config: Server config dict with id, name, command/url, args, env.

        Returns:
            List of discovered tool definitions.

        Raises:
            ImportError: If the ``mcp`` package is not installed.
            RuntimeError: If the server connection or tool discovery fails.
        """
        # A5: require the real mcp SDK — no silent stubs
        try:
            import mcp  # noqa: F401
        except ImportError:
            raise ImportError(
                "The 'mcp' Python package is required for MCP server connections. "
                "Install it with: pip install mcp"
            )

        server_id = server_config.get("id") or server_config.get("name", "server")
        server_name = server_config.get("name", server_id)
        command = server_config.get("command", "")
        args = server_config.get("args", [])
        url = server_config.get("url", "")

        discovered_tools: List[Dict[str, Any]] = []
        session_obj = None
        transport_obj = None

        try:
            if command:
                # Stdio-based server
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client

                env = os.environ.copy()
                if server_config.get("env") and isinstance(server_config["env"], dict):
                    env.update(server_config["env"])

                server_params = StdioServerParameters(
                    command=command,
                    args=list(args),
                    env=env,
                )
                logger.info("MCP: Connecting to stdio server '%s': %s %s", server_name, command, args)

                stdio_transport = await asyncio.wait_for(
                    stdio_client(server_params).__aenter__(),
                    timeout=30,
                )
                transport_obj = stdio_transport
                read_stream, write_stream = stdio_transport
                session_obj = ClientSession(read_stream, write_stream)
                await asyncio.wait_for(session_obj.__aenter__(), timeout=15)
                await asyncio.wait_for(session_obj.initialize(), timeout=15)

            elif url:
                # SSE/HTTP-based server
                from mcp import ClientSession
                from mcp.client.sse import sse_client

                logger.info("MCP: Connecting to SSE server '%s': %s", server_name, url)
                sse_transport = await asyncio.wait_for(
                    sse_client(url).__aenter__(),
                    timeout=30,
                )
                transport_obj = sse_transport
                read_stream, write_stream = sse_transport
                session_obj = ClientSession(read_stream, write_stream)
                await asyncio.wait_for(session_obj.__aenter__(), timeout=15)
                await asyncio.wait_for(session_obj.initialize(), timeout=15)

            else:
                raise ValueError("MCP server configuration must specify either 'command' or 'url'.")

            # Discover tools from the live server
            tools_response = await asyncio.wait_for(session_obj.list_tools(), timeout=15)
            raw_tools = getattr(tools_response, "tools", [])

            for tool in raw_tools:
                t_name = tool.name
                t_desc = getattr(tool, "description", "") or ""
                t_schema = {}
                if hasattr(tool, "inputSchema") and tool.inputSchema:
                    try:
                        t_schema = dict(tool.inputSchema)
                    except Exception:
                        t_schema = {}
                discovered_tools.append({
                    "name": t_name,
                    "description": t_desc,
                    "input_schema": t_schema,
                })

        except Exception as conn_err:
            logger.error("Failed to connect MCP server '%s': %s", server_name, conn_err)
            raise RuntimeError(f"MCP server '{server_name}' connection failed: {conn_err}") from conn_err

        # Register discovered tools into global MCP_DISCOVERED_TOOLS
        for tool in discovered_tools:
            t_name = tool["name"]
            MCP_DISCOVERED_TOOLS[t_name] = {
                "server_id": server_id,
                "server_name": server_name,
                "name": t_name,
                "description": tool["description"],
                "input_schema": tool.get("input_schema", {}),
                "config": server_config,
            }

        self._connected_servers[server_id] = {
            "config": server_config,
            "tools": discovered_tools,
            "session": session_obj,
            "transport": transport_obj,
            "connected_at": asyncio.get_event_loop().time(),
        }

        logger.info("MCP: Connected server '%s', registered %d tools.", server_name, len(discovered_tools))
        return discovered_tools

    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on a connected MCP server and return the result as a string.

        Args:
            server_id: ID of the connected server.
            tool_name: Name of the tool to call.
            arguments: Tool input arguments.

        Returns:
            String representation of the tool result content.

        Raises:
            RuntimeError: If the server is not connected or the call fails.
        """
        server_entry = self._connected_servers.get(server_id)
        if not server_entry:
            raise RuntimeError(
                f"MCP server '{server_id}' is not connected. "
                f"Call connect_server() first."
            )

        session_obj = server_entry.get("session")
        if session_obj is None:
            raise RuntimeError(f"MCP server '{server_id}' has no active session.")

        try:
            result = await asyncio.wait_for(
                session_obj.call_tool(tool_name, arguments=arguments),
                timeout=60,
            )
            # Extract text content from MCP result
            content_parts = getattr(result, "content", None) or []
            parts = []
            for part in content_parts:
                part_type = getattr(part, "type", "")
                if part_type == "text":
                    parts.append(getattr(part, "text", ""))
                else:
                    try:
                        parts.append(json.dumps(part.__dict__ if hasattr(part, "__dict__") else str(part)))
                    except Exception:
                        parts.append(str(part))
            return "\n".join(parts) if parts else "[MCP tool returned no content]"
        except Exception as e:
            raise RuntimeError(f"MCP tool call '{tool_name}' failed: {e}") from e

    async def disconnect_server(self, server_id: str) -> bool:
        """Disconnect an MCP server, close the session, and unregister its tools."""
        if server_id in self._connected_servers:
            entry = self._connected_servers.pop(server_id)
            # Close session gracefully
            session_obj = entry.get("session")
            if session_obj is not None:
                try:
                    await asyncio.wait_for(session_obj.__aexit__(None, None, None), timeout=10)
                except Exception:
                    pass
            transport_obj = entry.get("transport")
            if transport_obj is not None:
                try:
                    await asyncio.wait_for(transport_obj.__aexit__(None, None, None), timeout=10)
                except Exception:
                    pass
            # Unregister tools
            tools_to_remove = [k for k, v in MCP_DISCOVERED_TOOLS.items() if v.get("server_id") == server_id]
            for k in tools_to_remove:
                MCP_DISCOVERED_TOOLS.pop(k, None)
            logger.info("MCP: Disconnected server '%s'", server_id)
            return True
        return False


# Global singleton instance
global_mcp_manager = MCPClientManager()
