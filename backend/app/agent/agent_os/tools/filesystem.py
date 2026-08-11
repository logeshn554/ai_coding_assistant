"""
Filesystem Tools — Implements real read_file, write_file, and edit_file tools with path-sandbox security.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any, Dict

from agent_os.tools.base import Tool, ToolResult


class ReadFileTool(Tool):
    """Read file content from the local workspace."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = pathlib.Path(workspace_root).resolve()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a UTF-8 text file from the workspace."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to file from workspace root",
                }
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        try:
            # Resolve absolute path and enforce path isolation
            full_path = (self.workspace_root / path).resolve()
            if not str(full_path).startswith(str(self.workspace_root)):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Security Error: Path escape attempt: {path}",
                )

            if not full_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {path}",
                )

            content = full_path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                metadata={"size_bytes": len(content.encode("utf-8"))},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading file '{path}': {e}",
            )


class WriteFileTool(Tool):
    """Write (create or overwrite) file contents in the local workspace."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = pathlib.Path(workspace_root).resolve()

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file in the workspace (creates or overwrites)."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to file from workspace root",
                },
                "content": {
                    "type": "string",
                    "description": "Content string to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> ToolResult:
        try:
            # Resolve absolute path and enforce path isolation
            full_path = (self.workspace_root / path).resolve()
            if not str(full_path).startswith(str(self.workspace_root)):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Security Error: Path escape attempt: {path}",
                )

            # Create parent directories dynamically
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write to temporary file then replace to prevent partial writes
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=full_path.parent,
                delete=False,
                encoding="utf-8"
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            os.replace(tmp_path, full_path)

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to '{path}'",
                metadata={"size_bytes": len(content.encode("utf-8"))},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error writing to file '{path}': {e}",
            )


class EditFileTool(Tool):
    """Surgical search-and-replace edit on file content."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = pathlib.Path(workspace_root).resolve()

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Replace the first occurrence of a specific section of a file with new content."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to file from workspace root",
                },
                "target": {
                    "type": "string",
                    "description": "Exact block of text in the file to find and replace",
                },
                "replacement": {
                    "type": "string",
                    "description": "The replacement text",
                },
            },
            "required": ["path", "target", "replacement"],
        }

    async def execute(self, path: str, target: str, replacement: str, **kwargs: Any) -> ToolResult:
        try:
            # Resolve absolute path and enforce path isolation
            full_path = (self.workspace_root / path).resolve()
            if not str(full_path).startswith(str(self.workspace_root)):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Security Error: Path escape attempt: {path}",
                )

            if not full_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {path}",
                )

            content = full_path.read_text(encoding="utf-8")
            if target not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Target text block not found in {path}",
                )

            new_content = content.replace(target, replacement, 1)
            full_path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True,
                output=f"Successfully edited file '{path}'",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error editing file '{path}': {e}",
            )
