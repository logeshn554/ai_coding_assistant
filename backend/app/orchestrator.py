import json
import logging
import asyncio
import uuid
import time
import re
import os
from typing import List, Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

class DevPilotChatModel(BaseChatModel):
    session: Any
    agent_name: Optional[str] = None
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("Use async generate")
        
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        dp_messages = []
        system_prompt = None
        for m in messages:
            if m.type == "system":
                system_prompt = m.content
            elif m.type == "human":
                dp_messages.append({"role": "user", "content": m.content})
            elif m.type == "ai":
                dp_messages.append({"role": "assistant", "content": m.content})
                
        if not dp_messages:
            dp_messages.append({"role": "user", "content": ""})
            
        from .adapters.router import ModelRouter
        router = ModelRouter()
        
        response_text = await router.completion(
            self.session.profile, 
            dp_messages, 
            system_prompt, 
            is_agent=True, 
            task_type=self.agent_name
        )
        
        ai_message = AIMessage(content=response_text)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    @property
    def _llm_type(self) -> str:
        return "devpilot-chat"

# ── LangChain Prompt Templates ──

planner_prompt_template = PromptTemplate.from_template(
    "You are the Planner Agent. Break down the following request into a logical sequence of subtasks "
    "that can be assigned to specialized agents. Specify any dependencies between tasks.\n\n"
    "Request: {task_description}\n\n"
    "Format the output as a JSON list of subtasks with IDs and dependencies (parent task IDs), e.g.:\n"
    "[\n"
    '  {{"id": 1, "agent": "Requirement Analysis Agent", "description": "Formulate exact file modifications and target list", "dependencies": []}},\n'
    '  {{"id": 2, "agent": "File System Agent", "description": "Locate files and read their contents", "dependencies": [1]}},\n'
    '  {{"id": 3, "agent": "Coding Agent", "description": "Implement request modifications", "dependencies": [2]}},\n'
    '  {{"id": 4, "agent": "Terminal Agent", "description": "Run build/typecheck to verify compilation", "dependencies": [3]}},\n'
    '  {{"id": 5, "agent": "Git Agent", "description": "Perform diff review and verification log", "dependencies": [4]}}\n'
    "]\n\n"
    "Available agents: Planner Agent, Requirement Analysis Agent, Coding Agent, File System Agent, "
    "Terminal Agent, Testing Agent, Debugging Agent, Documentation Agent, Code Review Agent, "
    "Refactoring Agent, Git Agent."
)

requirement_prompt_template = PromptTemplate.from_template(
    "Analyze the following task and name the files in the codebase (relative paths) that will need to be read or modified:\n\n"
    "Task: {task_description}\n\n"
    "Codebase details:\n"
    "{codebase_details}\n\n"
    "Format response as a JSON list of file paths, e.g. ['backend/config.py']."
)

coding_prompt_template = PromptTemplate.from_template(
    "You are a master coder. Modify the following file to implement this feature:\n\n"
    "Task: {task_description}\n"
    "File: {path}\n"
    "Original Content:\n{original}\n\n"
    "Provide the complete, updated content of the file. Output ONLY the raw updated content. "
    "Do NOT wrap it in markdown code blocks or add any descriptions. Just code."
)

terminal_prompt_template = PromptTemplate.from_template(
    "Name a logical terminal command (e.g. 'npm run build', 'npm run test', 'pytest') "
    "to verify this task:\n\n"
    "Task: {task_description}\n\n"
    "Respond with ONLY the command string. If no command is needed, output 'NONE'."
)

debugging_prompt_template = PromptTemplate.from_template(
    "You are the Debugging Agent. Here is the collaboration history and log of issues/commands:\n\n"
    "Log:\n{history_summary}\n\n"
    "Please identify any errors, tracebacks, or compilation failures. Propose concrete debugging steps or "
    "code fixes to address these. If no bugs are found in the logs, state 'No issues identified'."
)

