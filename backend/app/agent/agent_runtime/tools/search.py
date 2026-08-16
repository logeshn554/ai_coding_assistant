"""
Search Tools — Code and symbol search for the agent.

Provides search_code (text grep) and search_symbol (AST-based) tools
that operate on the workspace filesystem.
"""

from __future__ import annotations

import functools
import logging
import os
import re

from agent_runtime.tools import RiskLevel, ToolDefinition, ToolResult

logger = logging.getLogger("agent_runtime.tools.search")

# Maximum number of results to return
_MAX_RESULTS = 50


async def _search_code(
    query: str,
    file_pattern: str = "*",
    workspace_root: str = ".",
) -> ToolResult:
    """Search for a text pattern across files in the workspace.

    Args:
        query: Text or regex pattern to search for.
        file_pattern: Glob-style file filter (e.g. "*.py", "*.ts").
        workspace_root: Root directory to search in.
    """
    import fnmatch

    skip_dirs = {".git", "node_modules", "__pycache__", "dist", "build", "venv", ".venv", ".env", "env"}
    matches = []

    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        # Fall back to literal search if regex is invalid
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    try:
        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for filename in files:
                if file_pattern != "*" and not fnmatch.fnmatch(filename, file_pattern):
                    continue

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                matches.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                                if len(matches) >= _MAX_RESULTS:
                                    break
                except (OSError, UnicodeDecodeError):
                    continue

                if len(matches) >= _MAX_RESULTS:
                    break
            if len(matches) >= _MAX_RESULTS:
                break

        if not matches:
            return ToolResult(
                success=True,
                output=f"No matches found for '{query}'",
                metadata={"query": query, "count": 0},
            )

        truncated = f"\n(truncated at {_MAX_RESULTS} results)" if len(matches) >= _MAX_RESULTS else ""
        return ToolResult(
            success=True,
            output="\n".join(matches) + truncated,
            metadata={"query": query, "count": len(matches)},
        )

    except Exception as e:
        return ToolResult(success=False, output="", error=f"Search failed: {e}")


async def _search_symbol(
    symbol_name: str,
    workspace_root: str = ".",
) -> ToolResult:
    """Search for a function, class, or variable definition by name.

    Uses simple regex-based symbol detection for Python and JavaScript/TypeScript.
    """
    skip_dirs = {".git", "node_modules", "__pycache__", "dist", "build", "venv", ".venv"}
    supported_extensions = {".py", ".js", ".ts", ".tsx", ".jsx"}

    # Patterns for common symbol definitions
    patterns = [
        re.compile(rf"^\s*(async\s+)?def\s+{re.escape(symbol_name)}\s*\(", re.MULTILINE),
        re.compile(rf"^\s*class\s+{re.escape(symbol_name)}\s*[\(:]", re.MULTILINE),
        re.compile(rf"^\s*(export\s+)?(const|let|var|function|async\s+function)\s+{re.escape(symbol_name)}\s*", re.MULTILINE),
        re.compile(rf"^\s*{re.escape(symbol_name)}\s*=", re.MULTILINE),
    ]

    matches = []

    try:
        for root, dirs, files in os.walk(workspace_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for filename in files:
                ext = os.path.splitext(filename)[1]
                if ext not in supported_extensions:
                    continue

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, workspace_root).replace("\\", "/")

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()

                    for pat in patterns:
                        for m in pat.finditer(content):
                            line_num = content[:m.start()].count("\n") + 1
                            line = content.splitlines()[line_num - 1].strip()
                            entry = f"{rel_path}:{line_num}: {line}"
                            if entry not in matches:
                                matches.append(entry)

                except (OSError, UnicodeDecodeError):
                    continue

                if len(matches) >= _MAX_RESULTS:
                    break
            if len(matches) >= _MAX_RESULTS:
                break

        if not matches:
            return ToolResult(
                success=True,
                output=f"No definitions found for symbol '{symbol_name}'",
                metadata={"symbol": symbol_name, "count": 0},
            )

        return ToolResult(
            success=True,
            output="\n".join(matches),
            metadata={"symbol": symbol_name, "count": len(matches)},
        )

    except Exception as e:
        return ToolResult(success=False, output="", error=f"Symbol search failed: {e}")


def create_search_tools(workspace_root: str) -> list[ToolDefinition]:
    """Create all search tools bound to a workspace root."""
    search = functools.partial(_search_code, workspace_root=workspace_root)
    symbol = functools.partial(_search_symbol, workspace_root=workspace_root)

    return [
        ToolDefinition(
            name="search_code",
            description=(
                "Search for a text pattern across all files in the workspace. "
                "Supports regex patterns. Returns matching lines with file paths and line numbers."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text or regex pattern to search for.",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob filter for file names (e.g. '*.py'). Defaults to all files.",
                        "default": "*",
                    },
                },
                "required": ["query"],
            },
            executor=search,
            risk_level=RiskLevel.LOW,
            timeout=30.0,
        ),
        ToolDefinition(
            name="search_symbol",
            description=(
                "Search for a function, class, or variable definition by name. "
                "Returns file locations where the symbol is defined."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "symbol_name": {
                        "type": "string",
                        "description": "The name of the function, class, or variable to find.",
                    },
                },
                "required": ["symbol_name"],
            },
            executor=symbol,
            risk_level=RiskLevel.LOW,
            timeout=30.0,
        ),
    ]
