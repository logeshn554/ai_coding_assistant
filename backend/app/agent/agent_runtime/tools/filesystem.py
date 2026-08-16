"""
Filesystem Tools — Real file operations for the agent.

Provides read_file, write_file, edit_file, create_file, and list_directory
as executable ToolDefinitions that operate on the actual workspace filesystem.
"""

from __future__ import annotations

import logging
import os

from agent_runtime.tools import RiskLevel, ToolDefinition, ToolResult

logger = logging.getLogger("agent_runtime.tools.filesystem")


def _validate_path(workspace_root: str, file_path: str) -> tuple[bool, str, str]:
    """Resolve and validate a file path within the workspace.

    Returns:
        (is_valid, abs_path, error_message)
    """
    if os.path.isabs(file_path):
        abs_path = os.path.abspath(file_path)
    else:
        abs_path = os.path.abspath(os.path.join(workspace_root, file_path))

    # Security: path must be within workspace
    if not abs_path.startswith(os.path.abspath(workspace_root)):
        return False, abs_path, f"Security error: path '{file_path}' is outside workspace"

    return True, abs_path, ""


async def _read_file(file_path: str, workspace_root: str = ".") -> ToolResult:
    """Read the contents of a file."""
    valid, abs_path, err = _validate_path(workspace_root, file_path)
    if not valid:
        return ToolResult(success=False, output="", error=err)

    if not os.path.exists(abs_path):
        return ToolResult(success=False, output="", error=f"File not found: {file_path}")

    if not os.path.isfile(abs_path):
        return ToolResult(success=False, output="", error=f"Path is not a file: {file_path}")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return ToolResult(
            success=True,
            output=content,
            metadata={"file_path": file_path, "size_bytes": len(content.encode("utf-8"))},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Error reading file: {e}")


async def _write_file(file_path: str, content: str, workspace_root: str = ".") -> ToolResult:
    """Write content to a file, creating it if it doesn't exist."""
    valid, abs_path, err = _validate_path(workspace_root, file_path)
    if not valid:
        return ToolResult(success=False, output="", error=err)

    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            success=True,
            output=f"Successfully wrote {len(content)} bytes to {file_path}",
            metadata={"file_path": file_path, "size_bytes": len(content.encode("utf-8"))},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Error writing file: {e}")


async def _edit_file(
    file_path: str,
    target: str,
    replacement: str,
    workspace_root: str = ".",
) -> ToolResult:
    """Edit a file by replacing the first occurrence of target text with replacement text."""
    valid, abs_path, err = _validate_path(workspace_root, file_path)
    if not valid:
        return ToolResult(success=False, output="", error=err)

    if not os.path.exists(abs_path):
        return ToolResult(success=False, output="", error=f"File not found: {file_path}")

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if target not in content:
            return ToolResult(
                success=False,
                output="",
                error=f"Target text not found in {file_path}. The file may have changed.",
            )

        new_content = content.replace(target, replacement, 1)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return ToolResult(
            success=True,
            output=f"Successfully edited {file_path}",
            metadata={"file_path": file_path, "chars_removed": len(target), "chars_added": len(replacement)},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Error editing file: {e}")


async def _list_directory(
    path: str = ".",
    workspace_root: str = ".",
) -> ToolResult:
    """List files and directories in a path."""
    valid, abs_path, err = _validate_path(workspace_root, path)
    if not valid:
        return ToolResult(success=False, output="", error=err)

    if not os.path.isdir(abs_path):
        return ToolResult(success=False, output="", error=f"Directory not found: {path}")

    skip_dirs = {".git", "node_modules", "__pycache__", "dist", "build", "venv", ".venv", ".env"}
    try:
        entries = []
        for item in sorted(os.listdir(abs_path)):
            full = os.path.join(abs_path, item)
            if os.path.isdir(full):
                if item in skip_dirs:
                    continue
                entries.append(f"{item}/")
            else:
                entries.append(item)

        output = "\n".join(entries) if entries else "(empty directory)"
        return ToolResult(
            success=True,
            output=output,
            metadata={"path": path, "count": len(entries)},
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Error listing directory: {e}")


def create_filesystem_tools(workspace_root: str) -> list[ToolDefinition]:
    """Create all filesystem tools bound to a specific workspace root.

    Args:
        workspace_root: Absolute path to the workspace directory.

    Returns:
        List of ToolDefinition objects ready for registry.
    """
    import functools

    # Bind workspace_root into each executor
    read = functools.partial(_read_file, workspace_root=workspace_root)
    write = functools.partial(_write_file, workspace_root=workspace_root)
    edit = functools.partial(_edit_file, workspace_root=workspace_root)
    list_dir = functools.partial(_list_directory, workspace_root=workspace_root)

    return [
        ToolDefinition(
            name="read_file",
            description="Read the contents of a file. Returns the full file content as text.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from the workspace root.",
                    },
                },
                "required": ["file_path"],
            },
            executor=read,
            risk_level=RiskLevel.LOW,
            timeout=10.0,
        ),
        ToolDefinition(
            name="write_file",
            description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from the workspace root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to write to the file.",
                    },
                },
                "required": ["file_path", "content"],
            },
            executor=write,
            risk_level=RiskLevel.MEDIUM,
            timeout=10.0,
        ),
        ToolDefinition(
            name="edit_file",
            description="Edit a file by replacing the first occurrence of target text with replacement text. "
                        "Use this for surgical edits instead of rewriting the entire file.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file from the workspace root.",
                    },
                    "target": {
                        "type": "string",
                        "description": "The exact text to find and replace (must match exactly).",
                    },
                    "replacement": {
                        "type": "string",
                        "description": "The text to replace the target with.",
                    },
                },
                "required": ["file_path", "target", "replacement"],
            },
            executor=edit,
            risk_level=RiskLevel.MEDIUM,
            timeout=10.0,
        ),
        ToolDefinition(
            name="list_directory",
            description="List files and subdirectories in a directory. Skips common build/dependency directories.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the directory. Defaults to workspace root.",
                        "default": ".",
                    },
                },
                "required": [],
            },
            executor=list_dir,
            risk_level=RiskLevel.LOW,
            timeout=10.0,
        ),
    ]