documentation_prompt_template = PromptTemplate.from_template(
    "You are the Documentation Agent. Generate a markdown documentation summarizing the implementation of this task:\n\n"
    "Task: {task_description}\n\n"
    "Format the output strictly as markdown. Do not include extra markdown block wrapping."
)

review_prompt_template = PromptTemplate.from_template(
    "Perform a thorough code review of the workspace codebase based on the task description:\n\n"
    "Task: {task_description}\n\n"
    "Codebase:\n{codebase_text}\n\n"
    "Analyze style, potential bugs, efficiency, and safety. Report any concerns."
)

orchestrator_prompt_template = PromptTemplate.from_template(
    "You are the Orchestrator Agent. Your task is to resolve the user request by dynamically calling specialized agents.\n\n"
    "User Request: {task_description}\n\n"
    "{agents_description}\n"
    "Current Collaboration Log/Steps taken so far:\n{history_summary}\n\n"
    "Current Shared Memory Content:\n{memory_summary}\n\n"
    "Based on the work done so far, identify which agent(s) should be called next and describe exactly what they need to do. "
    "To speed up execution, you should run independent agents in parallel (e.g. running 'Terminal Agent', 'Testing Agent', 'Code Review Agent', 'Documentation Agent', and 'Git Agent' in parallel after files are modified).\n\n"
    "Format the output strictly as a JSON object with keys:\n"
    "- 'agents': a list of agent names to run in parallel (even if only one agent is run, e.g. ['Requirement Analysis Agent'])\n"
    "- 'reasoning': explanation of the decision\n"
    "- 'descriptions': a list of task descriptions, one for each agent in the 'agents' list, matching their positions.\n"
    "Example for parallel run:\n"
    '{{"agents": ["Terminal Agent", "Documentation Agent"], "reasoning": "We can verify the changes and write documentation in parallel.", "descriptions": ["Run build to verify", "Write DOCS.md summarizing changes"]}}\n'
    "Example when finished:\n"
    '{{"agents": ["Orchestrator"], "reasoning": "All steps complete.", "descriptions": ["Task complete"]}}\n'
)

