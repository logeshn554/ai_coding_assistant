"""Route agent tool calls to file, terminal, and search implementations."""

from __future__ import annotations

from typing import Any, Dict

from . import file_tools, search_tool, terminal_tool, spawn_subagent as _spawn_subagent_mod


async def dispatch_tool(
    session: Any,
    tc_id: str,
    name: str,
    args: Dict[str, Any],
    auto_apply: bool,
) -> str:
    """Dispatch a single tool call to the appropriate implementation.

    Mutative tools (write/edit) and terminal commands may prompt the user
    for confirmation via the session's pending_confirmations map unless
    auto_apply / permission rules allow them through.

    Args:
        session: Active AgentSession instance.
        tc_id: Tool call identifier.
        name: Tool name (e.g. ``read_file``, ``run_terminal_command``).
        args: Parsed tool arguments.
        auto_apply: When True, skip file-edit confirmation dialogs.

    Returns:
        Tool result string for the model / chat history.

    Raises:
        NotImplementedError: If ``name`` is not a supported tool.
        ValueError: Propagated from edit uniqueness checks.
    """
    # Tool Name Normalization / Aliases for LLM compatibility
    TOOL_ALIASES = {
        "list_files": "list_directory",
        "list_dir": "list_directory",
        "dir": "list_directory",
        "ls": "list_directory",
        "get_files": "list_directory",
        "show_files": "list_directory",
        "view_files": "list_directory",
        "see_files": "list_directory",
        "workspace_files": "list_directory",
        "view_file": "read_file",
        "get_file": "read_file",
        "read_workspace_file": "read_file",
        "open_file": "read_file",
        "cat_file": "read_file",
        "find_files": "search_codebase",
        "search_files": "search_codebase",
        "search_code": "search_codebase",
        "grep": "search_codebase",
        "execute_command": "run_terminal_command",
        "run_command": "run_terminal_command",
        "terminal": "run_terminal_command",
        "shell_command": "run_terminal_command",
        "live_server": "open_with_live_server",
        "start_live_server": "open_with_live_server",
        "open_live_server": "open_with_live_server",
        "serve_html": "open_with_live_server",
        "run_html": "open_with_live_server",
        "preview_html": "open_with_live_server",
        "open_with_live_server": "open_with_live_server",
    }
    name = TOOL_ALIASES.get(name.lower(), name)

    # A. File write/edit safety check
    if name in ("write_file", "edit_file"):
        return await file_tools.write_or_edit_file(session, tc_id, name, args, auto_apply)

    # B. Destructive/Terminal Command safety check
    if name == "run_terminal_command":
        return await terminal_tool.run_terminal_command(session, tc_id, args, auto_apply)

    # C. Read-only / Live Server tools (no approval required)
    if name == "list_directory":
        return await file_tools.list_directory(session, args)

    if name == "read_file":
        return await file_tools.read_file(session, args)

    if name == "search_codebase":
        return await search_tool.search_codebase(session, args)

    if name == "open_with_live_server":
        return await file_tools.open_with_live_server(session, args)

    if name == "spawn_subagent":
        prompt = args.get("prompt", "")
        if not prompt:
            raise ValueError("spawn_subagent requires a non-empty 'prompt' argument.")
        return await _spawn_subagent_mod.spawn_subagent(session, prompt)

    # D. Discovered MCP Tools routing with permission checks
    from ..mcp_client import MCP_DISCOVERED_TOOLS
    if name in MCP_DISCOVERED_TOOLS or name.startswith("mcp_"):
        # Check mcp_tool_rules permissions
        if hasattr(session, "permission_manager") and session.permission_manager:
            is_approved, risk, reason = session.permission_manager.check_permission(f"mcp:{name}")
            if not is_approved:
                # Check config mcp_tool_rules directly
                mcp_rules = session.permission_manager.config.get_mcp_tool_rules()
                rule_match = any(
                    r.get("target") in (name, "*", f"mcp:{name}") and r.get("action") == "deny"
                    for r in (mcp_rules or [])
                )
                if rule_match:
                    return f"Action blocked: MCP tool '{name}' denied by mcp_tool_rules permission policy."

        mcp_meta = MCP_DISCOVERED_TOOLS.get(name, {})
        server_name = mcp_meta.get("server_name", "MCP Server")
        return f"[MCP Tool '{name}' executed on {server_name}] Arguments: {args}"

    raise NotImplementedError(f"Tool '{name}' is not supported.")


