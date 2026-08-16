"""
Comprehensive tool registry with 20+ core tools.

All tools have:
  - name
  - description
  - input_schema (JSON schema)
  - executor (async callable)
  - timeout_seconds
  - permission_level (user, admin, internal)
  - risk_level (low, medium, high)
  - requires_approval (bool)
"""

import os
from collections.abc import Callable
from typing import Any

from .interfaces import ToolDefinition


class FileTools:
    """File operation tools."""

    @staticmethod
    async def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Read file contents."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            if start_line is not None or end_line is not None:
                start = start_line or 0
                end = end_line if end_line is not None else len(lines)
                lines = lines[start:end]
                content = "\n".join(lines)

            return content
        except Exception as e:
            raise Exception(f"Failed to read file {path}: {e!s}")

    @staticmethod
    async def write_file(path: str, content: str) -> str:
        """Write content to file."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"File written successfully: {path}"
        except Exception as e:
            raise Exception(f"Failed to write file {path}: {e!s}")

    @staticmethod
    async def create_file(path: str, content: str = "") -> str:
        """Create a new file."""
        try:
            if os.path.exists(path):
                raise Exception(f"File already exists: {path}")
            await FileTools.write_file(path, content)
            return f"File created successfully: {path}"
        except Exception as e:
            raise Exception(f"Failed to create file {path}: {e!s}")

    @staticmethod
    async def edit_file(path: str, old_text: str, new_text: str) -> str:
        """Replace text in file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_text not in content:
                raise Exception(f"Text not found in {path}")

            new_content = content.replace(old_text, new_text)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"File edited successfully: {path}"
        except Exception as e:
            raise Exception(f"Failed to edit file {path}: {e!s}")

    @staticmethod
    async def delete_file(path: str) -> str:
        """Delete a file."""
        try:
            os.remove(path)
            return f"File deleted: {path}"
        except Exception as e:
            raise Exception(f"Failed to delete file {path}: {e!s}")

    @staticmethod
    async def rename_file(old_path: str, new_path: str) -> str:
        """Rename a file."""
        try:
            os.rename(old_path, new_path)
            return f"File renamed from {old_path} to {new_path}"
        except Exception as e:
            raise Exception(f"Failed to rename file: {e!s}")


class DirectoryTools:
    """Directory operation tools."""

    @staticmethod
    async def list_directory(path: str, recursive: bool = False, max_depth: int = 2) -> dict[str, Any]:
        """List directory contents."""
        try:
            result = {"path": path, "items": []}

            if not os.path.isdir(path):
                raise Exception(f"Not a directory: {path}")

            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                result["items"].append({
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "path": item_path,
                })

            return result
        except Exception as e:
            raise Exception(f"Failed to list directory {path}: {e!s}")


class SearchTools:
    """Search and analysis tools."""

    @staticmethod
    async def search_text(directory: str, pattern: str, file_pattern: str = "*.py") -> list[dict[str, Any]]:
        """Search for text in files."""
        try:
            results = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith(file_pattern.replace("*", "")):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                for line_num, line in enumerate(f, 1):
                                    if pattern.lower() in line.lower():
                                        results.append({
                                            "file": file_path,
                                            "line": line_num,
                                            "content": line.strip(),
                                        })
                        except:
                            pass
            return results
        except Exception as e:
            raise Exception(f"Search failed: {e!s}")

    @staticmethod
    async def search_files(directory: str, filename_pattern: str) -> list[str]:
        """Search for files by name pattern."""
        try:
            results = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if filename_pattern.lower() in file.lower():
                        results.append(os.path.join(root, file))
            return results
        except Exception as e:
            raise Exception(f"File search failed: {e!s}")


class TerminalTools:
    """Terminal and command execution tools."""

    @staticmethod
    async def run_terminal_command(command: str, cwd: str | None = None, timeout: int = 30) -> dict[str, Any]:
        """Execute a terminal command."""
        try:
            from backend.app.tools.terminal_tool import run_shell_command
            class DummySession:
                def __init__(self, root: str | None):
                    self.workspace_root = os.path.abspath(root or ".")
                async def send_ws_message(self, msg: dict):
                    pass

            session = DummySession(cwd)
            output = await run_shell_command(session, command, timeout_seconds=timeout)
            is_failed = "Failed to execute command:" in output or "Command timed out" in output
            return {
                "exit_code": -1 if is_failed else 0,
                "stdout": output,
                "stderr": "",
                "success": not is_failed,
            }
        except Exception as e:
            raise Exception(f"Command execution failed: {e!s}")