summary_prompt_template = PromptTemplate.from_template(
    "You are the Orchestrator Agent. The user's query/task description was: '{task_description}'.\n"
    "Here is the log of what the specialized agents accomplished:\n"
    "{final_history_summary}\n\n"
    "Please write a friendly, concise summary response to the user explaining what was done and the final outcome. "
    "If it was just a simple conversational message (like 'hi' or 'hello'), respond to it directly and politely, without listing logs. "
    "Keep your response concise."
)

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
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a master software architect planner. Output ONLY valid JSON."),
            ("human", "{prompt_content}")
        ])
        prompt_content = planner_prompt_template.format(task_description=task_description)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        response = response_msg.content
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
        
        try:
            from .files import config_manager
            exclude_dirs = set(config_manager.get_exclude_list())
            exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll", ".pyc", ".bak", ".map"}
            
            workspace_files = []
            for root, dirs, files in os.walk(session.workspace_root):
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
            
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a master requirement analysis engineer. Output ONLY valid JSON array of strings."),
            ("human", "{prompt_content}")
        ])
        prompt_content = requirement_prompt_template.format(task_description=task_description, codebase_details=codebase_details)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        response = response_msg.content
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
        await self.orchestrator.context.log(f"Coding Agent: Starting parallel code generation...")
        await self.orchestrator.update_task_progress(task_id, 10, session)
        
        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = self.orchestrator.context.memory.get("file_contents", {})
        
        if not target_files:
            await self.orchestrator.context.log("Coding Agent: No target files identified. Asking Planner to refine list.")
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No files to modify"
            
        async def process_file(path: str):
            original = file_contents.get(path, "")
            
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a master software engineer. Output ONLY the raw, complete code. No formatting."),
                ("human", "{prompt_content}")
            ])
            prompt_content = coding_prompt_template.format(task_description=task_description, path=path, original=original)
            
            llm = DevPilotChatModel(session=session, agent_name=self.name)
            chain = chat_prompt | llm
            
            new_code_msg = await chain.ainvoke({"prompt_content": prompt_content})
            new_code = new_code_msg.content
            
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
            
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": clean_code}, auto_apply=False)
            
            await session.send_ws_message({
                "type": "tool_result",
                "tool_call_id": tc_id,
                "name": "write_file",
                "status": "success",
                "result": result
            })
            
            await self.orchestrator.context.log(f"Coding Agent: Wrote modifications to {path}.")

        # Concurrently process all file modifications
        tasks = [process_file(path) for path in target_files]
        await asyncio.gather(*tasks)
            
        await self.orchestrator.event_bus.emit("FILE_UPDATED", {"task": task_description})
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class TerminalAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Terminal Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Terminal Agent: Coordinating system task...")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a master system terminal executor. Output ONLY the raw command string."),
            ("human", "{prompt_content}")
        ])
        prompt_content = terminal_prompt_template.format(task_description=task_description)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        cmd_msg = await chain.ainvoke({"prompt_content": prompt_content})
        cmd = cmd_msg.content
        
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
        
        history_summary = "\n".join(self.orchestrator.context.collaboration_log)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior debugging engineer. Analyze the output and suggest fixes."),
            ("human", "{prompt_content}")
        ])
        prompt_content = debugging_prompt_template.format(history_summary=history_summary)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        debug_output_msg = await chain.ainvoke({"prompt_content": prompt_content})
        debug_output = debug_output_msg.content
        
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
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a technical writer. Write clean, readable technical documentation."),
            ("human", "{prompt_content}")
        ])
        prompt_content = documentation_prompt_template.format(task_description=task_description)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        doc_content_msg = await chain.ainvoke({"prompt_content": prompt_content})
        doc_content = doc_content_msg.content
        
        path = "DOCS.md"
        tc_id = f"doc_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status",
            "status": "tool_executing",
            "message": f"Writing documentation to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": doc_content}}
        })
        
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": doc_content}, auto_apply=False)
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
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior code reviewer. Provide constructive criticism and issues found."),
            ("human", "{prompt_content}")
        ])
        prompt_content = review_prompt_template.format(task_description=task_description, codebase_text=codebase_text)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        review_msg = await chain.ainvoke({"prompt_content": prompt_content})
        review = review_msg.content
        
        await self.orchestrator.context.log(f"Code Review Agent: Review completed. Summary:\n{review[:250]}...")
        self.orchestrator.context.memory["code_review"] = review
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class GitAgent(BaseAgent):
    def __init__(self, orchestrator):
        super().__init__("Git Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Git Agent: Auditing diff status...")
        await self.orchestrator.update_task_progress(task_id, 40, session)
        
        tc_id = f"git_status_{uuid.uuid4().hex[:6]}"
        result = await session._execute_tool_with_guardrails(tc_id, "run_terminal_command", {"command": "git status"}, auto_apply=True)
        
        await self.orchestrator.context.log(f"Git Agent: Checked git status:\n{result[:150]}")
        await self.orchestrator.event_bus.emit("GIT_COMMIT", {"task": task_description})
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

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

from typing import Annotated

def reduce_log(left: list, right: list) -> list:
    combined = []
    seen = set()
    for item in (left or []) + (right or []):
        if item not in seen:
            combined.append(item)
            seen.add(item)
    return combined

def reduce_subtasks(left: list, right: list) -> list:
    merged = {t["id"]: t for t in (left or [])}
    for t in (right or []):
        merged[t["id"]] = t
    return list(merged.values())

class AgentState(TypedDict):
    task_description: str
    collaboration_log: Annotated[List[str], reduce_log]
    memory: Dict[str, Any]
    subtasks: Annotated[List[Dict[str, Any]], reduce_subtasks]
    active_agent: str
    active_task: str
    next_agents: List[str]
    agent_tasks: Dict[str, str]
    session: Any
    task_id_counter: int
    step_count: int
    orchestrator: Any

