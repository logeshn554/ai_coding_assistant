"""Write Tool – creates, overwrites, or surgically edits workspace files.

Exposes ``write_or_edit_file(session, tc_id, name, args, auto_apply)``
as the primary agent-facing async function.

Contains:
  - ``write_or_edit_file`` – unified write/edit entry point with confirmation guardrail
  - ``_build_edit_error_hint``   – diff-based diagnostic for failed edit_file targets (A1)
  - ``_whitespace_near_match``   – fuzzy whitespace-insensitive target matching
  - ``_check_missing_packages``  – JS/TS import × package.json cross-check (A4)
  - ``_extract_bare_specifiers`` – parse bare import specifiers from JS/TS
"""
from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
from typing import Any, Dict

from ..async_files import (
    async_read_workspace_file,
    async_write_workspace_file,
)
from ..files import safe_path


# ── A4: Node builtin module names excluded from import cross-check ────────────
_NODE_BUILTINS = frozenset({
    "assert", "buffer", "child_process", "cluster", "console", "constants",
    "crypto", "dgram", "dns", "domain", "events", "fs", "http", "http2",
    "https", "inspector", "module", "net", "os", "path", "perf_hooks",
    "process", "punycode", "querystring", "readline", "repl", "stream",
    "string_decoder", "sys", "timers", "tls", "trace_events", "tty", "url",
    "util", "v8", "vm", "wasi", "worker_threads", "zlib",
    "node:fs", "node:path", "node:os", "node:url", "node:crypto",
})

_FROM_RE = re.compile(r'from\s+["\']([^./][^"\']*)["\']')
_REQ_RE = re.compile(r'require\(\s*["\']([^./][^"\']*)["\']\s*\)')


def _extract_bare_specifiers(content: str) -> set:
    """Extract bare-specifier package names from JS/TS import statements."""
    names: set = set()
    for m in _FROM_RE.finditer(content):
        spec = m.group(1)
        parts = spec.split("/")
        pkg = "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]
        if pkg not in _NODE_BUILTINS:
            names.add(pkg)
    for m in _REQ_RE.finditer(content):
        spec = m.group(1)
        parts = spec.split("/")
        pkg = "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]
        if pkg not in _NODE_BUILTINS:
            names.add(pkg)
    return names


