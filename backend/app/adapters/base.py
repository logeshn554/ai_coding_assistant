from typing import AsyncGenerator, List, Dict, Any, Optional, Tuple
import asyncio
import json
import logging
import os

logger = logging.getLogger("devpilot.adapters")

class ModelAdapter:
    """
    Base class for all provider adapters.

    Design rule: there is exactly one subclass — LLMAdapter (adapters/llm.py) —
    covering every provider. Providers differ only by config (api_key,
    base_url, model_name, provider string), never by a separate class or
    file. Tool-call JSON parsing, chunk formatting, error handling, and the
    bug-scan injection are common to every provider and live here so they
    behave identically no matter which model API is being called.
    """
    _last_bug_report: str = ""
    _last_bug_report_time: float = 0.0


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

    # ------------------------------------------------------------------
    # Shared helpers — common to every provider adapter. Do NOT duplicate
    # this logic inside a provider-specific adapter file.
    # ------------------------------------------------------------------

    @staticmethod
    def parse_tool_arguments(tool_name: str, raw_json: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """Common JSON parsing for tool-call arguments, with a fallback and a
        standardized error message when the model produces malformed JSON.
        Used by every provider adapter so a malformed tool call is handled
        identically regardless of which model API produced it."""
        try:
            return json.loads(raw_json), None
        except Exception:
            try:
                return json.loads(raw_json.strip()), None
            except Exception:
                error_msg = (
                    f"Error: model produced malformed JSON arguments for tool '{tool_name}': "
                    f"{raw_json[:200]}. Tool was not executed."
                )
                return {"raw_input": raw_json}, error_msg

    @staticmethod
    def build_tool_call_chunk(
        tool_id: str,
        tool_name: str,
        parsed_input: Dict[str, Any],
        error_msg: Optional[str] = None,
        thought_signature: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Standard shape for a tool-call chunk, shared across all providers."""
        chunk: Dict[str, Any] = {
            "type": "tool_call",
            "id": tool_id,
            "name": tool_name,
            "input": parsed_input,
        }
        if error_msg:
            chunk["error"] = error_msg
        if thought_signature is not None:
            chunk["thought_signature"] = thought_signature
        return chunk

    @staticmethod
    def build_text_chunk(content: str) -> Dict[str, Any]:
        return {"type": "text", "content": content}

    @staticmethod
    def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
        model_name = (model_name or "").lower()
        
        # Default fallback pricing (Claude 3.5 Sonnet / standard medium model)
        input_rate = 3.00
        output_rate = 15.00
        
        if "opus" in model_name:
            input_rate = 15.00
            output_rate = 75.00
        elif "sonnet" in model_name:
            input_rate = 3.00
            output_rate = 15.00
        elif "haiku" in model_name:
            input_rate = 0.80
            output_rate = 4.00
        elif "gpt-4o-mini" in model_name:
            input_rate = 0.15
            output_rate = 0.60
        elif "gpt-4o" in model_name:
            input_rate = 2.50
            output_rate = 10.00
        elif "gpt-4" in model_name or "turbo" in model_name:
            input_rate = 10.00
            output_rate = 30.00
        elif "o1-mini" in model_name:
            input_rate = 3.00
            output_rate = 12.00
        elif "o1" in model_name:
            input_rate = 15.00
            output_rate = 60.00
        elif "gemini-1.5-pro" in model_name or "gemini-pro" in model_name:
            input_rate = 1.25
            output_rate = 5.00
        elif "gemini-1.5-flash" in model_name or "gemini-flash" in model_name:
            input_rate = 0.075
            output_rate = 0.30
            
        return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000

    @staticmethod
    def build_usage_chunk(input_tokens: int, output_tokens: int, model_name: str = "unknown") -> Dict[str, Any]:
        cost = ModelAdapter.calculate_cost(model_name, input_tokens, output_tokens)
        return {
            "type": "usage",
            "input_tokens": input_tokens or 0,
            "output_tokens": output_tokens or 0,
            "cost_usd": cost,
        }

    @staticmethod
    def build_done_chunk(stop_reason: str) -> Dict[str, Any]:
        return {"type": "done", "stop_reason": stop_reason}

    async def generate_bug_report(self) -> str:
        """
        Scans the entire workspace for bugs using the `scan_for_bugs` tool and
        returns a concise JSON report. Identical for every provider, so it
        lives here once instead of being copy-pasted into each adapter.
        """
        from ..tools.scan_for_bugs import scan_for_bugs_sync as scan_for_bugs
        try:
            loop = asyncio.get_event_loop()
            bug_data = await loop.run_in_executor(None, scan_for_bugs, os.getcwd())
        except Exception as e:
            logger.error(f"Failed to execute scan_for_bugs: {e}")
            raise

        try:
            report = json.dumps(bug_data, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to serialize bug data to JSON: {e}")
            raise

        max_length = 2000  # characters
        if len(report) > max_length:
            report = report[: max_length - 3] + "..."
        return report

    @staticmethod
    async def maybe_inject_bug_scan(
        messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """If the scan_for_bugs tool was supplied, run it once and inject the
        result as a user message right after the first turn, before the model
        generates a response. Shared across all providers so this behaves the
        same regardless of which model API is being called."""
        if not any(tool.get("name") == "scan_for_bugs" for tool in tools):
            return messages
        try:
            import time
            now = time.time()
            if (now - ModelAdapter._last_bug_report_time < 60.0) and ModelAdapter._last_bug_report:
                bug_report = ModelAdapter._last_bug_report
            else:
                from ..tools.scan_for_bugs import scan_for_bugs as _scan_for_bugs_func
                result = _scan_for_bugs_func()
                bug_report = await result if hasattr(result, "__await__") else result
                bug_report = str(bug_report).strip()
                ModelAdapter._last_bug_report = bug_report
                ModelAdapter._last_bug_report_time = now

            report_message = {
                "role": "user",
                "content": (
                    "[AUTOMATED WORKSPACE SCAN — do not reference this as a user request]\n"
                    f"Bug scan results for context:\n{bug_report}"
                ),
            }
            msg_list = list(messages)
            if msg_list:
                return [msg_list[0], report_message] + msg_list[1:]
            return [report_message]
        except Exception as e:
            logger.error(f"Failed to run scan_for_bugs tool: {e}")
            return messages


# Standardized tool definitions exposed to LLMs
AVAILABLE_TOOLS = [
    {
        "name": "list_directory",
        "description": (
            "List files and subfolders in a workspace directory. "
            "Set recursive=true to walk ALL sub-folders in one call — use this when the project "
            "has many folders so you see the full structure without multiple round-trips. "
            "Returns name, path, is_dir, size, mtime, and child_count for each entry."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to list (e.g. '.', 'src', 'backend'). Defaults to workspace root."
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, walk all sub-folders recursively and return the full tree. Default false (one level only)."
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum folder depth for recursive listing (default 4, max 10)."
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
        "name": "delete_file",
        "description": "Deletes an existing file or folder in the workspace. Always double-check before deleting critical files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path of the file or folder to delete (e.g. 'index.html')."
                }
            },
            "required": ["path"]
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
        "description": "Runs a shell command in the workspace directory (e.g. 'npm run build', 'python -m pytest'). This tool MUST be used to start dev servers (e.g. 'npm run dev', 'npm start', 'python backend/launcher.py'). Check the project's 'package.json' 'scripts' field first to identify correct startup commands. Returns stdout/stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute."
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Optional timeout override in seconds (default 30, maximum 300)."
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
        "description": "Launches a Live Server ONLY for static HTML files or static sites in the workspace with NO build steps (e.g. basic index.html files). Do NOT use this tool for modern frameworks like React, Vite, Next.js, Vue, or Angular — use run_terminal_command instead to start their dev servers.",
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
    },
    {
        "name": "glob",
        "description": (
            "Find files matching a glob pattern inside the workspace. "
            "Supports standard wildcards: * (any chars in one path segment), "
            "** (any path depth), ? (single char). "
            "Examples: '**/*.py', 'src/**/*.tsx', '*.json', 'backend/**/*.py'. "
            "Returns a list of relative file paths. Use this to discover files "
            "before reading them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match, e.g. '**/*.py', 'src/**/*.tsx'."
                },
                "base_path": {
                    "type": "string",
                    "description": "Optional sub-directory to search within (relative to workspace root). Defaults to workspace root."
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "web_fetch",
        "description": (
            "Fetch the content of any public URL and return it as readable plain text. "
            "Strips HTML tags and formatting. Use this to read documentation pages, "
            "API references, GitHub files, StackOverflow answers, or any web resource. "
            "Note: requires network access and respects robots.txt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch (must start with http:// or https://)."
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default 40000, max 40000)."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "apply_patch",
        "description": (
            "Apply a unified diff (patch) to one or more workspace files. "
            "The patch must be in standard unified diff format as produced by 'git diff' or 'diff -u'. "
            "Supports multi-file patches. Will ask for user confirmation before writing, "
            "unless auto-apply is enabled. Use this to apply large, structured changes "
            "across multiple files at once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "The full unified diff text to apply (--- a/file, +++ b/file, @@ ... hunk format)."
                }
            },
            "required": ["patch"]
        }
    },
    {
        "name": "todo_write",
        "description": (
            "Create or update your structured agent todo list to track tasks. "
            "Each item has 'text' (description), 'id' (auto-assigned if omitted), "
            "and 'status' ('pending', 'in_progress', or 'done'). "
            "Use this at the start of complex tasks to plan your steps, and update "
            "statuses as you complete them. Set merge=true to update specific items "
            "without replacing the whole list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "Array of todo items. Each item: {text: string, id?: string, status?: 'pending'|'in_progress'|'done'}.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "id": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "done"]}
                        },
                        "required": ["text"]
                    }
                },
                "merge": {
                    "type": "boolean",
                    "description": "If true, merge with existing list. If false (default), replace entirely."
                }
            },
            "required": ["todos"]
        }
    },
    {
        "name": "todo_read",
        "description": (
            "Read your current agent todo list. Returns all tasks with their "
            "status (pending, in_progress, done). Call this to check what you "
            "still need to do in a multi-step task."
        ),
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "question",
        "description": (
            "Ask the user a clarifying question and wait for their answer before continuing. "
            "Use this when you genuinely cannot proceed without user input — for example, "
            "when requirements are ambiguous, a critical decision requires human judgment, "
            "or you need credentials/secrets. Do NOT overuse this; resolve ambiguity "
            "from context when possible. Provide options[] to make answering easier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask the user."
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of suggested answer choices."
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context shown below the question."
                }
            },
            "required": ["question"]
        }
    }
]