async def orchestrator_node(state: AgentState) -> AgentState:
    state["step_count"] += 1
    if state["step_count"] >= 10:
        state["next_agents"] = ["Orchestrator"]
        return state

    agents_description = """
Available Agents:
- Requirement Analysis Agent: Identifies which files in the codebase need to be read or modified. Call this first if you don't know which files are target of the user's request.
- File System Agent: Reads the contents of target files. Call this to retrieve contents of code files before making changes.
- Coding Agent: Performs file modifications. Call this only after you know the file contents and target changes.
- Terminal Agent: Runs build commands, compilation check commands, or syntax tests. Call this to verify modifications.
- Git Agent: Reviews files, checks git diff status, or inspects logs. Call this to summarize final changes.
"""
    history_summary = "\n".join(state["collaboration_log"])
    memory_summary = json.dumps(state["memory"])
    
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a master software architect routing coordinator. Output ONLY valid JSON."),
        ("human", "{prompt_content}")
    ])
    prompt_content = orchestrator_prompt_template.format(
        task_description=state["task_description"],
        agents_description=agents_description,
        history_summary=history_summary,
        memory_summary=memory_summary
    )
    
    state["active_agent"] = "Orchestrator"
    await state["session"].send_ws_message({
        "type": "agent_state",
        "active_agent": "Orchestrator",
        "active_task": "Deciding next agent...",
        "subtasks": state["subtasks"],
        "collaboration_log": state["collaboration_log"]
    })
    
    llm = DevPilotChatModel(session=state["session"], agent_name="Orchestrator Agent")
    chain = chat_prompt | llm
    
    response_msg = await chain.ainvoke({"prompt_content": prompt_content})
    response = response_msg.content
    
    selected_agents = ["Orchestrator"]
    agent_tasks = {}
    
    try:
        clean_res = response.strip()
        if clean_res.startswith("```json"):
            clean_res = clean_res[7:]
        if clean_res.endswith("```"):
            clean_res = clean_res[:-3]
        decision = json.loads(clean_res.strip())
        
        # Parse agents list
        selected_agents = decision.get("agents", [])
        if isinstance(selected_agents, str):
            selected_agents = [selected_agents]
        if not selected_agents and "agent" in decision:
            selected_agents = [decision["agent"]]
        if not selected_agents:
            selected_agents = ["Orchestrator"]
            
        # Parse task descriptions
        descriptions = decision.get("descriptions", [])
        if isinstance(descriptions, str):
            descriptions = [descriptions]
        if not descriptions and "description" in decision:
            descriptions = [decision["description"]]
            
        # Build tasks mapping
        for i, name in enumerate(selected_agents):
            desc = descriptions[i] if i < len(descriptions) else "Execute task"
            agent_tasks[name] = desc
            
        reasoning = decision.get("reasoning", "")
        log_msg = f"Orchestrator: Selected agent(s) {selected_agents} to run in parallel. Reasoning: {reasoning}"
        state["collaboration_log"].append(log_msg)
        state["orchestrator"].context.collaboration_log = state["collaboration_log"]
        logger.info(log_msg)
    except Exception as e:
        log_msg = f"Orchestrator: Parsing error, defaulting to complete: {str(e)}"
        state["collaboration_log"].append(log_msg)
        state["orchestrator"].context.collaboration_log = state["collaboration_log"]
        logger.info(log_msg)
        selected_agents = ["Orchestrator"]
        agent_tasks = {"Orchestrator": "Task complete"}
        
    state["next_agents"] = selected_agents
    state["agent_tasks"] = agent_tasks
    
    return state