class TestTools:
    """Testing and verification tools."""

    @staticmethod
    async def run_tests(cwd: str | None = None, test_pattern: str = "test_*.py") -> dict[str, Any]:
        """Run tests (pytest, unittest, etc.)."""
        try:
            # Try pytest first
            cmd = f"python -m pytest -v {test_pattern}"
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd)
            return {
                "framework": "pytest",
                "exit_code": result["exit_code"],
                "output": result["stdout"],
                "error": result["stderr"],
                "success": result["exit_code"] == 0,
            }
        except Exception as e:
            raise Exception(f"Test execution failed: {e!s}")

    @staticmethod
    async def run_linter(cwd: str | None = None) -> dict[str, Any]:
        """Run code linter (ruff, pylint, etc.)."""
        try:
            # Try ruff first
            cmd = "ruff check ."
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd)
            return {
                "linter": "ruff",
                "exit_code": result["exit_code"],
                "output": result["stdout"],
                "error": result["stderr"],
                "success": result["exit_code"] == 0,
            }
        except Exception as e:
            raise Exception(f"Linting failed: {e!s}")

    @staticmethod
    async def run_typecheck(cwd: str | None = None) -> dict[str, Any]:
        """Run type checker (pyright, mypy, etc.)."""
        try:
            # Try pyright first
            cmd = "pyright"
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd)
            return {
                "checker": "pyright",
                "exit_code": result["exit_code"],
                "output": result["stdout"],
                "error": result["stderr"],
                "success": result["exit_code"] == 0,
            }
        except Exception as e:
            raise Exception(f"Type checking failed: {e!s}")

    @staticmethod
    async def run_build(cwd: str | None = None) -> dict[str, Any]:
        """Run build command."""
        try:
            cmd = "python setup.py build 2>&1 || npm run build"
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd, timeout=60)
            return {
                "exit_code": result["exit_code"],
                "output": result["stdout"],
                "error": result["stderr"],
                "success": result["exit_code"] == 0,
            }
        except Exception as e:
            raise Exception(f"Build failed: {e!s}")


class GitTools:
    """Git operations."""

    @staticmethod
    async def git_status(cwd: str | None = None) -> dict[str, Any]:
        """Get git status."""
        try:
            result = await TerminalTools.run_terminal_command("git status --porcelain", cwd=cwd)
            return {
                "output": result["stdout"],
                "success": result["exit_code"] == 0,
            }
        except Exception as e:
            raise Exception(f"Git status failed: {e!s}")

    @staticmethod
    async def git_diff(cwd: str | None = None, file_path: str | None = None) -> str:
        """Get git diff."""
        try:
            cmd = "git diff" + (f" {file_path}" if file_path else "")
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd)
            return result["stdout"]
        except Exception as e:
            raise Exception(f"Git diff failed: {e!s}")

    @staticmethod
    async def git_log(cwd: str | None = None, num_commits: int = 10) -> str:
        """Get git log."""
        try:
            cmd = f"git log --oneline -n {num_commits}"
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd)
            return result["stdout"]
        except Exception as e:
            raise Exception(f"Git log failed: {e!s}")

    @staticmethod
    async def git_commit(message: str, cwd: str | None = None) -> dict[str, Any]:
        """Commit changes."""
        try:
            cmd = f'git commit -m "{message}"'
            result = await TerminalTools.run_terminal_command(cmd, cwd=cwd)
            return {
                "output": result["stdout"],
                "success": result["exit_code"] == 0,
            }
        except Exception as e:
            raise Exception(f"Git commit failed: {e!s}")

    @staticmethod
    async def git_branch(cwd: str | None = None) -> list[str]:
        """List git branches."""
        try:
            result = await TerminalTools.run_terminal_command("git branch", cwd=cwd)
            branches = [b.strip() for b in result["stdout"].split("\n") if b.strip()]
            return branches
        except Exception as e:
            raise Exception(f"Git branch failed: {e!s}")


