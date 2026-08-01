from __future__ import annotations

import os
import shutil
import asyncio
from typing import Any, Dict
from ..files import safe_path
from ..async_files import async_read_workspace_file

async def delete_file(
    session: Any,
    tc_id: str,
    args: Dict[str, Any],
    auto_apply: bool,
) -> str:
    """Delete a file or folder relative to the workspace root.

    Args:
        session: Active AgentSession.
        tc_id: Tool call identifier for confirmation correlation.
        args:
            path (str, required): Relative path of the file or folder to delete.
        auto_apply: When True, skip confirmation.

    Returns:
        Human-readable success or failure message.
    """
    path = args.get("path") or ""
    if not path:
        return "Error: Path parameter is required."

    try:
        abs_path = safe_path(session.workspace_root, path)
    except Exception as e:
        return f"Error resolving path: {str(e)}"

    if not os.path.exists(abs_path):
        return f"Error: Path '{path}' does not exist in workspace."

    # 1. Determine original content for diff display
    is_dir = os.path.isdir(abs_path)
    if is_dir:
        original_content = f"Directory to be recursively deleted:\n{path}"
        try:
            children = os.listdir(abs_path)
            if children:
                original_content += "\n\nContents include:\n" + "\n".join(f" - {c}" for c in children[:10])
                if len(children) > 10:
                    original_content += f"\n ... and {len(children) - 10} more items."
        except Exception:
            pass
    else:
        try:
            original_content = await async_read_workspace_file(session.workspace_root, path)
        except Exception as e:
            original_content = f"File content could not be read: {str(e)}"

    proposed_content = ""

    # 2. Confirmation guardrail
    if not auto_apply:
        from ..diff_utils import generate_hunks
        hunks = generate_hunks(original_content, proposed_content)

        event = asyncio.Event()
        session.pending_confirmations[tc_id] = {"event": event, "approved": False, "hunk_decisions": None}

        await session.send_ws_message({
            "type": "confirm_request",
            "tool_call_id": tc_id,
            "tool_name": "delete_file",
            "args": args,
            "diff": {
                "path": path,
                "original": original_content,
                "proposed": proposed_content,
                "hunks": hunks
            }
        })

        try:
            await asyncio.wait_for(event.wait(), timeout=60)
        except asyncio.TimeoutError:
            session.pending_confirmations.pop(tc_id, None)
            session.log_audit("delete_file", args, "timeout", "Confirmation timed out after 60 s — auto-rejected.")
            return (
                f"Action auto-rejected: user did not respond to the 'delete_file' "
                f"confirmation dialog for '{path}' within 60 seconds."
            )

        decision = session.pending_confirmations.pop(tc_id, {})
        if not decision.get("approved"):
            session.log_audit("delete_file", args, "rejected", "User rejected deletion.")
            return "Action cancelled by the user."

    # 3. Perform the actual delete
    try:
        if is_dir:
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
        session.log_audit("delete_file", args, "success", f"Deleted {path}")
        return f"Successfully deleted '{path}'."
    except Exception as e:
        return f"Error: Failed to delete '{path}': {str(e)}"
