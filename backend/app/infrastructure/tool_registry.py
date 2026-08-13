import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, Field

logger = logging.getLogger("devpilot.infrastructure.tool_registry")

@dataclass
class ToolDefinition:
    name: str
    version: str
    description: str
    input_schema: Type[BaseModel]
    output_schema: Optional[Type[BaseModel]]
    capabilities: List[str]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    timeout: float = 60.0
    output_limit: int = 1048576  # 1MB
    network_policy: str = "DENY"  # ALLOW, ALLOW_SPECIFIC, DENY
    sandbox_required: bool = True
    idempotent: str = "non-idempotent"  # idempotent, conditionally idempotent, non-idempotent

# --- Strongly Typed Input Schemas ---

class ReadFileInput(BaseModel):
    path: str = Field(..., description="The path of the file to read.")

class WriteFileInput(BaseModel):
    path: str = Field(..., description="The path of the file to write.")
    content: str = Field(..., description="The content to write to the file.")

class EditFileInput(BaseModel):
    path: str = Field(..., description="The path of the file to edit.")
    target: str = Field(..., description="The target content to be replaced.")
    replacement: str = Field(..., description="The replacement content.")

class DeleteFileInput(BaseModel):
    path: str = Field(..., description="The path of the file to delete.")

class ListDirectoryInput(BaseModel):
    path: Optional[str] = Field(None, description="Optional path to list directory of. Defaults to workspace root.")

class SearchCodebaseInput(BaseModel):
    query: str = Field(..., description="The search term or pattern to look for.")

class RunTerminalCommandInput(BaseModel):
    command: str = Field(..., description="The exact shell command to execute.")

class GlobInput(BaseModel):
    pattern: str = Field(..., description="The glob pattern to match files against.")

class WebFetchInput(BaseModel):
    url: str = Field(..., description="The URL to fetch.")

class ApplyPatchInput(BaseModel):
    patch: str = Field(..., description="The git diff patch to apply.")

class TodoWriteInput(BaseModel):
    todos: List[str] = Field(..., description="The list of todos to write.")

class TodoReadInput(BaseModel):
    pass

class QuestionInput(BaseModel):
    question: str = Field(..., description="The question to ask the user.")

class SpawnSubagentInput(BaseModel):
    prompt: str = Field(..., description="The prompt or task for the subagent.")

class DelegateToAgentInput(BaseModel):
    agent_name: str = Field(..., description="The name of the agent to delegate to.")
    task_description: str = Field(..., description="The description of the task.")

class SearchWebInput(BaseModel):
    query: str = Field(..., description="The search query.")

class OpenLiveServerInput(BaseModel):
    pass

# --- Central Tool Registry ---

class ToolRegistry:
    _registry: Dict[str, ToolDefinition] = {}
    _aliases: Dict[str, str] = {}

    @classmethod
    def register(cls, tool: ToolDefinition):
        cls._registry[tool.name] = tool

    @classmethod
    def register_alias(cls, alias: str, canonical_name: str):
        cls._aliases[alias.lower().strip()] = canonical_name

    @classmethod
    def get_tool(cls, name: str) -> Optional[ToolDefinition]:
        canonical = cls._aliases.get(name.lower().strip(), name.lower().strip())
        return cls._registry.get(canonical)

    @classmethod
    def get_all_tools(cls) -> List[ToolDefinition]:
        return list(cls._registry.values())

    @classmethod
    def get_handler(cls, canonical_name: str) -> Callable:
        """Lazily load tool handlers to prevent circular imports."""
        name = canonical_name.lower().strip()
        if name == "read_file":
            from backend.app.tools.read_tool import read_file
            return read_file
        elif name in ("write_file", "edit_file"):
            from backend.app.tools.write_tool import write_or_edit_file
            return write_or_edit_file
        elif name == "delete_file":
            from backend.app.tools.delete_tool import delete_file
            return delete_file
        elif name == "list_directory":
            from backend.app.tools.list_tool import list_directory
            return list_directory
        elif name == "search_codebase":
            from backend.app.tools import search_tool
            return search_tool.search_codebase
        elif name == "run_terminal_command":
            from backend.app.tools import terminal_tool
            return terminal_tool.run_terminal_command
        elif name == "glob":
            from backend.app.tools.glob_tool import glob_search
            return glob_search
        elif name == "web_fetch":
            from backend.app.tools.web_fetch_tool import web_fetch
            return web_fetch
        elif name == "apply_patch":
            from backend.app.tools.patch_tool import apply_patch
            return apply_patch
        elif name == "todo_write":
            from backend.app.tools.todo_tool import todo_write
            return todo_write
        elif name == "todo_read":
            from backend.app.tools.todo_tool import todo_read
            return todo_read
        elif name == "question":
            from backend.app.tools.question_tool import ask_question
            return ask_question
        elif name == "spawn_subagent":
            from backend.app.tools.spawn_subagent import spawn_subagent
            return spawn_subagent
        elif name in ("search_web", "tavily_search", "web_search"):
            from backend.app.tools.web_search_tool import search_web
            return search_web
        elif name == "open_with_live_server":
            from backend.app.tools.live_server_tool import open_with_live_server
            return open_with_live_server
        else:
            raise NotImplementedError(f"Handler for canonical tool '{name}' not found.")

