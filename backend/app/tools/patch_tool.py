"""Patch tool – apply a unified diff (patch) to workspace files.

Exposes ``apply_patch(session, tc_id, args, auto_apply)`` as the
agent-facing async function. Requires user confirmation unless
``auto_apply`` is set, consistent with ``write_file`` behaviour.

Supports the standard unified diff format produced by ``git diff`` and
``diff -u``.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Minimal unified-diff parser
# ---------------------------------------------------------------------------

def _parse_unified_diff(patch_text: str) -> List[Dict]:
    """Parse a unified diff into a list of file-change dicts.

    Each dict has:
        ``path``   – relative file path being patched
        ``hunks``  – list of (old_start, old_count, new_start, new_count, lines)
    """
    files: List[Dict] = []
    current: Dict | None = None
    hunk: Dict | None = None

    for line in patch_text.splitlines():
        # --- a/path / +++ b/path
        if line.startswith("--- "):
            pass  # handled by +++ line
        elif line.startswith("+++ "):
            path = re.sub(r"^b/", "", line[4:].strip().split("\t")[0])
            current = {"path": path, "hunks": []}
            files.append(current)
            hunk = None
        elif line.startswith("@@ ") and current is not None:
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                hunk = {
                    "old_start": int(m.group(1)),
                    "old_count": int(m.group(2) or 1),
                    "new_start": int(m.group(3)),
                    "new_count": int(m.group(4) or 1),
                    "lines": [],
                }
                current["hunks"].append(hunk)
        elif hunk is not None:
            hunk["lines"].append(line)

    return files


def _apply_hunk(original_lines: List[str], hunk: Dict) -> List[str]:
    """Apply a single hunk to the original file lines (1-indexed start)."""
    result: List[str] = []
    old_idx = 0  # 0-based cursor through original_lines
    start = hunk["old_start"] - 1  # convert to 0-based

    # Copy lines before this hunk
    result.extend(original_lines[:start])
    old_idx = start

    for line in hunk["lines"]:
        if line.startswith(" "):        # context line
            result.append(original_lines[old_idx] if old_idx < len(original_lines) else line[1:] + "\n")
            old_idx += 1
        elif line.startswith("-"):      # removed line
            old_idx += 1               # skip original
        elif line.startswith("+"):      # added line
            result.append(line[1:] + "\n")
        # lines starting with \ (no newline at end of file) are ignored

    # Copy remaining lines after hunk
    result.extend(original_lines[old_idx:])
    return result


def _apply_patch_to_content(original: str, file_patch: Dict) -> Tuple[str, List[str]]:
    """Apply all hunks for a single file. Returns (new_content, warnings)."""
    lines = original.splitlines(keepends=True)
    warnings: List[str] = []
    for hunk in file_patch["hunks"]:
        try:
            lines = _apply_hunk(lines, hunk)
        except Exception as exc:
            warnings.append(f"Hunk at line {hunk['old_start']} failed: {exc}")
    return "".join(lines), warnings


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

async def apply_patch(
    session: Any,
    tc_id: str,
    args: Dict[str, Any],
    auto_apply: bool = False,
) -> str:
    """Apply a unified diff patch to one or more workspace files.

    Args:
        session: Active AgentSession.
        tc_id: Tool call identifier (for confirmation dialog).
        args:
            patch (str, required): The full unified diff text.
        auto_apply: Skip confirmation dialog if True.

    Returns:
        Summary of applied changes or error message.
    """
    patch_text: str = (args.get("patch") or "").strip()
    if not patch_text:
        return "Error: 'patch' argument is required for apply_patch."

    workspace_root = Path(getattr(session, "workspace_root", ".")).resolve()

    # Parse the diff
    try:
        file_patches = _parse_unified_diff(patch_text)
    except Exception as exc:
        return f"Error parsing patch: {exc}"

    if not file_patches:
        return "Error: No file changes found in the provided patch."

    # Build a preview summary for the confirmation dialog
    summary_lines = [f"apply_patch will modify {len(file_patches)} file(s):"]
    for fp in file_patches:
        adds = sum(1 for h in fp["hunks"] for l in h["lines"] if l.startswith("+"))
        dels = sum(1 for h in fp["hunks"] for l in h["lines"] if l.startswith("-"))
        summary_lines.append(f"  {fp['path']}  (+{adds} / -{dels})")
    preview = "\n".join(summary_lines)

    # Require confirmation (same pattern as write_or_edit_file)
    if not auto_apply:
        confirm_event = None
        if hasattr(session, "pending_confirmations"):
            import asyncio
            confirm_event = asyncio.Event()
            session.pending_confirmations[tc_id] = {"event": confirm_event, "approved": False}
            await session.send_ws_message({
                "type": "confirmation_request",
                "tool_call_id": tc_id,
                "tool": "apply_patch",
                "preview": preview,
                "message": "Approve applying this patch to your files?",
            })
            try:
                await asyncio.wait_for(confirm_event.wait(), timeout=120)
            except asyncio.TimeoutError:
                return "apply_patch timed out waiting for user confirmation."
            if not session.pending_confirmations.get(tc_id, {}).get("approved"):
                return "apply_patch was rejected by the user."

    # Apply patches
    results: List[str] = []
    for fp in file_patches:
        rel_path = fp["path"].lstrip("/\\")
        if ".." in rel_path:
            results.append(f"  SKIPPED {fp['path']}: path traversal detected.")
            continue

        abs_path = (workspace_root / rel_path).resolve()
        try:
            abs_path.relative_to(workspace_root)
        except ValueError:
            results.append(f"  SKIPPED {fp['path']}: outside workspace root.")
            continue

        # Read original (empty string for new files)
        original = ""
        if abs_path.exists():
            try:
                original = abs_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                results.append(f"  ERROR reading {fp['path']}: {exc}")
                continue

        new_content, warnings = _apply_patch_to_content(original, fp)

        try:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(new_content, encoding="utf-8")
            warn_str = ("  Warnings: " + "; ".join(warnings)) if warnings else ""
            results.append(f"  ✓ Patched {fp['path']}{warn_str}")
        except Exception as exc:
            results.append(f"  ERROR writing {fp['path']}: {exc}")

    return "Patch applied:\n" + "\n".join(results)
