"""Route agent tool calls to file, terminal, and search implementations."""

from __future__ import annotations

import logging
from typing import Any, Dict

from . import search_tool, terminal_tool, spawn_subagent as _spawn_subagent_mod
from .read_tool import read_file as _read_file
from .write_tool import write_or_edit_file as _write_or_edit_file
from .list_tool import list_directory as _list_directory
from .live_server_tool import open_with_live_server as _open_with_live_server

logger = logging.getLogger("devpilot.dispatcher")

# ── Agent Intelligence: RecoveryManager + KnowledgeStore ────────────────────
# Imported lazily to avoid circular imports; cached at module level after first use.
_recovery_manager = None

def _get_recovery_manager():
    global _recovery_manager
    if _recovery_manager is None:
        try:
            from ..agent.recovery_manager import RecoveryManager
            _recovery_manager = RecoveryManager()
        except Exception:
            pass
    return _recovery_manager


def _maybe_update_knowledge_store(session: Any, rel_path: str) -> None:
    """Update the session's KnowledgeStore index and invalidate cached symbols."""
    try:
        ks = getattr(session, "_knowledge_store", None)
        if ks is not None:
            ks.update_file(rel_path)
    except Exception as e:
        logger.debug(f"KnowledgeStore update_file failed (non-fatal): {e}")

    try:
        from ..cache import invalidate_pattern
        import asyncio
        # Normalize paths for matching in serialized JSON keys
        norm_path = rel_path.replace("\\", "/")
        asyncio.create_task(invalidate_pattern(f"*get_symbols*{norm_path}*"))
        asyncio.create_task(invalidate_pattern("*get_global_symbols*"))
    except Exception as ce:
        logger.debug(f"Cache invalidation trigger failed (non-fatal): {ce}")


_WRITE_ERROR_SIGNATURES = (
    "error", "failed", "permission", "denied", "not found",
    "target block", "not unique", "ambiguous", "exception",
)

def _looks_like_error(result: str) -> bool:
    r = (result or "").lower().strip()
    return r.startswith("error") or any(sig in r for sig in _WRITE_ERROR_SIGNATURES)


