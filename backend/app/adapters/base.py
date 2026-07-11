from typing import AsyncGenerator, List, Dict, Any

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
        "name": "scan_for_bugs",
        "description": "Scans the entire workspace folder, reads all code files, and uses a background LLM process to analyze them and generate a summary of identified bugs and code quality issues. Use this to find bugs across the codebase.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]
