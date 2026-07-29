from typing import AsyncGenerator, List, Dict, Any
import os

class ModelAdapter:
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

    async def stream_chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]], 
        system_prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields chunks of the model response:
        - Text chunk: {"type": "text", "content": "str"}
        - Tool call chunk: {"type": "tool_call", "id": "str", "name": "str", "input": {...}}
        - Done chunk: {"type": "done", "stop_reason": "tool_use" | "stop"}
        """
        raise NotImplementedError("Subclasses must implement stream_chat")


# Standardized tool definitions exposed to LLMs
AVAILABLE_TOOLS = [
    {
        "name": "list_directory",
        "description": "Lists the files and subfolders in a specific workspace directory (relative path). Returns name, relative path, size, and whether it's a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the directory to list (e.g. '.', 'src', 'backend'). Defaults to '.'."
                }
            }
        }
    },
    {
        "name": "read_file",
        "description": "Reads the entire contents of a file in the workspace. Use this to inspect file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to read (e.g. 'src/App.tsx')."
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Creates a new file or overwrites an existing file with the specified content. Always double-check before overwriting critical files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to write (e.g. 'src/components/Button.tsx')."
                },
                "content": {
                    "type": "string",
                    "description": "The complete text content of the file."
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Edits an existing file using a search-and-replace block. Target must match the exact block in the file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to edit (e.g. 'src/App.tsx')."
                },
                "target": {
                    "type": "string",
                    "description": "The exact block of code to search for. Must match exactly, including leading spaces/tabs."
                },
                "replacement": {
                    "type": "string",
                    "description": "The replacement code block to swap in."
                }
            },
            "required": ["path", "target", "replacement"]
        }
    },
    {
        "name": "run_terminal_command",
        "description": "Runs a shell command in the workspace directory (e.g. 'npm run build', 'python -m pytest'). Returns stdout/stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "search_codebase",
        "description": "Searches the codebase for lines containing a specific text query or regex pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text or regex pattern to search for."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "open_with_live_server",
        "description": "Launches a Live Server for an HTML file or static site in the workspace and returns the localhost URL (e.g., http://localhost:5500/index.html). Use when the user asks to open, run, or preview HTML files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the HTML file to open with Live Server (e.g., 'index.html', 'game.html'). If omitted, automatically finds the primary HTML file."
                },
                "port": {
                    "type": "integer",
                    "description": "Port to run the live HTTP server on (default 5500)."
                }
            }
        }
    },
    {
        "name": "spawn_subagent",
        "description": (
            "Spawn a disposable, stateless, read-only sub-agent to answer a single "
            "self-contained question about the codebase. "
            "Stateless, one-shot. The sub-agent cannot ask follow-up questions — "
            "prompt must be fully self-contained. "
            "The sub-agent is restricted to read-only tools (list_directory, read_file, "
            "search_codebase) and cannot write files, edit files, or run terminal commands. "
            "Use this when you need to delegate a focused research task without consuming "
            "the parent session's tool-call budget."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "A fully self-contained prompt for the sub-agent. "
                        "Include all necessary context — the sub-agent has no access "
                        "to the parent conversation history."
                    )
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "delegate_to_agent",
        "description": (
            "Delegate a specific, self-contained task to one specialist agent "
            "(e.g. 'Coding Agent', 'Testing Agent', 'Frontend Developer Agent'). "
            "Call this once per agent you need this turn; independent agents may be "
            "called in parallel within the same turn. Call again in later turns as prior "
            "agents' outputs become available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Exact specialist agent name"},
                "task_description": {"type": "string", "description": "Specific, actionable task for that agent"}
            },
            "required": ["agent_name", "task_description"]
        }
    }
]