# Register all canonical tool definitions
ToolRegistry.register(ToolDefinition("read_file", "1.0", "Read content of a file", ReadFileInput, None, ["filesystem.read"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("write_file", "1.0", "Write content to a file", WriteFileInput, None, ["filesystem.write"], "HIGH", idempotent="conditionally idempotent"))
ToolRegistry.register(ToolDefinition("edit_file", "1.0", "Replace a block of content in a file", EditFileInput, None, ["filesystem.write"], "HIGH", idempotent="conditionally idempotent"))
ToolRegistry.register(ToolDefinition("delete_file", "1.0", "Delete a file", DeleteFileInput, None, ["filesystem.delete"], "CRITICAL", idempotent="conditionally idempotent"))
ToolRegistry.register(ToolDefinition("list_directory", "1.0", "List contents of a directory", ListDirectoryInput, None, ["filesystem.read"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("search_codebase", "1.0", "Search codebase for a query using ripgrep", SearchCodebaseInput, None, ["filesystem.read"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("run_terminal_command", "1.0", "Run a terminal command in isolated shell", RunTerminalCommandInput, None, ["terminal.execute"], "CRITICAL", idempotent="non-idempotent"))
ToolRegistry.register(ToolDefinition("glob", "1.0", "Glob search workspace files", GlobInput, None, ["filesystem.read"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("web_fetch", "1.0", "Fetch content of a URL", WebFetchInput, None, ["network.request"], "MEDIUM", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("apply_patch", "1.0", "Apply a git diff patch", ApplyPatchInput, None, ["filesystem.write"], "HIGH", idempotent="conditionally idempotent"))
ToolRegistry.register(ToolDefinition("todo_write", "1.0", "Write list of todos", TodoWriteInput, None, ["filesystem.write"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("todo_read", "1.0", "Read current todos", TodoReadInput, None, ["filesystem.read"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("question", "1.0", "Ask the user a clarifying question", QuestionInput, None, ["interaction.ask"], "LOW", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("spawn_subagent", "1.0", "Spawn a specialized subagent for subtask", SpawnSubagentInput, None, ["agent.spawn"], "MEDIUM", idempotent="non-idempotent"))
ToolRegistry.register(ToolDefinition("search_web", "1.0", "Search the web using Tavily API", SearchWebInput, None, ["network.request"], "MEDIUM", idempotent="idempotent"))
ToolRegistry.register(ToolDefinition("open_with_live_server", "1.0", "Serve static web files using a local server", OpenLiveServerInput, None, ["terminal.execute"], "MEDIUM", idempotent="idempotent"))

# Consolidate all tool aliases (Section 3 requirement)
aliases = {
    "list_files": "list_directory",
    "list_dir": "list_directory",
    "dir": "list_directory",
    "ls": "list_directory",
    "get_files": "list_directory",
    "show_files": "list_directory",
    "view_files": "list_directory",
    "see_files": "list_directory",
    "workspace_files": "list_directory",
    "view_file": "read_file",
    "get_file": "read_file",
    "read_workspace_file": "read_file",
    "open_file": "read_file",
    "cat_file": "read_file",
    "find_files": "search_codebase",
    "search_files": "search_codebase",
    "search_code": "search_codebase",
    "grep": "search_codebase",
    "execute_command": "run_terminal_command",
    "run_command": "run_terminal_command",
    "terminal": "run_terminal_command",
    "shell_command": "run_terminal_command",
    "live_server": "open_with_live_server",
    "start_live_server": "open_with_live_server",
    "open_live_server": "open_with_live_server",
    "serve_html": "open_with_live_server",
    "run_html": "open_with_live_server",
    "preview_html": "open_with_live_server",
    "glob_search": "glob",
    "find_pattern": "glob",
    "glob_files": "glob",
    "fetch_url": "web_fetch",
    "fetch": "web_fetch",
    "http_get": "web_fetch",
    "get_url": "web_fetch",
    "read_url": "web_fetch",
    "patch": "apply_patch",
    "apply_diff": "apply_patch",
    "apply_git_diff": "apply_patch",
    "write_todo": "todo_write",
    "update_todo": "todo_write",
    "set_todos": "todo_write",
    "read_todo": "todo_read",
    "get_todos": "todo_read",
    "list_todos": "todo_read",
    "create_file": "write_file",
    "write_to_file": "write_file",
    "save_file": "write_file",
    "make_file": "write_file",
    "new_file": "write_file",
    "delegate_agent": "delegate_to_agent",
    "delegate": "delegate_to_agent",
    "run_agent": "delegate_to_agent",
    "call_agent": "delegate_to_agent",
    "agent_delegate": "delegate_to_agent",
    "agent": "delegate_to_agent",
    "ask_user": "question",
    "ask_question": "question",
    "clarify": "question",
    "prompt_user": "question",
    "delete": "delete_file",
    "delete_path": "delete_file",
    "remove_file": "delete_file",
    "remove": "delete_file",
    "rm": "delete_file",
    "tavily_search": "search_web",
    "web_search": "search_web",
}

for alias, canonical in aliases.items():
    ToolRegistry.register_alias(alias, canonical)