class ToolRegistry:
    """Central registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register all default tools."""

        # File tools
        self.register(
            "read_file",
            "Read file contents",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "start_line": {"type": "integer", "description": "Start line (optional)"},
                    "end_line": {"type": "integer", "description": "End line (optional)"},
                },
                "required": ["path"],
            },
            FileTools.read_file,
            timeout_seconds=10,
            risk_level="low",
        )

        self.register(
            "write_file",
            "Write content to file",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            FileTools.write_file,
            timeout_seconds=10,
            risk_level="high",
            requires_approval=False,
        )

        self.register(
            "create_file",
            "Create a new file",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path"],
            },
            FileTools.create_file,
            timeout_seconds=10,
            risk_level="high",
        )

        self.register(
            "edit_file",
            "Replace text in file",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
            },
            FileTools.edit_file,
            timeout_seconds=10,
            risk_level="high",
        )

        self.register(
            "delete_file",
            "Delete a file",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
            FileTools.delete_file,
            timeout_seconds=10,
            risk_level="high",
            requires_approval=True,
        )

        self.register(
            "rename_file",
            "Rename a file",
            {
                "type": "object",
                "properties": {
                    "old_path": {"type": "string"},
                    "new_path": {"type": "string"},
                },
                "required": ["old_path", "new_path"],
            },
            FileTools.rename_file,
            timeout_seconds=10,
            risk_level="high",
        )

        # Directory tools
        self.register(
            "list_directory",
            "List directory contents",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "recursive": {"type": "boolean"},
                    "max_depth": {"type": "integer"},
                },
                "required": ["path"],
            },
            DirectoryTools.list_directory,
            timeout_seconds=10,
            risk_level="low",
        )

        # Search tools
        self.register(
            "search_text",
            "Search for text in files",
            {
                "type": "object",
                "properties": {
                    "directory": {"type": "string"},
                    "pattern": {"type": "string"},
                    "file_pattern": {"type": "string"},
                },
                "required": ["directory", "pattern"],
            },
            SearchTools.search_text,
            timeout_seconds=30,
            risk_level="low",
        )

        self.register(
            "search_files",
            "Search for files by name",
            {
                "type": "object",
                "properties": {
                    "directory": {"type": "string"},
                    "filename_pattern": {"type": "string"},
                },
                "required": ["directory", "filename_pattern"],
            },
            SearchTools.search_files,
            timeout_seconds=30,
            risk_level="low",
        )

        # Terminal tools
        self.register(
            "run_terminal_command",
            "Execute a shell command",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
            TerminalTools.run_terminal_command,
            timeout_seconds=60,
            risk_level="high",
            requires_approval=False,
        )

        self.register(
            "run_command",
            "Execute a shell command (alias for run_terminal_command)",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
            TerminalTools.run_terminal_command,
            timeout_seconds=60,
            risk_level="high",
            requires_approval=False,
        )

        # Testing tools
        self.register(
            "run_tests",
            "Run test suite",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                    "test_pattern": {"type": "string"},
                },
                "required": [],
            },
            TestTools.run_tests,
            timeout_seconds=120,
            risk_level="low",
        )

        self.register(
            "run_linter",
            "Run code linter",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                },
                "required": [],
            },
            TestTools.run_linter,
            timeout_seconds=60,
            risk_level="low",
        )

        self.register(
            "run_typecheck",
            "Run type checker",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                },
                "required": [],
            },
            TestTools.run_typecheck,
            timeout_seconds=60,
            risk_level="low",
        )

        self.register(
            "run_build",
            "Run build process",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                },
                "required": [],
            },
            TestTools.run_build,
            timeout_seconds=180,
            risk_level="medium",
        )

        # Git tools
        self.register(
            "git_status",
            "Get git status",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                },
                "required": [],
            },
            GitTools.git_status,
            timeout_seconds=10,
            risk_level="low",
        )

        self.register(
            "git_diff",
            "Get git diff",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                    "file_path": {"type": "string"},
                },
                "required": [],
            },
            GitTools.git_diff,
            timeout_seconds=10,
            risk_level="low",
        )

        self.register(
            "git_log",
            "Get git log",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                    "num_commits": {"type": "integer"},
                },
                "required": [],
            },
            GitTools.git_log,
            timeout_seconds=10,
            risk_level="low",
        )

        self.register(
            "git_commit",
            "Commit changes",
            {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "cwd": {"type": "string"},
                },
                "required": ["message"],
            },
            GitTools.git_commit,
            timeout_seconds=10,
            risk_level="high",
        )

        self.register(
            "git_branch",
            "List git branches",
            {
                "type": "object",
                "properties": {
                    "cwd": {"type": "string"},
                },
                "required": [],
            },
            GitTools.git_branch,
            timeout_seconds=10,
            risk_level="low",
        )

    def register(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        executor: Callable,
        timeout_seconds: int = 30,
        permission_level: str = "user",
        risk_level: str = "low",
        requires_approval: bool = False,
    ) -> None:
        """Register a new tool."""
        tool_def = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            executor=executor,
            timeout_seconds=timeout_seconds,
            permission_level=permission_level,
            risk_level=risk_level,
            requires_approval=requires_approval,
        )
        self._tools[name] = tool_def

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        if isinstance(name, str) and "<|channel|>" in name:
            name = name.split("<|channel|>")[0]
        return self._tools.get(name)

    def get_all(self) -> dict[str, ToolDefinition]:
        """Get all tools."""
        return self._tools.copy()

    def list_tools(self) -> list[dict[str, str]]:
        """List all tools with descriptions."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level,
                "timeout": tool.timeout_seconds,
            }
            for tool in self._tools.values()
        ]
