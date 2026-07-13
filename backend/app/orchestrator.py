import json
import logging
import asyncio
import uuid
import time
import re
import os
from typing import List, Dict

logger = logging.getLogger("devpilot.orchestrator")

class EventBus:
    def __init__(self):
        self.listeners = {}

    def subscribe(self, event_type: str, callback):
        self.listeners.setdefault(event_type, []).append(callback)

    async def emit(self, event_type: str, data: dict):
        if event_type in self.listeners:
            tasks = [asyncio.create_task(cb(data)) for cb in self.listeners[event_type]]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

class SharedContext:
    def __init__(self):
        self.memory = {}
        self.subtasks = []
        self.active_agent = "Orchestrator"
        self.collaboration_log = []
        self.lock = asyncio.Lock()

    async def log(self, message: str):
        async with self.lock:
            self.collaboration_log.append(message)
            logger.info(message)

class BaseAgent:
    def __init__(self, name: str, orchestrator):
        self.name = name
        self.orchestrator = orchestrator

    async def execute(self, task_description: str, session, task_id: int) -> str:
        raise NotImplementedError

class PlannerAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Planner Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Planner Agent: Formulating execution plan...")
        prompt = (
            f"You are the Planner Agent. Break down the following request into a logical sequence of subtasks "
            f"that can be assigned to specialized agents. Specify any dependencies between tasks.\n\n"
            f"Request: {task_description}\n\n"
            "Format the output as a JSON list of subtasks with IDs and dependencies (parent task IDs), e.g.:\n"
            '[\n'
            '  {"id": 1, "agent": "Requirement Analysis Agent", "description": "Formulate exact file modifications and target list", "dependencies": []},\n'
            '  {"id": 2, "agent": "File System Agent", "description": "Locate files and read their contents", "dependencies": [1]},\n'
            '  {"id": 3, "agent": "Coding Agent", "description": "Implement request modifications", "dependencies": [2]},\n'
            '  {"id": 4, "agent": "Terminal Agent", "description": "Run build/typecheck to verify compilation", "dependencies": [3]},\n'
            '  {"id": 5, "agent": "Git Agent", "description": "Perform diff review and verification log", "dependencies": [4]}\n'
            ']\n\n'
            "Available agents: Planner Agent, Requirement Analysis Agent, Coding Agent, File System Agent, "
            "Terminal Agent, Testing Agent, Debugging Agent, Documentation Agent, Code Review Agent, "
            "Refactoring Agent, Git Agent."
        )
        system_prompt = "You are a master software architect planner. Output ONLY valid JSON."
        response = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
        try:
            clean_res = response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            subtasks = json.loads(clean_res.strip())
            self.orchestrator.context.subtasks = subtasks
            await self.orchestrator.context.log(f"Planner Agent: Formulated plan containing {len(subtasks)} subtasks.")
            return f"Plan formulated with {len(subtasks)} subtasks."
        except Exception:
            self.orchestrator.context.subtasks = [
                {"id": 1, "agent": "Requirement Analysis Agent", "description": "Formulate exact file modifications and target list", "dependencies": []},
                {"id": 2, "agent": "File System Agent", "description": "Locate files and read their contents", "dependencies": [1]},
                {"id": 3, "agent": "Coding Agent", "description": task_description, "dependencies": [2]},
                {"id": 4, "agent": "Terminal Agent", "description": "Run project build check", "dependencies": [3]},
                {"id": 5, "agent": "Git Agent", "description": "Perform status checks", "dependencies": [4]}
            ]
            await self.orchestrator.context.log("Planner Agent: Fallback plan created.")
            return "Fallback plan created."

class RequirementAnalysisAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Requirement Analysis Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Requirement Analysis Agent: Analyzing: {task_description}")
        await self.orchestrator.update_task_progress(task_id, 30, session)
        
        # Get actual codebase file paths to help LLM identify target files
        try:
            from .files import config_manager
            exclude_dirs = set(config_manager.get_exclude_list())
            exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll", ".pyc", ".bak", ".map"}
            
            workspace_files = []
            for root, dirs, files in os.walk(session.workspace_root):
                # Prune excluded directories in-place
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in exclude_extensions:
                        continue
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, session.workspace_root).replace("\\", "/")
                    workspace_files.append(rel_path)
            
            codebase_details = "Actual files in the workspace:\n" + "\n".join(workspace_files)
        except Exception as e:
            codebase_details = "Could not list workspace files."
            logger.error(f"Error listing workspace files: {e}")
            
        # Analyze request to get target files
        prompt = (
            f"Analyze the following task and name the files in the codebase (relative paths) that will need to be read or modified:\n\n"
            f"Task: {task_description}\n\n"
            f"Codebase details:\n"
            f"{codebase_details}\n\n"
            f"Format response as a JSON list of file paths, e.g. ['backend/config.py']."
        )
        system_prompt = "You are a master requirement analysis engineer. Output ONLY valid JSON array of strings."
        response = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
        await self.orchestrator.update_task_progress(task_id, 70, session)
        
        try:
            clean_res = response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            files = json.loads(clean_res.strip())
            if isinstance(files, list):
                self.orchestrator.context.memory["target_files"] = files
                await self.orchestrator.context.log(f"Requirement Analysis Agent: Identified target files: {files}")
            else:
                self.orchestrator.context.memory["target_files"] = []
        except Exception:
            self.orchestrator.context.memory["target_files"] = []
            
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class FileSystemAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("File System Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"File System Agent: Reading codebase files...")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        target_files = self.orchestrator.context.memory.get("target_files", [])
        
        from .async_files import async_read_workspace_file
        file_contents = {}
        
        progress_step = 80 / max(len(target_files), 1)
        current_progress = 20
        
        for index, path in enumerate(target_files):
            try:
                # Read using async utility function
                content = await async_read_workspace_file(session.workspace_root, path)
                file_contents[path] = content
                await self.orchestrator.context.log(f"File System Agent: Read {path} successfully.")
            except Exception as e:
                await self.orchestrator.context.log(f"File System Agent: Warning: Could not read {path}: {str(e)}")
            current_progress += progress_step
            await self.orchestrator.update_task_progress(task_id, int(current_progress), session)
            
        self.orchestrator.context.memory["file_contents"] = file_contents
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class CodingAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Coding Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Coding Agent: Starting code generation...")
        await self.orchestrator.update_task_progress(task_id, 10, session)
        
        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = self.orchestrator.context.memory.get("file_contents", {})
        
        if not target_files:
            await self.orchestrator.context.log("Coding Agent: No target files identified. Asking Planner to refine list.")
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No files to modify"
            
        total_files = len(target_files)
        progress_per_file = 90 / total_files
        
        for idx, path in enumerate(target_files):
            original = file_contents.get(path, "")
            
            prompt = (
                f"You are a master coder. Modify the following file to implement this feature:\n\n"
                f"Task: {task_description}\n"
                f"File: {path}\n"
                f"Original Content:\n{original}\n\n"
                f"Provide the complete, updated content of the file. Output ONLY the raw updated content. "
                f"Do NOT wrap it in markdown code blocks or add any descriptions. Just code."
            )
            system_prompt = "You are a master software engineer. Output ONLY the raw, complete code. No formatting."
            
            # Run query
            new_code = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
            
            # Clean up markdown block wrapping if present
            clean_code = new_code.strip()
            if clean_code.startswith("```"):
                lines = clean_code.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_code = "\n".join(lines)
                
            tc_id = f"write_{task_id}_{uuid.uuid4().hex[:6]}"
            await session.send_ws_message({
                "type": "status",
                "status": "tool_executing",
                "message": f"Writing {path}...",
                "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": clean_code}}
            })
            
            # Execute modification (auto_apply matches workspace state toggle)
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": clean_code}, auto_apply=True)
            
            await session.send_ws_message({
                "type": "tool_result",
                "tool_call_id": tc_id,
                "name": "write_file",
                "status": "success",
                "result": result
            })
            
            await self.orchestrator.context.log(f"Coding Agent: Wrote modifications to {path}.")
            await self.orchestrator.update_task_progress(task_id, int(10 + (idx + 1) * progress_per_file), session)
            
        await self.orchestrator.event_bus.emit("FILE_UPDATED", {"task": task_description})
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class TerminalAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Terminal Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Terminal Agent: Coordinating system task...")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        # Analyze if we need to run compile or check commands
        prompt = (
            f"Name a logical terminal command (e.g. 'npm run build', 'npm run test', 'pytest') "
            f"to verify this task:\n\n"
            f"Task: {task_description}\n\n"
            f"Respond with ONLY the command string. If no command is needed, output 'NONE'."
        )
        system_prompt = "You are a master system terminal executor. Output ONLY the raw command string."
        cmd = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
        
        cmd = cmd.strip().strip("`").strip()
        if cmd and cmd.upper() != "NONE":
            await self.orchestrator.context.log(f"Terminal Agent: Running command: {cmd}")
            tc_id = f"term_{task_id}_{uuid.uuid4().hex[:6]}"
            
            await session.send_ws_message({
                "type": "status",
                "status": "tool_executing",
                "message": f"Executing: {cmd}...",
                "tool_call": {"id": tc_id, "name": "run_terminal_command", "args": {"command": cmd}}
            })
            
            # Execute terminal (requests permission dialog on mutative/destructive commands!)
            result = await session._execute_tool_with_guardrails(tc_id, "run_terminal_command", {"command": cmd}, auto_apply=False)
            
            await session.send_ws_message({
                "type": "tool_result",
                "tool_call_id": tc_id,
                "name": "run_terminal_command",
                "status": "success",
                "result": result
            })
            
            await self.orchestrator.context.log(f"Terminal Agent: Executed command. Outcome: {result[:120]}...")
            
        await self.orchestrator.event_bus.emit("TERMINAL_COMPLETED", {"task": task_description})
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class TestingAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Testing Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Testing Agent: Verifying results for: {task_description}")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        # Determine test command based on project type
        if os.path.exists(os.path.join(session.workspace_root, "package.json")):
            cmd = "npm test"
        else:
            cmd = "pytest"
            
        await self.orchestrator.context.log(f"Testing Agent: Running test command: {cmd}")
        tc_id = f"test_{task_id}_{uuid.uuid4().hex[:6]}"
        
        await session.send_ws_message({
            "type": "status",
            "status": "tool_executing",
            "message": f"Executing Tests: {cmd}...",
            "tool_call": {"id": tc_id, "name": "run_terminal_command", "args": {"command": cmd}}
        })
        
        result = await session._execute_tool_with_guardrails(tc_id, "run_terminal_command", {"command": cmd}, auto_apply=True)
        
        await session.send_ws_message({
            "type": "tool_result",
            "tool_call_id": tc_id,
            "name": "run_terminal_command",
            "status": "success",
            "result": result
        })
        
        await self.orchestrator.context.log(f"Testing Agent: Tests executed. Outcome:\n{result[:300]}")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class DebuggingAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Debugging Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Debugging Agent: Scanning workspace for errors and warnings...")
        await self.orchestrator.update_task_progress(task_id, 30, session)
        
        # Look for traceback or failure indicators in collaboration log
        history_summary = "\n".join(self.orchestrator.context.collaboration_log)
        
        prompt = (
            f"You are the Debugging Agent. Here is the collaboration history and log of issues/commands:\n\n"
            f"Log:\n{history_summary}\n\n"
            f"Please identify any errors, tracebacks, or compilation failures. Propose concrete debugging steps or "
            f"code fixes to address these. If no bugs are found in the logs, state 'No issues identified'."
        )
        system_prompt = "You are a senior debugging engineer. Analyze the output and suggest fixes."
        debug_output = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
        
        await self.orchestrator.context.log(f"Debugging Agent: Debugging analysis:\n{debug_output[:300]}")
        self.orchestrator.context.memory["debugging_notes"] = debug_output
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class DocumentationAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Documentation Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Documentation Agent: Creating notes...")
        await self.orchestrator.update_task_progress(task_id, 30, session)
        
        prompt = (
            f"You are the Documentation Agent. Generate a markdown documentation summarizing the implementation of this task:\n\n"
            f"Task: {task_description}\n\n"
            f"Format the output strictly as markdown. Do not include extra markdown block wrapping."
        )
        system_prompt = "You are a technical writer. Write clean, readable technical documentation."
        doc_content = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
        
        path = "DOCS.md"
        tc_id = f"doc_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status",
            "status": "tool_executing",
            "message": f"Writing documentation to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": doc_content}}
        })
        
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": doc_content}, auto_apply=True)
        await session.send_ws_message({
            "type": "tool_result",
            "tool_call_id": tc_id,
            "name": "write_file",
            "status": "success",
            "result": result
        })
        
        await self.orchestrator.context.log(f"Documentation Agent: Documentation written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class CodeReviewAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Code Review Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Code Review Agent: Auditing codebase modifications...")
        await self.orchestrator.update_task_progress(task_id, 30, session)
        
        from .async_files import async_get_codebase_contents
        codebase_text = await async_get_codebase_contents(session.workspace_root)
        
        prompt = (
            f"Perform a thorough code review of the workspace codebase based on the task description:\n\n"
            f"Task: {task_description}\n\n"
            f"Codebase:\n{codebase_text}\n\n"
            f"Analyze style, potential bugs, efficiency, and safety. Report any concerns."
        )
        system_prompt = "You are a senior code reviewer. Provide constructive criticism and issues found."
        review = await session._run_llm_query(system_prompt, prompt, agent_name=self.name)
        
        await self.orchestrator.context.log(f"Code Review Agent: Review completed. Summary:\n{review[:250]}...")
        self.orchestrator.context.memory["code_review"] = review
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class RefactoringAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Refactoring Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Refactoring Agent: Restructuring files...")
        await self.orchestrator.update_task_progress(task_id, 50, session)
        await self.orchestrator.context.log("Refactoring Agent: Restructuring checks complete.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class GitAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Git Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Git Agent: Auditing diff status...")
        await self.orchestrator.update_task_progress(task_id, 40, session)
        
        # Git status check
        tc_id = f"git_status_{uuid.uuid4().hex[:6]}"
        result = await session._execute_tool_with_guardrails(tc_id, "run_terminal_command", {"command": "git status"}, auto_apply=True)
        
        await self.orchestrator.context.log(f"Git Agent: Checked git status:\n{result[:150]}")
        await self.orchestrator.event_bus.emit("GIT_COMMIT", {"task": task_description})
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class TaskScheduler:
    def __init__(self, orchestrator, session):
        self.orchestrator = orchestrator
        self.session = session
        self.tasks = []

    async def run(self, subtasks_list: List[Dict]):
        self.tasks = []
        for t in subtasks_list:
            self.tasks.append({
                "id": t.get("id"),
                "agent": t.get("agent", "Coding Agent"),
                "description": t.get("description", ""),
                "dependencies": t.get("dependencies", []),
                "progress": 0,
                "status": "waiting"  # waiting, running, completed, failed
            })

        active_futures = {}
        
        while True:
            # Check if all tasks finished
            all_done = all(t["status"] in ("completed", "failed") for t in self.tasks)
            if all_done:
                break
                
            # Filter tasks whose dependencies are met
            ready_tasks = []
            for t in self.tasks:
                if t["status"] == "waiting":
                    deps_met = True
                    for dep_id in t["dependencies"]:
                        parent = next((pt for pt in self.tasks if pt["id"] == dep_id), None)
                        if not parent or parent["status"] != "completed":
                            deps_met = False
                            break
                    if deps_met:
                        ready_tasks.append(t)

            # Spawn ready tasks concurrently
            for rt in ready_tasks:
                rt["status"] = "running"
                rt["progress"] = 0
                task_id = rt["id"]
                
                async def run_wrapper(task_entry=rt):
                    agent_name = task_entry["agent"]
                    if agent_name not in self.orchestrator.agents:
                        agent_name = "Coding Agent"
                    agent = self.orchestrator.agents[agent_name]
                    try:
                        await agent.execute(task_entry["description"], self.session, task_entry["id"])
                        task_entry["status"] = "completed"
                        task_entry["progress"] = 100
                    except Exception as e:
                        logger.error(f"Task {task_entry['id']} failed: {str(e)}")
                        task_entry["status"] = "failed"
                    finally:
                        await self.send_state_update()
                        
                fut = asyncio.create_task(run_wrapper())
                active_futures[task_id] = fut
                
            if ready_tasks:
                await self.send_state_update()

            if active_futures:
                done, pending = await asyncio.wait(
                    active_futures.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )
                # Remove completed tasks from active mapping
                for tid, fut in list(active_futures.items()):
                    if fut in done:
                        active_futures.pop(tid)
            else:
                break

    async def send_state_update(self):
        await self.session.send_ws_message({
            "type": "agent_state",
            "active_agent": self.orchestrator.context.active_agent,
            "active_task": "Running concurrent workers...",
            "subtasks": self.tasks,
            "collaboration_log": self.orchestrator.context.collaboration_log
        })

def extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
        
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except Exception:
            pass
            
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
            
    raise ValueError(f"Could not parse response as JSON: {text}")

class AgentOrchestrator:
    def __init__(self):
        self.context = SharedContext()
        self.event_bus = EventBus()
        self.agents = {
            "Planner Agent": PlannerAgent(self),
            "Requirement Analysis Agent": RequirementAnalysisAgent(self),
            "Coding Agent": CodingAgent(self),
            "File System Agent": FileSystemAgent(self),
            "Terminal Agent": TerminalAgent(self),
            "Testing Agent": TestingAgent(self),
            "Debugging Agent": DebuggingAgent(self),
            "Documentation Agent": DocumentationAgent(self),
            "Code Review Agent": CodeReviewAgent(self),
            "Refactoring Agent": RefactoringAgent(self),
            "Git Agent": GitAgent(self)
        }
        # Verify no duplicate agent mappings are registered
        agent_names = list(self.agents.keys())
        if len(agent_names) != len(set(agent_names)):
            logger.warning("Duplicate agent mappings detected in orchestrator registry!")

    async def update_task_progress(self, task_id: int, progress: int, session):
        if hasattr(session, "scheduler") and session.scheduler:
            for t in session.scheduler.tasks:
                if t["id"] == task_id:
                    t["progress"] = progress
                    break
            await session.scheduler.send_state_update()

    async def run_task(self, task_description: str, session) -> str:
        """
        Coordinates the dynamic agent routing flow based on the LLM's step-by-step decisions.
        """
        await self.context.log("Orchestrator: Initializing dynamic agent router session...")
        
        # Initialize an empty subtasks array for the UI view
        self.context.subtasks = []
        task_id_counter = 1
        
        # Loop limit to prevent infinite runaways
        max_steps = 10
        step = 0
        
        while step < max_steps:
            step += 1
            
            # Format list of available agents and descriptions
            agents_description = """
Available Agents:
- Requirement Analysis Agent: Identifies which files in the codebase need to be read or modified. Call this first if you don't know which files are target of the user's request.
- File System Agent: Reads the contents of target files. Call this to retrieve contents of code files before making changes.
- Coding Agent: Performs file modifications. Call this only after you know the file contents and target changes.
- Terminal Agent: Runs build commands, compilation check commands, or syntax tests. Call this to verify modifications.
- Git Agent: Reviews files, checks git diff status, or inspects logs. Call this to summarize final changes.
"""
            # Retrieve what has been completed so far
            history_summary = "\n".join(self.context.collaboration_log)
            memory_summary = json.dumps(self.context.memory)
            
            prompt = (
                f"You are the Orchestrator Agent. Your task is to resolve the user request by dynamically calling specialized agents one-by-one.\n\n"
                f"User Request: {task_description}\n\n"
                f"{agents_description}\n"
                f"Current Collaboration Log/Steps taken so far:\n{history_summary}\n\n"
                f"Current Shared Memory Content:\n{memory_summary}\n\n"
                f"Based on the work done so far, identify which agent should be called next and describe exactly what it needs to do. "
                f"If the request is fully completed and verified, select agent 'Orchestrator' to finish the session.\n\n"
                f"Format the output strictly as a JSON object, e.g.:\n"
                f'{{"agent": "File System Agent", "reasoning": "We need to read the target file to understand its current code.", "description": "Read the contents of the target files identified by the analysis."}}\n'
                f"or when finished:\n"
                f'{{"agent": "Orchestrator", "reasoning": "Coding and terminal verification checks are all complete.", "description": "Task complete"}}\n'
            )
            
            system_prompt = "You are a master software architect routing coordinator. Output ONLY valid JSON."
            
            self.context.active_agent = "Orchestrator"
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": "Orchestrator",
                "active_task": "Deciding next agent...",
                "subtasks": self.context.subtasks,
                "collaboration_log": self.context.collaboration_log
            })
            
            response = await session._run_llm_query(system_prompt, prompt, agent_name="Orchestrator Agent")
            
            selected_agent_name = "Orchestrator"
            agent_description = "Task complete"
            
            try:
                clean_res = response.strip()
                if clean_res.startswith("```json"):
                    clean_res = clean_res[7:]
                if clean_res.endswith("```"):
                    clean_res = clean_res[:-3]
                decision = json.loads(clean_res.strip())
                selected_agent_name = decision.get("agent", "Orchestrator")
                agent_description = decision.get("description", "Execute step")
                reasoning = decision.get("reasoning", "")
                
                await self.context.log(f"Orchestrator: Selected '{selected_agent_name}' to run. Reasoning: {reasoning}")
            except Exception as e:
                # Fallback path if JSON parsing fails
                await self.context.log(f"Orchestrator: Parsing error, defaulting to complete: {str(e)}")
                break
                
            if selected_agent_name == "Orchestrator" or selected_agent_name not in self.agents:
                break
                
            # Add subtask entry dynamically to the list for UI visualization
            subtask_id = task_id_counter
            task_id_counter += 1
            task_entry = {
                "id": subtask_id,
                "agent": selected_agent_name,
                "description": agent_description,
                "status": "running",
                "progress": 10
            }
            self.context.subtasks.append(task_entry)
            
            self.context.active_agent = selected_agent_name
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": selected_agent_name,
                "active_task": agent_description,
                "subtasks": self.context.subtasks,
                "collaboration_log": self.context.collaboration_log
            })
            
            # Execute agent
            agent = self.agents[selected_agent_name]
            try:
                await agent.execute(agent_description, session, subtask_id)
                task_entry["status"] = "completed"
                task_entry["progress"] = 100
            except Exception as e:
                task_entry["status"] = "failed"
                await self.context.log(f"Orchestrator: Error executing agent {selected_agent_name}: {str(e)}")
                
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": selected_agent_name,
                "active_task": "Step finished",
                "subtasks": self.context.subtasks,
                "collaboration_log": self.context.collaboration_log
            })
            
        self.context.active_agent = "Orchestrator"
        await self.context.log("Orchestrator: Dynamic routing session finished.")
        
        await session.send_ws_message({
            "type": "agent_state",
            "active_agent": "Orchestrator",
            "active_task": "All tasks completed",
            "subtasks": self.context.subtasks,
            "collaboration_log": self.context.collaboration_log
        })
        
        # Generate and stream final response summary
        final_history_summary = "\n".join(self.context.collaboration_log)
        summary_prompt = (
            f"You are the Orchestrator Agent. The user's query/task description was: '{task_description}'.\n"
            f"Here is the log of what the specialized agents accomplished:\n"
            f"{final_history_summary}\n\n"
            f"Please write a friendly, concise summary response to the user explaining what was done and the final outcome. "
            f"If it was just a simple conversational message (like 'hi' or 'hello'), respond to it directly and politely, without listing logs. "
            f"Keep your response concise."
        )
        system_prompt = "You are the head Orchestrator assistant. Summarize the task outcome clearly."
        try:
            response_text = await session._run_llm_query(system_prompt, summary_prompt, agent_name="Orchestrator Agent")
            # Append response to session conversation history so context is preserved
            session.conversation_history.append({"role": "assistant", "content": response_text})
            await session.send_ws_message({
                "type": "text_delta",
                "content": response_text
            })
        except Exception as e:
            logger.error(f"Failed to generate final orchestrator summary: {str(e)}")
            fallback_text = "Dynamic routing session completed successfully."
            session.conversation_history.append({"role": "assistant", "content": fallback_text})
            await session.send_ws_message({
                "type": "text_delta",
                "content": fallback_text
            })
            
        return "Dynamic routing session completed."
