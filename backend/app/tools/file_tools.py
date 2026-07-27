"""File listing, reading, and write/edit helpers for agent tool dispatch."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict

from ..async_files import (
    async_list_workspace_dir,
    async_read_workspace_file,
    async_write_workspace_file,
)
from ..files import safe_path


async def list_directory(session: Any, args: Dict[str, Any]) -> str:
    """List files and directories under a workspace-relative path.

    Args:
        session: Active AgentSession providing workspace_root.
        args: Tool arguments; uses ``path`` (default empty string).

    Returns:
        JSON string of directory entries.
    """
    path = args.get("path") or args.get("dir") or args.get("directory") or args.get("folder") or ""
    items = await async_list_workspace_dir(session.workspace_root, path)
    return json.dumps(items, indent=2)


async def read_file(session: Any, args: Dict[str, Any]) -> str:
    """Read a file relative to the workspace root.

    Args:
        session: Active AgentSession providing workspace_root.
        args: Tool arguments; uses ``path``.

    Returns:
        File contents as a string.
    """
    path = args.get("path") or args.get("file") or args.get("filepath") or args.get("filename") or ""
    return await async_read_workspace_file(session.workspace_root, path)



async def write_or_edit_file(
    session: Any,
    tc_id: str,
    name: str,
    args: Dict[str, Any],
    auto_apply: bool,
) -> str:
    """Apply write_file or edit_file with confirmation guardrails.

    Args:
        session: Active AgentSession (pending_confirmations, audit, WS).
        tc_id: Tool call identifier for confirmation correlation.
        name: Either ``write_file`` or ``edit_file``.
        args: Tool arguments including path and content/target/replacement.
        auto_apply: When True, skip the confirmation dialog.

    Returns:
        Human-readable success, cancellation, or timeout message.

    Raises:
        ValueError: If edit target is missing or not unique in the file.
    """
    path = args.get("path")

    # Resolve original and proposed content for diff view
    original_content = ""
    proposed_content = ""

    try:
        # Resolve path
        abs_path = safe_path(session.workspace_root, path)
        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            original_content = await async_read_workspace_file(session.workspace_root, path)
    except Exception as e:
        return f"Path verification failed: {str(e)}"

    if name == "write_file":
        proposed_content = args.get("content", "")
    elif name == "edit_file":
        target = args.get("target", "").replace("\r\n", "\n")
        replacement = args.get("replacement", "").replace("\r\n", "\n")
        args["target"] = target
        args["replacement"] = replacement
        if target not in original_content:
            raise ValueError(f"Target block not found in file '{path}'. Edit failed.")
        if original_content.count(target) > 1:
            raise ValueError(f"Target block occurs multiple times in file '{path}'. Make target block more unique.")
        proposed_content = original_content.replace(target, replacement, 1)

    # Check if user confirmation is required
    if not auto_apply:
        from ..diff_utils import generate_hunks, apply_hunks
        hunks = generate_hunks(original_content, proposed_content)

        # Ask frontend for approval
        event = asyncio.Event()
        session.pending_confirmations[tc_id] = {"event": event, "approved": False, "hunk_decisions": None}

        await session.send_ws_message({
            "type": "confirm_request",
            "tool_call_id": tc_id,
            "tool_name": name,
            "args": args,
            "diff": {
                "path": path,
                "original": original_content,
                "proposed": proposed_content,
                "hunks": hunks
            }
        })

        # Wait for websocket confirmation response (5-min timeout to handle disconnects)
        try:
            await asyncio.wait_for(event.wait(), timeout=300)
        except asyncio.TimeoutError:
            session.pending_confirmations.pop(tc_id, None)
            session.log_audit(name, args, "timeout", "Confirmation timed out — client disconnected.")
            return "Action timed out: client did not respond within 5 minutes."

        decision = session.pending_confirmations[tc_id]
        del session.pending_confirmations[tc_id]

        if not decision["approved"]:
            session.log_audit(name, args, "rejected", "User rejected file modification.")
            return "Action cancelled by the user."

        # Reconstruct content based on hunk decisions
        hunk_decisions = decision.get("hunk_decisions")
        if hunk_decisions is not None:
            proposed_content = apply_hunks(original_content, hunks, hunk_decisions)
        # If hunk_decisions is None, it means the user accepted the entire file edits as a whole

    # Perform the actual write
    await async_write_workspace_file(session.workspace_root, path, proposed_content)
    session.log_audit(name, args, "success", f"Modified {path}")
    return f"Successfully updated file '{path}'."


def find_free_port(start_port: int = 5500) -> int:
    """Finds an available free TCP port starting from start_port."""
    import socket
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return start_port


async def open_with_live_server(session: Any, args: Dict[str, Any]) -> str:
    """Launches or reuses Live Server for an HTML file or static site in the workspace.

    Args:
        session: Active AgentSession providing workspace_root & send_ws_message.
        args: Tool arguments; optional ``path`` (default auto-detect) and ``port`` (default 5500).

    Returns:
        String output containing the Live Server localhost URL.
    """
    rel_path = args.get("path") or args.get("file") or args.get("filepath") or ""

    if not rel_path or not rel_path.endswith((".html", ".htm")):
        found_html = None
        for root, _, files in os.walk(session.workspace_root):
            for file in files:
                if file.endswith((".html", ".htm")):
                    rel_p = os.path.relpath(os.path.join(root, file), session.workspace_root).replace("\\", "/")
                    if file == "index.html":
                        found_html = rel_p
                        break
                    elif not found_html:
                        found_html = rel_p
            if found_html and found_html.endswith("index.html"):
                break
        rel_path = found_html or "index.html"

    from ..processes import global_process_manager

    # 1. Check if Live Server is already running for this workspace
    running_procs = global_process_manager.get_running_processes()
    for p in running_procs:
        if p.cwd == session.workspace_root and ("http.server" in p.command or "Live Server" in (p.name or "")):
            port = p.port or 5500
            live_url = f"http://localhost:{port}/{rel_path}".rstrip("/")
            res_msg = (
                f"🚀 **Live Server is already running!**\n\n"
                f"🔗 **Preview URL**: [{live_url}]({live_url})\n\n"
                f"Serving file: `{rel_path}` at `http://localhost:{port}/`"
            )
            await session.send_ws_message({
                "type": "text_delta",
                "content": f"\n{res_msg}\n"
            })
            return res_msg

    # 2. Find an available free port if requested port is blocked
    requested_port = args.get("port") or 5500
    port = find_free_port(requested_port)
    command = f"python -m http.server {port}"

    proc = await global_process_manager.start_process(command, session.workspace_root, name="Live Server (Static HTML)")
    asyncio.create_task(session.monitor_and_stream_events(proc))

    live_url = f"http://localhost:{port}/{rel_path}".rstrip("/")

    res_msg = (
        f"🚀 **Live Server Started!**\n\n"
        f"🔗 **Preview URL**: [{live_url}]({live_url})\n\n"
        f"Serving HTML file `{rel_path}` at `http://localhost:{port}/`"
    )

    await session.send_ws_message({
        "type": "text_delta",
        "content": f"\n{res_msg}\n"
    })

    return res_msg


