import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any
from .adapters.base import AVAILABLE_TOOLS
from .adapters.anthropic import AnthropicAdapter
from .adapters.openai import OpenAIAdapter
from .files import (
    safe_path,
    list_workspace_dir,
    read_workspace_file,
    write_workspace_file,
    delete_workspace_item,
    search_workspace_codebase,
    get_codebase_contents
)
from .async_files import async_write_workspace_file

from .orchestrator import AgentOrchestrator

logger = logging.getLogger("devpilot.agent")

class AgentSession:
    def __init__(self, workspace_root: str, profile: dict, send_ws_message, permission_manager=None):
        self.workspace_root = workspace_root
        self.profile = profile
        self.send_ws_message = send_ws_message
        self.permission_manager = permission_manager
        self.orchestrator = AgentOrchestrator()
        self.conversation_history = []
        self.pending_confirmations = {}  # tool_call_id -> {"event": asyncio.Event(), "approved": bool}
        self.max_turns = 25
        self.audit_log = []
        self.is_running = False
        self.active_task = None

    def log_audit(self, tool_name: str, arguments: dict, status: str, details: str = ""):
        log_entry = {
            "tool": tool_name,
            "arguments": arguments,
            "status": status,
            "details": details
        }
        self.audit_log.append(log_entry)
        logger.info(f"Audit Log: {json.dumps(log_entry)}")

    def _get_adapter(self, is_agent: bool = False):
        fmt = self.profile.get("api_format", "openai")
        key = self.profile.get("api_key", "")
        url = self.profile.get("base_url", "")
        model = self.profile.get("model_name", "")
        
        if is_agent:
            from .config import ConfigManager
            custom_agent_model = ConfigManager().get_agent_model_name()
            if custom_agent_model:
                model = custom_agent_model
        
        if fmt == "anthropic":
            return AnthropicAdapter(key, url, model)
        return OpenAIAdapter(key, url, model)

    def _get_tools_for_mode(self, mode: str) -> list:
        read_only_tools = {"list_directory", "read_file", "search_codebase"}
        if mode in ("Ask", "Plan"):
            return [t for t in AVAILABLE_TOOLS if t["name"] in read_only_tools]
        return AVAILABLE_TOOLS

    def _get_system_prompt(self, mode: str) -> str:
        base_prompt = (
            "You are DevPilot, a highly skilled AI coding assistant integrated into the user's workspace.\n"
            "You have access to specific tools to interact with the project.\n"
            f"Your current workspace root is: {self.workspace_root}\n"
            "When referencing files, always use paths relative to the workspace root.\n"
            "Always follow best practices, write clean, well-documented code.\n"
        )
        
        if mode == "Ask":
            return base_prompt + (
                "You are currently in ASK mode. You can answer questions and read files, but you cannot "
                "perform any write operations or run commands. Your tools are strictly read-only."
            )
        elif mode == "Plan":
            return base_prompt + (
                "You are currently in PLAN mode. You MUST NOT make any direct file edits or run terminal commands.\n"
                "Your goal is to inspect the codebase and respond with a structured, step-by-step plan "
                "outlining what files need to be modified, what code should be added/changed, and why.\n"
                "Explain the plan clearly. Do NOT attempt to use write tools; you only have read-only tools."
            )
        else:
            return base_prompt + (
                "You are currently in AGENT mode. You have full capability to read, write, edit files, and "
                "run terminal commands.\n"
                "Propose changes step-by-step. For editing existing files, use the `edit_file` tool to "
                "provide target search blocks and replacement blocks.\n"
                "Make sure your target blocks are unique and match the file content exactly (including spacing, tabs, and newlines).\n"
                "Before editing a file, always read it first to ensure you have the exact, up-to-date content."
            )

    async def handle_user_message(self, text: str, mode: str, auto_apply: bool = False):
        """
        Runs the agent loop for a user query.
        """
        if self.is_running:
            await self.send_ws_message({
                "type": "text_delta",
                "content": "\n[Error: Agent is already running another task.]\n"
            })
            await self.send_ws_message({"type": "session_done"})
            return
            
        self.is_running = True
        try:
            # Append user request to history
            self.conversation_history.append({"role": "user", "content": text})
        
            # Trigger multi-agent collaboration flow
            if mode == "Agent":
                try:
                    await self.orchestrator.run_task(text, self)
                except Exception as e:
                    logger.error(f"Orchestrator run failed: {str(e)}")
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": f"\n[Orchestrator Error: {str(e)}]\n"
                    })
                await self.send_ws_message({"type": "session_done"})
                return

            adapter = self._get_adapter()
            system_prompt = self._get_system_prompt(mode)
            tools = self._get_tools_for_mode(mode)
            
            turn = 0
            while turn < self.max_turns:
                turn += 1
                
                # Send status update
                await self.send_ws_message({
                    "type": "status",
                    "status": "thinking",
                    "message": f"Thinking (Turn {turn}/{self.max_turns})..."
                })
                
                response_text = ""
                tool_calls_to_run = []
                
                # 1. Stream the model's text response and collect tool calls
                async for chunk in adapter.stream_chat(self.conversation_history, tools, system_prompt):
                    if chunk["type"] == "text":
                        response_text += chunk["content"]
                        await self.send_ws_message({
                            "type": "text_delta",
                            "content": chunk["content"]
                        })
                    elif chunk["type"] == "tool_call":
                        tool_calls_to_run.append(chunk)
                    elif chunk["type"] == "done":
                        stop_reason = chunk["stop_reason"]
                
                # 2. Append assistant response to history
                assistant_msg = {"role": "assistant"}
                if response_text:
                    assistant_msg["content"] = response_text
                if tool_calls_to_run:
                    # Save tool calls in internal representation format
                    assistant_msg["tool_calls"] = [
                        {"id": tc["id"], "name": tc["name"], "input": tc["input"]}
                        for tc in tool_calls_to_run
                    ]
                
                self.conversation_history.append(assistant_msg)
                
                # If no tool calls, the turn loop is complete
                if not tool_calls_to_run:
                    break
                    
                # 3. Execute tool calls (potentially seeking user confirmation)
                tool_results = []
                for tc in tool_calls_to_run:
                    tc_id = tc["id"]
                    tc_name = tc["name"]
                    tc_args = tc["input"]
                    
                    await self.send_ws_message({
                        "type": "status",
                        "status": "tool_executing",
                        "message": f"Preparing tool '{tc_name}'...",
                        "tool_call": {"id": tc_id, "name": tc_name, "args": tc_args}
                    })
                    
                    try:
                        result = await self._execute_tool_with_guardrails(tc_id, tc_name, tc_args, auto_apply)
                        status = "success"
                    except Exception as e:
                        result = f"Error executing tool '{tc_name}': {str(e)}"
                        status = "error"
                        
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": result
                    })
                    
                    # Send result back to frontend for chat display
                    await self.send_ws_message({
                        "type": "tool_result",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "status": status,
                        "result": result
                    })
                    
                # Append tool outputs to history
                self.conversation_history.extend(tool_results)
                
                # Check if there is another turn needed
                # (only if model chose tool_use stop_reason, which we track implicitly by whether it called tools)
                # If the user rejected tools, the model will see "Action cancelled by the user" in the tool result and continue or stop.
                
            if turn >= self.max_turns:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "\n\n[Warning: Agent reached the maximum limit of 25 turns.]"
                })
                
            await self.send_ws_message({"type": "session_done"})
        except asyncio.CancelledError:
            await self.send_ws_message({"type": "session_done"})
            raise
        finally:
            self.is_running = False

    async def _execute_tool_with_guardrails(self, tc_id: str, name: str, args: dict, auto_apply: bool) -> str:
        """
        Executes a single tool. If the tool is mutative (write/edit) or destructive (terminal commands),
        it prompts the user for confirmation unless auto-apply is true.
        """
        # A. File write/edit safety check
        if name in ("write_file", "edit_file"):
            path = args.get("path")
            
            # Resolve original and proposed content for diff view
            original_content = ""
            proposed_content = ""
            
            try:
                # Resolve path
                abs_path = safe_path(self.workspace_root, path)
                if os.path.exists(abs_path) and os.path.isfile(abs_path):
                    original_content = read_workspace_file(self.workspace_root, path)
            except Exception as e:
                return f"Path verification failed: {str(e)}"
                
            if name == "write_file":
                proposed_content = args.get("content", "")
            elif name == "edit_file":
                target = args.get("target", "").replace("\r\n", "\n")
                replacement = args.get("replacement", "").replace("\r\n", "\n")
                args["target"] = target
                args["replacement"] = replacement
                if target not in original_content:
                    raise ValueError(f"Target block not found in file '{path}'. Edit failed.")
                if original_content.count(target) > 1:
                    raise ValueError(f"Target block occurs multiple times in file '{path}'. Make target block more unique.")
                proposed_content = original_content.replace(target, replacement, 1)

            # Check if user confirmation is required
            if not auto_apply:
                from .diff_utils import generate_hunks, apply_hunks
                hunks = generate_hunks(original_content, proposed_content)
                
                # Ask frontend for approval
                event = asyncio.Event()
                self.pending_confirmations[tc_id] = {"event": event, "approved": False, "hunk_decisions": None}
                
                await self.send_ws_message({
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
                
                # Wait for websocket confirmation response
                await event.wait()
                
                decision = self.pending_confirmations[tc_id]
                del self.pending_confirmations[tc_id]
                
                if not decision["approved"]:
                    self.log_audit(name, args, "rejected", "User rejected file modification.")
                    return "Action cancelled by the user."
                
                # Reconstruct content based on hunk decisions
                hunk_decisions = decision.get("hunk_decisions")
                if hunk_decisions is not None:
                    proposed_content = apply_hunks(original_content, hunks, hunk_decisions)
                # If hunk_decisions is None, it means the user accepted the entire file edits as a whole

            # Perform the actual write
            await async_write_workspace_file(self.workspace_root, path, proposed_content)
            self.log_audit(name, args, "success", f"Modified {path}")
            return f"Successfully updated file '{path}'."

        # B. Destructive/Terminal Command safety check
        elif name == "run_terminal_command":
            cmd = args.get("command", "")
            
            is_approved = False
            risk = "mutative"
            reason = ""
            
            if self.permission_manager:
                is_approved, risk, reason = self.permission_manager.check_permission(cmd)
                
            # If not auto-approved, request permission via popup dialog
            if not is_approved:
                event = asyncio.Event()
                self.pending_confirmations[tc_id] = {
                    "event": event, 
                    "approved": False,
                    "scope": "once",
                    "command": cmd
                }
                
                explanation = f"Runs the terminal command: `{cmd}`"
                
                await self.send_ws_message({
                    "type": "permission_request",
                    "tool_call_id": tc_id,
                    "tool_name": name,
                    "command": cmd,
                    "risk": risk,
                    "reason": reason,
                    "explanation": explanation,
                    "args": args
                })
                
                await event.wait()
                decision = self.pending_confirmations[tc_id]
                del self.pending_confirmations[tc_id]
                
                if not decision["approved"]:
                    self.log_audit(name, args, "rejected", "User rejected command execution.")
                    return "Action cancelled by the user."
                    
                # Extract potentially edited command and scope
                cmd = decision.get("command", cmd)
                scope = decision.get("scope", "once")
                
                # Grant permission if session/project level was chosen
                if scope in ("session", "project") and self.permission_manager:
                    self.permission_manager.grant_permission(cmd, scope)
            
            # Execute command
            self.log_audit(name, args, "pending", f"Running command: {cmd}")
            result = await self._run_shell_command(cmd)
            self.log_audit(name, args, "success", f"Command stdout returned: {len(result)} bytes")
            return result

        # C. Read-only tools (no approval required)
        elif name == "list_directory":
            path = args.get("path", "")
            items = list_workspace_dir(self.workspace_root, path)
            return json.dumps(items, indent=2)
            
        elif name == "read_file":
            path = args.get("path", "")
            return read_workspace_file(self.workspace_root, path)
            
        elif name == "search_codebase":
            query = args.get("query", "")
            results = search_workspace_codebase(self.workspace_root, query)
            return json.dumps(results, indent=2)
            
        elif name == "scan_for_bugs":
            codebase_text = get_codebase_contents(self.workspace_root)
            if not codebase_text:
                return "The workspace directory is empty or contains no readable source code files."
                
            prompt = (
                "Here is the complete codebase of the project:\n\n"
                f"{codebase_text}\n\n"
                "Please perform a deep scan of this codebase. Identify any:\n"
                "1. Syntax errors or compiler/runtime crashes.\n"
                "2. Missing imports, circular dependencies, or undefined variables.\n"
                "3. Logical bugs, race conditions, edge-case failures, or incorrect function parameters.\n"
                "4. Style inconsistencies, code smells, or security concerns.\n\n"
                "Provide a structured, concise summary of the identified bugs and issues. "
                "List each bug with its file path and description of what needs to be fixed. "
                "If no bugs are found, reply with 'No issues identified.'"
            )
            system_prompt = "You are a senior codebase auditor. Analyze the provided code files and list all bugs."
            bugs_summary = await self._run_llm_query(system_prompt, prompt)
            self.log_audit(name, args, "success", f"Scanned codebase; found {len(bugs_summary)} characters of bug summary")
            return bugs_summary
            
        else:
            raise NotImplementedError(f"Tool '{name}' is not supported.")

    async def _run_shell_command(self, command: str) -> str:
        """
        Runs a shell command asynchronously and streams stdout/stderr combined in real time.
        """
        import sys
        import time
        kwargs = {}
        if sys.platform != "win32":
            kwargs["executable"] = "/bin/bash"
            
        start_time = time.time()
        
        # Send initial execution state
        await self.send_ws_message({
            "type": "terminal_status",
            "status": "running",
            "command": command
        })
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.workspace_root,
                **kwargs
            )
            
            output_chunks = []
            while True:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                output_chunks.append(line)
                
                # Stream terminal line to client
                await self.send_ws_message({
                    "type": "terminal_stream",
                    "content": line
                })
                
            exit_code = await process.wait()
            elapsed_time = round(time.time() - start_time, 2)
            
            # Send terminal finished status
            await self.send_ws_message({
                "type": "terminal_status",
                "status": "completed",
                "exit_code": exit_code,
                "elapsed": elapsed_time
            })
            
            output = "".join(output_chunks)
            return output if output.strip() else "[Command executed with no output]"
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 2)
            await self.send_ws_message({
                "type": "terminal_status",
                "status": "failed",
                "exit_code": -1,
                "elapsed": elapsed_time
            })
            return f"Failed to execute command: {str(e)}"

    def resolve_confirmation(self, tool_call_id: str, approved: bool, scope: str = "once", edited_command: str = None, hunk_decisions: dict = None):
        """
        Called when the user clicks Accept or Reject in the frontend.
        """
        if tool_call_id in self.pending_confirmations:
            self.pending_confirmations[tool_call_id]["approved"] = approved
            self.pending_confirmations[tool_call_id]["scope"] = scope
            self.pending_confirmations[tool_call_id]["hunk_decisions"] = hunk_decisions
            if edited_command is not None:
                self.pending_confirmations[tool_call_id]["command"] = edited_command
            self.pending_confirmations[tool_call_id]["event"].set()

    async def _run_llm_query(self, system_prompt: str, user_content: str) -> str:
        """
        Queries the LLM non-disruptively by accumulating stream_chat chunks.
        """
        adapter = self._get_adapter(is_agent=True)
        messages = [{"role": "user", "content": user_content}]
        response_text = ""
        try:
            async for chunk in adapter.stream_chat(messages, [], system_prompt):
                if chunk["type"] == "text":
                    response_text += chunk["content"]
        except Exception as e:
            logger.error(f"Error querying background LLM: {str(e)}")
            response_text = f"Error performing background analysis: {str(e)}"
        return response_text
