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
    path = args.get("path", "")
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
    path = args.get("path", "")
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