def make_agent_node(agent_name: str):
    async def node(state: AgentState) -> AgentState:
        state["active_agent"] = agent_name
        agent_description = state.get("agent_tasks", {}).get(agent_name, "Execute task")
        
        subtask_id = state["task_id_counter"]
        task_entry = {
            "id": subtask_id,
            "agent": agent_name,
            "description": agent_description,
            "status": "running",
            "progress": 10
        }
        state["subtasks"].append(task_entry)
        state["task_id_counter"] += 1
        
        await state["session"].send_ws_message({
            "type": "agent_state",
            "active_agent": agent_name,
            "active_task": agent_description,
            "subtasks": state["subtasks"],
            "collaboration_log": state["collaboration_log"]
        })
        
        agent = state["orchestrator"].agents[agent_name]
        try:
            await agent.execute(agent_description, state["session"], subtask_id)
            task_entry["status"] = "completed"
            task_entry["progress"] = 100
        except Exception as e:
            task_entry["status"] = "failed"
            await state["orchestrator"].context.log(f"Orchestrator: Error executing agent {agent_name}: {str(e)}")
            
        await state["session"].send_ws_message({
            "type": "agent_state",
            "active_agent": agent_name,
            "active_task": "Step finished",
            "subtasks": state["subtasks"],
            "collaboration_log": state["collaboration_log"]
        })
        
        return state
    return node

def route_next(state: AgentState) -> List[str]:
    next_agents = state.get("next_agents", [])
    valid_agents = []
    for name in next_agents:
        if name in state["orchestrator"].agents:
            valid_agents.append(name)
    if not valid_agents:
        return ["end"]
    return valid_agents

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
            "Git Agent": GitAgent(self)
        }
        agent_names = list(self.agents.keys())
        if len(agent_names) != len(set(agent_names)):
            logger.warning("Duplicate agent mappings detected in orchestrator registry!")

    async def update_task_progress(self, task_id: int, progress: int, session):
        pass

    async def run_task(self, task_description: str, session) -> str:
        await self.context.log("Orchestrator: Initializing dynamic agent router session...")
        self.context.subtasks = []
        
        # Initialize graph state
        initial_state: AgentState = {
            "task_description": task_description,
            "collaboration_log": self.context.collaboration_log,
            "memory": self.context.memory,
            "subtasks": self.context.subtasks,
            "active_agent": "Orchestrator",
            "active_task": "Deciding next agent...",
            "next_agents": ["Orchestrator"],
            "agent_tasks": {},
            "session": session,
            "task_id_counter": 1,
            "step_count": 0,
            "orchestrator": self
        }
        
        # Compile graph
        workflow = StateGraph(AgentState)
        workflow.add_node("Orchestrator", orchestrator_node)
        for name in self.agents:
            workflow.add_node(name, make_agent_node(name))
            
        workflow.add_edge(START, "Orchestrator")
        workflow.add_conditional_edges(
            "Orchestrator",
            route_next,
            {
                "end": END,
                **{name: name for name in self.agents}
            }
        )
        for name in self.agents:
            workflow.add_edge(name, "Orchestrator")
            
        compiled_graph = workflow.compile()
        
        # Run graph
        final_state = await compiled_graph.ainvoke(initial_state)
        
        # Update our context from final state
        self.context.collaboration_log = final_state["collaboration_log"]
        self.context.memory = final_state["memory"]
        self.context.subtasks = final_state["subtasks"]
        
        self.context.active_agent = "Orchestrator"
        await self.context.log("Orchestrator: Dynamic routing session finished.")
        
        await session.send_ws_message({
            "type": "agent_state",
            "active_agent": "Orchestrator",
            "active_task": "All tasks completed",
            "subtasks": self.context.subtasks,
            "collaboration_log": self.context.collaboration_log
        })
        
        final_history_summary = "\n".join(self.context.collaboration_log)
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are the head Orchestrator assistant. Summarize the task outcome clearly."),
            ("human", "{prompt_content}")
        ])
        prompt_content = summary_prompt_template.format(
            task_description=task_description,
            final_history_summary=final_history_summary
        )
        
        llm = DevPilotChatModel(session=session, agent_name="Orchestrator Agent")
        chain = chat_prompt | llm
        try:
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            response_text = response_msg.content
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