async def dispatch_tool(
    session: Any,
    tc_id: str,
    name: str,
    args: Dict[str, Any],
    auto_apply: bool,
) -> str:
    """Dispatch a single tool call to the appropriate implementation.

    Mutative tools (write/edit) and terminal commands may prompt the user
    for confirmation via the session pending_confirmations map unless
    auto_apply / permission rules allow them through.

    Args:
        session: Active AgentSession instance.
        tc_id: Tool call identifier.
        name: Tool name (e.g. read_file, run_terminal_command).
        args: Parsed tool arguments.
        auto_apply: When True, skip file-edit confirmation dialogs.

    Returns:
        Tool result string for the model / chat history.

    Raises:
        NotImplementedError: If name is not a supported tool.
        ValueError: Propagated from edit uniqueness checks.
    """
    if isinstance(name, str) and "<|channel|>" in name:
        name = name.split("<|channel|>")[0]
    # Tool Name Normalization / Aliases for LLM compatibility
    TOOL_ALIASES = {
        # list_directory aliases
        "list_files": "list_directory",
        "list_dir": "list_directory",
        "dir": "list_directory",
        "ls": "list_directory",
        "get_files": "list_directory",
        "show_files": "list_directory",
        "view_files": "list_directory",
        "see_files": "list_directory",
        "workspace_files": "list_directory",
        # read_file aliases
        "view_file": "read_file",
        "get_file": "read_file",
        "read_workspace_file": "read_file",
        "open_file": "read_file",
        "cat_file": "read_file",
        # search_codebase aliases
        "find_files": "search_codebase",
        "search_files": "search_codebase",
        "search_code": "search_codebase",
        "grep": "search_codebase",
        # run_terminal_command aliases
        "execute_command": "run_terminal_command",
        "run_command": "run_terminal_command",
        "terminal": "run_terminal_command",
        "shell_command": "run_terminal_command",
        # live server aliases
        "live_server": "open_with_live_server",
        "start_live_server": "open_with_live_server",
        "open_live_server": "open_with_live_server",
        "serve_html": "open_with_live_server",
        "run_html": "open_with_live_server",
        "preview_html": "open_with_live_server",
        "open_with_live_server": "open_with_live_server",
        # glob aliases
        "glob_search": "glob",
        "find_pattern": "glob",
        "glob_files": "glob",
        # web_fetch aliases
        "fetch_url": "web_fetch",
        "fetch": "web_fetch",
        "http_get": "web_fetch",
        "get_url": "web_fetch",
        "read_url": "web_fetch",
        # apply_patch aliases
        "patch": "apply_patch",
        "apply_diff": "apply_patch",
        "apply_git_diff": "apply_patch",
        # todo aliases
        "write_todo": "todo_write",
        "update_todo": "todo_write",
        "set_todos": "todo_write",
        "read_todo": "todo_read",
        "get_todos": "todo_read",
        "list_todos": "todo_read",
        # write_file aliases
        "create_file": "write_file",
        "write_to_file": "write_file",
        "save_file": "write_file",
        "make_file": "write_file",
        "new_file": "write_file",
        # delegate_to_agent aliases
        "delegate_agent": "delegate_to_agent",
        "delegate": "delegate_to_agent",
        "run_agent": "delegate_to_agent",
        "call_agent": "delegate_to_agent",
        "agent_delegate": "delegate_to_agent",
        "agent": "delegate_to_agent",
        # question aliases
        "ask_user": "question",
        "ask_question": "question",
        "clarify": "question",
        "prompt_user": "question",
        # delete aliases
        "delete": "delete_file",
        "delete_path": "delete_file",
        "remove_file": "delete_file",
        "remove": "delete_file",
        "rm": "delete_file",
    }
    name = TOOL_ALIASES.get(name.lower(), name)

    # A. File write/edit safety check — with recovery analysis
    if name in ("write_file", "edit_file"):
        result = await _write_or_edit_file(session, tc_id, name, args, auto_apply)

        # Determine the file path for knowledge store update
        path_arg = (
            args.get("path")
            or args.get("file_path")
            or args.get("target_file")
            or ""
        )

        if _looks_like_error(result):
            # Analyse the failure and append recovery guidance
            rm = _get_recovery_manager()
            if rm:
                try:
                    # Count how many times this path has been retried
                    retry_key = f"_edit_retry_{path_arg}"
                    retry_count = getattr(session, retry_key, 0)
                    decision = rm.analyse_failure(
                        tool_name=name,
                        args=args,
                        error_output=result,
                        retry_count=retry_count,
                    )
                    setattr(session, retry_key, retry_count + 1)
                    guidance = rm.to_prompt_injection(decision)
                    result = result + guidance
                    logger.info(
                        f"[RecoveryManager] {name} failed on '{path_arg}' "
                        f"(retry #{retry_count}): strategy={decision.strategy}"
                    )
                except Exception as re:
                    logger.debug(f"RecoveryManager error (non-fatal): {re}")
        else:
            # Success — reset retry count and update knowledge store
            retry_key = f"_edit_retry_{path_arg}"
            if hasattr(session, retry_key):
                delattr(session, retry_key)
            if path_arg:
                _maybe_update_knowledge_store(session, path_arg)

        return result

    if name == "delete_file":
        from .delete_tool import delete_file
        return await delete_file(session, tc_id, args, auto_apply)

    # B. Terminal Command safety check
    if name == "run_terminal_command":
        return await terminal_tool.run_terminal_command(session, tc_id, args, auto_apply)

    # C. Apply Patch – requires confirmation like write_file
    if name == "apply_patch":
        from .patch_tool import apply_patch
        return await apply_patch(session, tc_id, args, auto_apply)

    # D. Read-only / utility tools (no approval required)
    if name == "list_directory":
        return await _list_directory(session, args)

    if name == "read_file":
        return await _read_file(session, args)

    if name == "search_codebase":
        return await search_tool.search_codebase(session, args)

    if name == "open_with_live_server":
        return await _open_with_live_server(session, args)

    if name == "glob":
        from .glob_tool import glob_search
        return await glob_search(session, args)

    if name == "web_fetch":
        from .web_fetch_tool import web_fetch
        return await web_fetch(session, args)

    if name == "todo_write":
        from .todo_tool import todo_write
        return await todo_write(session, args)

    if name == "todo_read":
        from .todo_tool import todo_read
        return await todo_read(session, args)

    if name == "question":
        from .question_tool import ask_question
        return await ask_question(session, tc_id, args)

    # E. Sub-agent / delegation tools
    if name == "spawn_subagent":
        prompt = args.get("prompt", "")
        if not prompt:
            raise ValueError("spawn_subagent requires a non-empty prompt argument.")
        return await _spawn_subagent_mod.spawn_subagent(session, prompt)

    if name in ("search_web", "tavily_search", "web_search"):
        from .web_search_tool import search_web
        from ..state import config_manager

        if not config_manager.get_web_search_fallback_enabled():
            return "Web search fallback is disabled in settings."

        query_str = args.get("query", "")
        results = await search_web(query_str)
        if not results:
            return "No web search results found or TAVILY_API_KEY not configured."
        formatted = "\n\n".join([f"### {r.title}\nURL: {r.url}\n{r.snippet}" for r in results])
        return f"## Web Search Results for '{query_str}':\n\n" + formatted

    # F. Discovered MCP Tools routing with permission checks
    from ..mcp_client import MCP_DISCOVERED_TOOLS
    if name in MCP_DISCOVERED_TOOLS or name.startswith("mcp_"):
        if hasattr(session, "permission_manager") and session.permission_manager:
            is_approved, risk, reason = session.permission_manager.check_permission(f"mcp:{name}")
            if not is_approved:
                mcp_rules = session.permission_manager.config.get_mcp_tool_rules()
                rule_match = any(
                    r.get("target") in (name, "*", f"mcp:{name}") and r.get("action") == "deny"
                    for r in (mcp_rules or [])
                )
                if rule_match:
                    return f"Action blocked: MCP tool '{name}' denied by mcp_tool_rules permission policy."

        mcp_meta = MCP_DISCOVERED_TOOLS.get(name, {})
        server_id = mcp_meta.get("server_id")
        if not server_id:
            return f"Error: MCP tool '{name}' has no registered server_id."
        from ..mcp_client import global_mcp_manager
        try:
            return await global_mcp_manager.call_tool(server_id, name, args)
        except Exception as e:
            return f"Error executing MCP tool '{name}': {str(e)}"

    # G. Agent delegation
    if name == "delegate_to_agent":
        agent_name = args.get("agent_name", "")
        task_description = args.get("task_description", "")
        agent = session.orchestrator.agents.get(agent_name)
        if agent is None:
            match = next((k for k in session.orchestrator.agents if k.lower() == agent_name.lower()), None)
            agent = session.orchestrator.agents.get(match) if match else None
        if agent is None:
            # Fallback routing for domain-specific agent names (e.g. Game Development Agent, UI Agent)
            agent_lower = agent_name.lower()
            if any(w in agent_lower for w in ["game", "frontend", "gui", "ui", "web"]):
                fallback = "Frontend Developer Agent"
            elif any(w in agent_lower for w in ["backend", "server", "db", "database"]):
                fallback = "Backend Developer Agent"
            else:
                fallback = "Coding Agent"
            agent = session.orchestrator.agents.get(fallback)
        if agent is None:
            valid = ", ".join(sorted(session.orchestrator.agents.keys()))
            return f"ERROR: Unknown agent '{agent_name}'. Valid agents: {valid}"
        task_id = len(session.orchestrator.context.collaboration_log) + 1
        result = await agent.execute(task_description, session, task_id)
        await session.orchestrator.context.log(f"{agent_name}: {result}")
        return result

    raise NotImplementedError(f"Tool '{name}' is not supported.")
