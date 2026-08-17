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
import logging
import os
import re
from typing import Any

logger = logging.getLogger("loopix.tools.write_tool")

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
        if spec.startswith("@/"):
            continue
        parts = spec.split("/")
        pkg = "/".join(parts[:2]) if spec.startswith("@") and len(parts) >= 2 else parts[0]
        if pkg not in _NODE_BUILTINS:
            names.add(pkg)
    for m in _REQ_RE.finditer(content):
        spec = m.group(1)
        if spec.startswith("@/"):
            continue
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
        return f"Error: Target block not found in file '{path}'."

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

        return f"Error: Mismatch at line {divergence_line}: expected '{expected}' but file has '{actual}'"

    file_first = orig_lines[0].strip() if orig_lines else ""
    return f"Error: Mismatch at line 1: expected '{first_target_line}' but file has '{file_first}'"


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


def check_path_casing(workspace_root: str, relative_path: str) -> tuple[str, bool]:
    """
    Checks the casing of a path.
    Returns (canonical_relative_path, collision_detected).
    - If the exact path exists (matching case): returns (exact_path, False)
    - If a path exists matching case-insensitively but NOT case-sensitively: returns (canonical_path, True)
    - If no match exists: returns (relative_path, False)
    """
    parts = relative_path.replace("\\", "/").split("/")
    current_abs = os.path.realpath(workspace_root)
    resolved_parts = []
    collision = False
    
    for part in parts:
        if not part:
            continue
        if os.path.isdir(current_abs):
            try:
                entries = os.listdir(current_abs)
            except Exception:
                entries = []
            part_lower = part.lower()
            match = None
            for entry in entries:
                if entry.lower() == part_lower:
                    match = entry
                    break
            
            if match is not None:
                if match != part:
                    collision = True
                resolved_parts.append(match)
                current_abs = os.path.join(current_abs, match)
            else:
                resolved_parts.append(part)
                current_abs = os.path.join(current_abs, part)
        else:
            resolved_parts.append(part)
            current_abs = os.path.join(current_abs, part)
            
    return "/".join(resolved_parts), collision


def validate_file_content(path: str, content: str) -> str | None:
    """Validate content is not empty, is valid JSON for .json, and is syntactically valid Python for .py."""
    if not content.strip():
        if os.path.basename(path) == "__init__.py":
            return None
        return "File content cannot be empty."
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e!s}"
    elif ext == ".py":
        try:
            compile(content, path, "exec")
        except SyntaxError as e:
            return f"Python syntax error: {e.msg} (line {e.lineno})"
        except Exception as e:
            return f"Python compilation failed: {e!s}"
            
    # Next.js App Router Client Component validation rule
    norm_path = path.replace("\\", "/").lower()
    if ("src/app/" in norm_path or "app/" in norm_path) and (norm_path.endswith(".tsx") or norm_path.endswith(".jsx")):
        client_hooks = ["useState", "useEffect", "useReducer", "useRef", "useContext", "useRouter", "usePathname", "useSearchParams"]
        has_hook = any(re.search(rf"\b{hook}\b", content) for hook in client_hooks)
        if has_hook:
            clean_content = re.sub(r'/\*[\s\S]*?\*/|//.*', '', content).strip()
            if not (clean_content.startswith('"use client"') or clean_content.startswith("'use client'")):
                return "Missing 'use client' directive in Next.js component containing client hooks."
                
    return None


async def write_or_edit_file(
    session: Any,
    tc_id: str,
    name: str,
    args: dict[str, Any],
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

    # Check casing and collisions
    canonical_path, collision = check_path_casing(session.workspace_root, path)
    if collision:
        abs_canonical = safe_path(session.workspace_root, canonical_path)
        if os.path.exists(abs_canonical):
            return f"Path conflict: case-insensitive collision detected. Trying to access/create '{path}' but '{canonical_path}' already exists."

    path = canonical_path
    args["path"] = canonical_path

    original_content = ""
    proposed_content = ""

    try:
        abs_path = safe_path(session.workspace_root, path)
        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            original_content = await async_read_workspace_file(session.workspace_root, path)
    except Exception as e:
        return f"Path verification failed: {e!s}"

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
                # Stale-content recovery sequence
                logger.info(f"[EditRecovery] Stale-content mismatch in '{path}'. Attempting automated regeneration.")
                if hasattr(session, "_run_llm_query"):
                    rec_sys_prompt = "You are an expert developer. Update a search-and-replace target block to match a file's content exactly."
                    rec_prompt = (
                        f"We are trying to edit a file at path '{path}' but the target block was not found.\n"
                        f"Here is the requested Target block to search for:\n"
                        f"```\n{target}\n```\n\n"
                        f"Here is the requested Replacement block:\n"
                        f"```\n{replacement}\n```\n\n"
                        f"Here is the actual file content:\n"
                        f"```\n{norm_original}\n```\n\n"
                        "Find the segment in the actual file content that matches the intent of the target block. "
                        "Output a JSON object with: \n"
                        "{\n"
                        "  \"target\": \"the exact target block as it appears in the actual file content, matching all spaces/newlines\"\n"
                        "}\n"
                        "Output ONLY the JSON object, nothing else."
                    )
                    try:
                        rec_res = await session._run_llm_query(rec_sys_prompt, rec_prompt)
                        clean_json = rec_res.strip()
                        if clean_json.startswith("```"):
                            clean_json = clean_json.strip("`").strip()
                            if clean_json.startswith("json"):
                                clean_json = clean_json[4:].strip()
                        import json
                        parsed = json.loads(clean_json)
                        new_target = parsed.get("target")
                        if new_target and new_target in norm_original:
                            if norm_original.count(new_target) == 1:
                                logger.info(f"[EditRecovery] Successfully regenerated target matching uniquely in '{path}'.")
                                start = norm_original.find(new_target)
                                target_range = (start, start + len(new_target))
                                target = new_target
                                args["target"] = target
                            else:
                                logger.warning(f"[EditRecovery] Regenerated target block matches multiple times in '{path}'.")
                        else:
                            logger.warning(f"[EditRecovery] Regenerated target block not found in '{path}'.")
                    except Exception as ex:
                        logger.error(f"[EditRecovery] Stale-content recovery query failed: {ex}")

                if target_range is None:
                    return _build_edit_error_hint(target, norm_original, path)

        start, end = target_range
        proposed_content = norm_original[:start] + replacement + norm_original[end:]

    # Confirmation guardrail
    # Skip confirmation for brand-new files (no existing content to diff — nothing to lose)
    is_new_file = not os.path.exists(abs_path)
    if not auto_apply and not is_new_file:
        from ..diff_utils import apply_hunks, generate_hunks
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

    # Validate proposed content
    validation_err = validate_file_content(path, proposed_content)
    if validation_err:
        session.log_audit(name, args, "validation_failed", validation_err)
        return f"Validation Error: {validation_err}"

    # Perform the actual write
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
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