async def _check_missing_packages(session: Any, path: str, content: str) -> str:
    """A4: Warn if JS/TS file imports packages absent from nearest package.json."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        return ""
    imports = _extract_bare_specifiers(content)
    if not imports:
        return ""
    try:
        abs_file_dir = os.path.dirname(safe_path(session.workspace_root, path))
    except Exception:
        abs_file_dir = session.workspace_root

    def _read_pkg_json_sync(start_dir: str) -> dict | None:
        search_dir = start_dir
        for _ in range(10):
            candidate = os.path.join(search_dir, "package.json")
            if os.path.isfile(candidate):
                try:
                    with open(candidate, encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    return None
            parent = os.path.dirname(search_dir)
            if parent == search_dir:
                break
            search_dir = parent
        return None

    pkg = await asyncio.to_thread(_read_pkg_json_sync, abs_file_dir)
    if not pkg:
        return ""

    declared: set = set()
    for section in ("dependencies", "devDependencies"):
        declared.update(pkg.get(section, {}).keys())

    missing = sorted(imports - declared)
    if not missing:
        return ""
    pkgs_str = ", ".join(f"`{p}`" for p in missing)
    install_cmd = "npm install " + " ".join(missing)
    return (
        f"\n\n⚠️ **Missing packages**: {pkgs_str} are imported but not declared in package.json. "
        f"Run `{install_cmd}` to install them."
    )


# ── A1: difflib-based edit error diagnostics ──────────────────────────────────

def _build_edit_error_hint(target: str, original_content: str, path: str) -> str:
    """Return a diff-based diagnostic when edit_file target block is not found."""
    target_lines = target.splitlines()
    orig_lines = original_content.splitlines()
    if not target_lines:
        return f"Target block not found in file '{path}'."

    first_target_line = target_lines[0].strip()
    best_line_no = None
    best_ratio = -1.0
    for i, orig_line in enumerate(orig_lines):
        ratio = difflib.SequenceMatcher(None, first_target_line, orig_line.strip()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_line_no = i + 1

    if best_line_no is not None:
        start_idx = best_line_no - 1
        divergence_line = best_line_no
        expected = ""
        actual = ""

        for j in range(len(target_lines)):
            target_idx = j
            file_idx = start_idx + j

            if file_idx >= len(orig_lines):
                divergence_line = file_idx + 1
                expected = target_lines[target_idx]
                actual = ""
                break

            if target_lines[target_idx].strip() != orig_lines[file_idx].strip():
                divergence_line = file_idx + 1
                expected = target_lines[target_idx]
                actual = orig_lines[file_idx]
                break
        else:
            divergence_line = start_idx + len(target_lines)
            expected = ""
            actual = ""

        return f"differs starting at line {divergence_line}: expected '{expected}' but file has '{actual}'"

    file_first = orig_lines[0].strip() if orig_lines else ""
    return f"differs starting at line 1: expected '{first_target_line}' but file has '{file_first}'"


def _whitespace_near_match(target: str, content: str) -> tuple[int, int] | None:
    """Return range (start, end) if target matches content when whitespace is collapsed/stripped."""
    t_stripped = target.strip()
    c_stripped = content.strip()
    if not t_stripped:
        return None

    if t_stripped == c_stripped:
        start = content.find(t_stripped)
        if start != -1:
            return start, start + len(t_stripped)

    parts = re.split(r"\s+", t_stripped)
    pattern = r"\s+".join(re.escape(p) for p in parts if p)
    try:
        rx = re.compile(pattern, re.DOTALL)
        matches = list(rx.finditer(content))
        if len(matches) == 1:
            return matches[0].start(), matches[0].end()
    except Exception:
        pass
    return None


async def write_or_edit_file(
    session: Any,
    tc_id: str,
    name: str,
    args: Dict[str, Any],
    auto_apply: bool,
) -> str:
    """Apply write_file or edit_file with user-confirmation guardrails.

    Args:
        session: Active AgentSession (pending_confirmations, audit, WS).
        tc_id: Tool call identifier for confirmation correlation.
        name: Either ``write_file`` or ``edit_file``.
        args: Tool arguments including path and content/target/replacement.
        auto_apply: When True, skip the confirmation dialog.

    Returns:
        Human-readable success, cancellation, or timeout message.
    """
    path = args.get("path")

    original_content = ""
    proposed_content = ""

    try:
        abs_path = safe_path(session.workspace_root, path)
        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            original_content = await async_read_workspace_file(session.workspace_root, path)
    except Exception as e:
        return f"Path verification failed: {str(e)}"

    if name == "write_file":
        proposed_content = args.get("content", "")

    elif name == "edit_file":
        # A1 — normalize CRLF on all three parties before any comparison
        target = args.get("target", "").replace("\r\n", "\n")
        replacement = args.get("replacement", "").replace("\r\n", "\n")
        norm_original = original_content.replace("\r\n", "\n")

        args["target"] = target
        args["replacement"] = replacement

        target_range = None
        if target in norm_original:
            if norm_original.count(target) > 1:
                raise ValueError(
                    f"Target block occurs multiple times in file '{path}'. Make target block more unique."
                )
            start = norm_original.find(target)
            target_range = (start, start + len(target))
        else:
            try:
                near = _whitespace_near_match(target, norm_original)
            except ValueError:
                raise ValueError(
                    f"Target block occurs multiple times in file '{path}'. Make target block more unique."
                )
            if near is not None:
                target_range = near
            else:
                return _build_edit_error_hint(target, norm_original, path)

        start, end = target_range
        proposed_content = norm_original[:start] + replacement + norm_original[end:]

    # Confirmation guardrail
    if not auto_apply:
        from ..diff_utils import generate_hunks, apply_hunks
        hunks = generate_hunks(original_content, proposed_content)

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

        try:
            # 60-second timeout: if the user disconnects or ignores the dialog,
            # auto-reject so the agent loop is never permanently blocked.
            await asyncio.wait_for(event.wait(), timeout=60)
        except asyncio.TimeoutError:
            session.pending_confirmations.pop(tc_id, None)
            session.log_audit(name, args, "timeout",
                              "Confirmation timed out after 60 s — auto-rejected.")
            return (
                f"Action auto-rejected: user did not respond to the '{name}' "
                f"confirmation dialog for '{path}' within 60 seconds. "
                "Re-send the request if you still want to apply this change."
            )

        decision = session.pending_confirmations.pop(tc_id, {})

        if not decision.get("approved"):
            session.log_audit(name, args, "rejected", "User rejected file modification.")
            return "Action cancelled by the user."

        hunk_decisions = decision.get("hunk_decisions")
        if hunk_decisions is not None:
            proposed_content = apply_hunks(original_content, hunks, hunk_decisions)

    # Perform the actual write
    await async_write_workspace_file(session.workspace_root, path, proposed_content)
    session.log_audit(name, args, "success", f"Modified {path}")
    result = f"Successfully updated file '{path}'."

    # A4 — cross-check imports against package.json (non-blocking)
    try:
        missing_note = await _check_missing_packages(session, path, proposed_content)
        if missing_note:
            result += missing_note
    except Exception:
        pass

    return result
