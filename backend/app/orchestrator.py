import json
import logging
import asyncio
import uuid
import time
import re
import os
from typing import List, Dict, Any, TypedDict, Optional
from pydantic import BaseModel, Field, ValidationError
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks.manager import CallbackManagerForLLMRun


# ---------------------------------------------------------------------------
# Structured output model for orchestrator routing decisions.
# Replaces ad-hoc dict access on raw LLM JSON, giving us schema validation
# and clean ValidationError tracebacks instead of silent bad state.
# ---------------------------------------------------------------------------
class OrchestratorDecision(BaseModel):
    """Validated schema for the orchestrator LLM routing decision."""
    agents: List[str] = Field(
        default_factory=list,
        description="Agent names to invoke next"
    )
    reasoning: str = Field(
        default="",
        description="Why these agents were chosen"
    )
    descriptions: List[str] = Field(
        default_factory=list,
        description="Task description per agent, index-aligned with agents list"
    )

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
    "You are the Planner Agent for DevPilot IDE. Decompose this coding request into an "
    "ordered, dependency-aware subtask plan for specialist agents.\n\n"
    "Request: {task_description}\n\n"
    "RULES:\n"
    "- Only include agents that are actually needed. Do not include Documentation, Git, "
    "or Testing agents unless the request specifically requires them.\n"
    "- Simple single-file changes need only: File System Agent + one coding agent. "
    "Do NOT add unnecessary phases.\n"
    "- Tasks with empty dependencies[] run in parallel.\n"
    "- Choose EXACTLY ONE of: Coding Agent, Frontend Developer Agent, or Backend Developer "
    "Agent (based on what files change — never all three on the same files).\n"
    "- Only add Terminal Agent if the task requires running commands to verify.\n"
    "- Only add Testing Agent if tests exist or are being created.\n\n"
    "Output ONLY a JSON array with no other text:\n"
    "[\n"
    '  {{"id": 1, "agent": "Requirement Analysis Agent", "description": "...", "dependencies": []}},\n'
    '  {{"id": 2, "agent": "File System Agent", "description": "...", "dependencies": [1]}},\n'
    '  {{"id": 3, "agent": "Backend Developer Agent", "description": "...", "dependencies": [2]}}\n'
    "]\n\n"
    "Available agents: Planner Agent, Requirement Analysis Agent, Coding Agent, "
    "Frontend Developer Agent, Backend Developer Agent, File System Agent, Software Architect Agent, "
    "Terminal Agent, Testing Agent, Debugging Agent, Documentation Agent, Code Review Agent, "
    "Security Agent, Performance Agent, API Agent, Database Agent, Integration Agent, "
    "DevOps Agent, AI Reviewer Agent, Git Agent, Release Agent."
)

requirement_prompt_template = PromptTemplate.from_template(
    "You are the Requirement Analysis Agent. Walk the live workspace file tree and identify "
    "exactly which files need to be read or modified for this task.\n\n"
    "Task: {task_description}\n\n"
    "Rules:\n"
    "- Output a JSON list of relative file paths. No other text.\n"
    "- Only include files that are directly relevant to the task.\n"
    "- If a config file (tsconfig.json, package.json, requirements.txt) is affected, include it.\n"
    "- Do not include test files unless the task is specifically about tests.\n"
    "- Max 10 files. If you need more, the task should be broken into subtasks.\n\n"
    "Example output: [\"src/components/Auth.tsx\", \"backend/app/routes/auth.py\"]\n\n"
    "Store result in shared_memory[\"target_files\"] ."
)

coding_prompt_template = PromptTemplate.from_template(
    "You are the Coding Agent — a senior software engineer. Implement the required changes "
    "precisely and completely.\n\n"
    "Task: {task_description}\n"
    "Target files from shared_memory: {target_files}\n"
    "File contents from shared_memory: {file_contents}\n\n"
    "RULES:\n"
    "1. Read the file contents above BEFORE making any changes.\n"
    "2. Use edit_file for targeted changes to existing files.\n"
    "3. Use write_file only for new files or complete rewrites.\n"
    "4. NEVER truncate code. Output complete file contents.\n"
    "5. NEVER use placeholder comments like '# TODO' or '... rest of code'.\n"
    "6. Add type hints to every function you write.\n"
    "7. Follow the existing code style in each file.\n"
    "8. After changes, run the appropriate build/lint command to verify.\n\n"
    "Shared memory context:\n{shared_memory}"
)

terminal_prompt_template = PromptTemplate.from_template(
    "Name a logical terminal command (e.g. 'npm run build', 'npm run test', 'pytest') "
    "to verify this task:\n\n"
    "Task: {task_description}\n\n"
    "Respond with ONLY the command string. If no command is needed, output 'NONE'."
)

debugging_prompt_template = PromptTemplate.from_template(
    "You are the Debugging Agent — a principal engineer who diagnoses and fixes issues.\n\n"
    "Task: {task_description}\n"
    "Error output: {build_error}\n"
    "Recent changes: {recent_commits}\n"
    "File contents: {file_contents}\n\n"
    "PROCESS:\n"
    "1. State the root cause in ONE sentence (file:line — what and why).\n"
    "2. Apply the minimal surgical fix using edit_file. Never rewrite unrelated code.\n"
    "3. Explain why the bug existed (the mechanism, not just 'it was wrong').\n"
    "4. Suggest ONE concrete prevention (lint rule, type check, test) for this bug class.\n"
    "5. Re-run the failing command to confirm the fix works.\n\n"
    "Shared memory context:\n{shared_memory}"
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
    "You are the Orchestrator Agent. Your role is to resolve the user request by routing work "
    "to specialized agents. You must produce a forward-looking action plan every turn.\n\n"
    "User Request: {task_description}\n\n"
    "{agents_description}\n"
    "Collaboration Log (most recent at bottom):\n{history_summary}\n\n"
    "Shared Memory Keys Available:\n{memory_summary}\n\n"
    "Already completed agents: {completed_agents}\n\n"
    "Decision Rules:\n"
    "1. ALWAYS start with Requirement Analysis Agent → File System Agent before any coding agents.\n"
    "2. MAXIMIZE parallelism: after files are read, run Coding/Frontend/Backend Developer Agents concurrently.\n"
    "3. After code changes, run Terminal Agent + Testing Agent + Code Review Agent IN PARALLEL.\n"
    "4. Run Security Agent, Performance Agent, and Documentation Agent in a final parallel pass.\n"
    "5. Call Git Agent last to summarize diffs.\n"
    "6. ONLY return 'Orchestrator' (done signal) when ALL of these are complete: "
    "code written, tests run, docs written, git status checked.\n"
    "7. NEVER repeat an agent that already has a ✅ in the collaboration log or is in the completed list: {completed_agents}.\n"
    "8. If a previous agent produced an error, route to Debugging Agent FIRST before retrying.\n"
    "9. RULE: Never call Coding/Frontend/Backend Agents unless either "
    "shared_memory['file_contents'] is non-empty OR shared_memory"
    "['target_files'] contains new files to create for a new project.\n\n"
    "Output ONLY a JSON object:\n"
    '{{"agents": [...], "reasoning": "...", "descriptions": [...]}}\n\n'
    "Example — parallel post-code pass:\n"
    '{{"agents": ["Terminal Agent", "Testing Agent", "Code Review Agent"], '
    '"reasoning": "Code changes complete — verify build, run tests, and audit in parallel.", '
    '"descriptions": ["npm run build", "pytest --tb=short", "Review all modified files for correctness"]}}\n\n'
    "Example — done:\n"
    '{{"agents": ["Orchestrator"], "reasoning": "All required steps confirmed complete.", '
    '"descriptions": ["Task complete"]}}'
)

summary_prompt_template = PromptTemplate.from_template(
    "You are the Orchestrator summarizing a completed agent session for the user.\n\n"
    "Original request: '{task_description}'\n\n"
    "Agent execution log:\n{final_history_summary}\n\n"
    "Write a clear, friendly summary that includes:\n"
    "1. What was done (one sentence per major action)\n"
    "2. Files created or modified (as a bullet list if any)\n"
    "3. Test/build outcome if a Terminal or Testing Agent ran\n"
    "4. Any issues found by Security/Performance/Review agents and whether they were fixed\n"
    "5. Next recommended steps (max 2)\n\n"
    "If the original request was conversational (e.g. 'hello', 'what can you do?'), "
    "respond directly and skip the structured format.\n\n"
    "Keep it under 200 words. Use markdown."
)

# ── New Agent Prompt Templates (LangChain) ──────────────────────────────────

frontend_planner_prompt_template = PromptTemplate.from_template(
    "You are the Frontend Planner Agent. Create a detailed frontend development plan for:\n\n"
    "Task: {task_description}\n\n"
    "Define:\n"
    "1. UI architecture and page hierarchy\n"
    "2. Component tree and reusable components\n"
    "3. State management approach (Context, Redux, Zustand)\n"
    "4. Routes and navigation structure\n"
    "5. Design system tokens (colors, typography, spacing)\n"
    "6. Responsive strategy (breakpoints, mobile-first)\n"
    "7. Accessibility requirements (WCAG 2.1)\n\n"
    "Output a structured Frontend Development Plan in markdown."
)

backend_planner_prompt_template = PromptTemplate.from_template(
    "You are the Backend Planner Agent. Create a detailed backend development plan for:\n\n"
    "Task: {task_description}\n\n"
    "Define:\n"
    "1. Backend architecture (REST/GraphQL/microservices)\n"
    "2. API structure and endpoint inventory\n"
    "3. Database schema and entity relationships\n"
    "4. Authentication and authorization strategy (JWT/OAuth/RBAC)\n"
    "5. Business logic layers (controllers/services/repositories)\n"
    "6. Queue, cache, and storage requirements\n"
    "7. Security threat model\n\n"
    "Output a structured Backend Development Plan in markdown."
)

architect_prompt_template = PromptTemplate.from_template(
    "You are the Software Architect Agent. Design the overall system architecture for:\n\n"
    "Task: {task_description}\n\n"
    "Produce:\n"
    "1. Recommended folder structure (feature-first or layer-first)\n"
    "2. Architecture pattern recommendation with justification\n"
    "3. Event flow diagram (text-based)\n"
    "4. API flow and data flow\n"
    "5. Key design patterns (Repository, Factory, Observer, etc.)\n"
    "6. Dependency graph between modules\n"
    "7. Domain-driven design bounded contexts\n\n"
    "Be specific and actionable. Output in markdown."
)

frontend_dev_prompt_template = PromptTemplate.from_template(
    "You are the Frontend Developer Agent — a senior React/TypeScript engineer.\n\n"
    "Task: {task_description}\n"
    "Target files: {target_files}\n"
    "File contents: {file_contents}\n\n"
    "REQUIREMENTS:\n"
    "1. Strict TypeScript — zero `any` types. Use `unknown` + type guards where needed.\n"
    "2. Semantic HTML5 with aria-* attributes on every interactive element.\n"
    "3. Every component needs: loading state, error state, empty state.\n"
    "4. Mobile-first CSS. Use existing CSS custom properties/design tokens.\n"
    "5. Apply React.memo/useCallback/useMemo wherever re-renders are costly.\n"
    "6. Components ≤ 200 lines. Split growing components proactively.\n"
    "7. Read existing components to match the project's patterns before writing new ones.\n"
    "8. Output COMPLETE file contents. Never truncate with '...' or placeholders.\n\n"
    "After implementing, run: tsc --noEmit to verify TypeScript compiles.\n\n"
    "Shared memory context:\n{shared_memory}"
)

backend_dev_prompt_template = PromptTemplate.from_template(
    "You are the Backend Developer Agent — a senior Python/FastAPI engineer.\n\n"
    "Task: {task_description}\n"
    "Target files: {target_files}\n"
    "File contents: {file_contents}\n\n"
    "REQUIREMENTS:\n"
    "1. Type hints on every function. Pydantic v2 models for all request/response schemas.\n"
    "2. Architecture: Controllers → Services → Repositories. No business logic in routes.\n"
    "3. Google-style docstrings on all public functions and classes.\n"
    "4. Structured logging: logger.info('event', extra={'key': value}).\n"
    "5. Typed, domain-specific exceptions. Never bare `except Exception`.\n"
    "6. No hardcoded secrets. All credentials via settings / env vars.\n"
    "7. Read existing routes/services first to match existing patterns.\n"
    "8. Output COMPLETE file contents. Never truncate with '...' or placeholders.\n\n"
    "After implementing, run: python -c 'import app' or the relevant test command.\n\n"
    "Shared memory context:\n{shared_memory}"
)

database_prompt_template = PromptTemplate.from_template(
    "You are the Database Agent. Design and implement database-related work for:\n\n"
    "Task: {task_description}\n\n"
    "Produce:\n"
    "1. Schema design: tables/collections, fields, data types\n"
    "2. Relationships: foreign keys, indexes, constraints\n"
    "3. Migration script (SQL or ORM Alembic format)\n"
    "4. Seed data for development/testing\n"
    "5. Query optimization suggestions (indexes, query plans)\n"
    "6. Backup and recovery strategy\n\n"
    "Output in markdown with SQL/ORM code blocks."
)

api_agent_prompt_template = PromptTemplate.from_template(
    "You are the API Agent. Create API contracts and documentation for:\n\n"
    "Task: {task_description}\n\n"
    "Produce:\n"
    "1. OpenAPI 3.0 YAML specification\n"
    "2. Request/response schemas with validation rules\n"
    "3. API versioning strategy (/v1/, /v2/)\n"
    "4. Rate limiting recommendations (per endpoint)\n"
    "5. Standard error response format\n"
    "6. Required authentication headers\n"
    "7. Example curl requests\n\n"
    "Output the OpenAPI YAML spec followed by implementation notes."
)

integration_prompt_template = PromptTemplate.from_template(
    "You are the Integration Agent. Verify all system components work correctly for:\n\n"
    "Task: {task_description}\n\n"
    "Codebase:\n{codebase_text}\n\n"
    "Verify and document:\n"
    "1. Frontend ↔ Backend API contract alignment\n"
    "2. Database connection and ORM query correctness\n"
    "3. Authentication flow end-to-end\n"
    "4. External API integrations and error handling\n"
    "5. Cache and queue connectivity\n"
    "6. Environment variable requirements\n"
    "7. Any integration gaps or type mismatches\n\n"
    "Output an integration verification report in markdown."
)

security_prompt_template = PromptTemplate.from_template(
    "You are the Security Agent — an OWASP-certified application security engineer.\n\n"
    "Task: {task_description}\n"
    "Files to audit: {file_contents}\n\n"
    "AUDIT SCOPE — check every item:\n"
    "  CRITICAL: SQL/NoSQL injection, hardcoded secrets/API keys, auth bypass, RCE vectors\n"
    "  HIGH:     XSS (reflected/stored/DOM), CSRF gaps, JWT alg=none, IDOR, missing authz\n"
    "  MEDIUM:   Missing rate limiting, weak session config, insecure headers, open redirects\n"
    "  LOW:      Verbose error messages, missing input validation, dep version warnings\n\n"
    "RULES:\n"
    "- For large codebases, chunk into ≤8000-char segments and audit each.\n"
    "- Never silently skip files. Process everything.\n"
    "- For each finding: file path, line number, severity, description, recommended fix.\n\n"
    "Output: SECURITY_REPORT.md with findings grouped by severity (CRITICAL → LOW).\n"
    "If no issues found: state 'No issues found' per category — don't skip categories.\n\n"
    "Shared memory context:\n{shared_memory}"
)

performance_prompt_template = PromptTemplate.from_template(
    "You are the Performance Agent. Analyze and optimize performance for:\n\n"
    "Task: {task_description}\n\n"
    "Codebase:\n{codebase_text}\n\n"
    "Review and optimize:\n"
    "1. Frontend bundle size — identify heavy dependencies, suggest lazy loading\n"
    "2. Unnecessary re-renders — identify missing React.memo/useCallback\n"
    "3. Backend query efficiency — identify N+1 queries, missing indexes\n"
    "4. Caching opportunities — Redis, in-memory, HTTP cache headers\n"
    "5. Image and asset optimization strategies\n"
    "6. Memory usage patterns — leaks, excessive allocations\n"
    "7. Response time bottlenecks — profiling recommendations\n\n"
    "Output a PERFORMANCE_REPORT.md with specific actionable improvements and estimated impact."
)

ai_reviewer_prompt_template = PromptTemplate.from_template(
    "You are the AI Reviewer Agent, acting as a Senior Staff Engineer. Deep technical review of:\n\n"
    "Task: {task_description}\n\n"
    "Codebase:\n{codebase_text}\n\n"
    "Review for:\n"
    "1. Algorithm efficiency — suggest better time/space complexities\n"
    "2. Technical debt — identify and suggest elimination\n"
    "3. Architecture simplification opportunities\n"
    "4. Code maintainability score (1-10) with detailed justification\n"
    "5. SOLID principles violations (identify specific file+line)\n"
    "6. Missing abstractions or over-engineering\n"
    "7. Top 3 highest-priority refactors with code examples\n\n"
    "Be precise, honest, and include before/after code examples. Output in markdown."
)

devops_prompt_template = PromptTemplate.from_template(
    "You are the DevOps Agent. Create infrastructure and deployment configuration for:\n\n"
    "Task: {task_description}\n\n"
    "Produce complete, production-ready configurations:\n"
    "1. Dockerfile (multi-stage build)\n"
    "2. docker-compose.yml (with volumes, networks, health checks)\n"
    "3. GitHub Actions CI/CD workflow (.github/workflows/ci.yml)\n"
    "4. NGINX reverse proxy config (if applicable)\n"
    "5. Environment variables documentation (.env.example)\n"
    "6. Monitoring setup (Prometheus/Grafana or similar)\n\n"
    "Label each file clearly and use proper code blocks."
)

release_prompt_template = PromptTemplate.from_template(
    "You are the Release Agent. Prepare the production release for:\n\n"
    "Task: {task_description}\n\n"
    "Collaboration Log:\n{history_summary}\n\n"
    "Produce a complete RELEASE_NOTES.md containing:\n"
    "1. Version recommendation (semantic versioning: MAJOR.MINOR.PATCH)\n"
    "2. Release notes in changelog format (Added/Changed/Fixed/Removed)\n"
    "3. Production deployment checklist (step-by-step)\n"
    "4. Rollback plan (step-by-step procedure)\n"
    "5. Post-deployment monitoring plan\n"
    "6. Go/No-Go criteria checklist\n\n"
    "Output a professional RELEASE_NOTES.md document."
)

logger = logging.getLogger("devpilot.orchestrator")

ASK_MODE_SYSTEM_PROMPT = (
    "You are DevPilot, an expert AI coding assistant. "
    "Answer the user's question directly and concisely. "
    "If it's a greeting, respond warmly in one sentence. "
    "If it's a technical question, give a precise, expert answer. "
    "Do not mention tools, agents, or orchestration. "
    "Do not use headers or bullets for simple questions. "
    "Never say 'Great question!' or similar filler."
)

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
    """Breaks down requests into a logical sequence of subtasks with dependencies."""
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
    """Identifies target files to read/modify for a given task."""
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
    """Reads multiple codebase files concurrently."""
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
    """General-purpose code generator that modifies files to implement features."""
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
            
            auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": clean_code}, auto_apply=auto_apply)
            
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
    """Runs arbitrary build, verification, and terminal commands."""
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
    """Runs tests (pytest/npm test) to verify code changes."""
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
    """Diagnoses errors in collaboration logs and proposes code fixes."""
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
    """Generates technical documentation and writes DOCS.md."""
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
        
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": doc_content}, auto_apply=auto_apply)
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
    """Audits codebase changes for style, bugs, efficiency, and correctness."""
    def __init__(self, orchestrator):
        super().__init__("Code Review Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Code Review Agent: Auditing codebase modifications...")
        await self.orchestrator.update_task_progress(task_id, 30, session)
        
        file_contents = await async_get_codebase_dict(session.workspace_root)
        chunks = chunked_codebase(file_contents)
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        findings = []
        for i, chunk in enumerate(chunks):
            await self.orchestrator.context.log(f"Code Review Agent: Auditing chunk {i+1}/{len(chunks)}...")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a senior code reviewer. Provide constructive criticism and issues found."),
                ("human", "{prompt_content}")
            ])
            prompt_content = review_prompt_template.format(task_description=task_description, codebase_text=chunk)
            chain = chat_prompt | llm
            review_msg = await chain.ainvoke({"prompt_content": prompt_content})
            findings.append(review_msg.content)
            
        review = "\n\n".join(findings)
        
        await self.orchestrator.context.log(f"Code Review Agent: Review completed. Summary:\n{review[:250]}...")
        self.orchestrator.context.memory["review"] = review
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class GitAgent(BaseAgent):
    """Audits git status and command diffs for workspace changes."""
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


# ── New Specialized Agents (LangGraph nodes) ─────────────────────────────────

class FrontendPlannerAgent(BaseAgent):
    """Plans UI architecture, component hierarchy, state management, and design system."""
    def __init__(self, orchestrator):
        super().__init__("Frontend Planner Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Frontend Planner Agent: Creating UI/UX architecture plan...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior frontend architect. Output a detailed, actionable frontend development plan."),
            ("human", "{prompt_content}")
        ])
        prompt_content = frontend_planner_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        plan = response_msg.content

        self.orchestrator.context.memory["frontend_plan"] = plan
        await self.orchestrator.context.log(f"Frontend Planner Agent: Plan ready.\n{plan[:200]}...")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Frontend Development Plan created."


class BackendPlannerAgent(BaseAgent):
    """Plans API structure, database schema, authentication, business logic, and infrastructure."""
    def __init__(self, orchestrator):
        super().__init__("Backend Planner Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Backend Planner Agent: Designing backend architecture plan...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior backend architect. Output a detailed, actionable backend development plan."),
            ("human", "{prompt_content}")
        ])
        prompt_content = backend_planner_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        plan = response_msg.content

        self.orchestrator.context.memory["backend_plan"] = plan
        await self.orchestrator.context.log(f"Backend Planner Agent: Plan ready.\n{plan[:200]}...")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Backend Development Plan created."


class SoftwareArchitectAgent(BaseAgent):
    """Designs folder structure, architecture patterns, event/API/DB flows, and design patterns."""
    def __init__(self, orchestrator):
        super().__init__("Software Architect Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Software Architect Agent: Designing system architecture...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a principal software architect. Design clean, scalable, production-ready system architecture."),
            ("human", "{prompt_content}")
        ])
        prompt_content = architect_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        architecture = response_msg.content

        self.orchestrator.context.memory["architecture"] = architecture
        await self.orchestrator.context.log(f"Software Architect Agent: Architecture ready.\n{architecture[:200]}...")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "System architecture designed."


class FrontendDeveloperAgent(BaseAgent):
    """Builds React/TypeScript UI: components, pages, hooks, animations, accessibility, SEO."""
    def __init__(self, orchestrator):
        super().__init__("Frontend Developer Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Frontend Developer Agent: Building UI components...")
        await self.orchestrator.update_task_progress(task_id, 10, session)

        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = self.orchestrator.context.memory.get("file_contents", {})

        frontend_prefixes = ("frontend/", "src/", "components/", "pages/", "app/", ".tsx", ".ts", ".jsx", ".js", ".css")
        frontend_files = [f for f in target_files if any(f.startswith(p) or f.endswith(p) for p in frontend_prefixes)]
        if not frontend_files:
            frontend_files = target_files

        if not frontend_files:
            await self.orchestrator.context.log("Frontend Developer Agent: No frontend files to modify.")
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No frontend files to modify."

        async def process_file(path: str):
            original = file_contents.get(path, "")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a senior React/TypeScript developer. Output ONLY raw file content, no markdown."),
                ("human", "{prompt_content}")
            ])
            prompt_content = frontend_dev_prompt_template.format(
                task_description=task_description, path=path, original=original
            )
            llm = DevPilotChatModel(session=session, agent_name=self.name)
            chain = chat_prompt | llm
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            new_code = response_msg.content.strip()
            if new_code.startswith("```"):
                lines = new_code.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                new_code = "\n".join(lines)

            tc_id = f"fedev_{task_id}_{uuid.uuid4().hex[:6]}"
            await session.send_ws_message({
                "type": "status", "status": "tool_executing",
                "message": f"Frontend Developer writing {path}...",
                "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": new_code}}
            })
            auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": new_code}, auto_apply=auto_apply)
            await session.send_ws_message({
                "type": "tool_result", "tool_call_id": tc_id,
                "name": "write_file", "status": "success", "result": result
            })
            await self.orchestrator.context.log(f"Frontend Developer Agent: Updated {path}.")

        await asyncio.gather(*[process_file(p) for p in frontend_files])
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Frontend components implemented."


class BackendDeveloperAgent(BaseAgent):
    """Builds REST APIs, auth, controllers, services, repositories, middleware, validation, logging."""
    def __init__(self, orchestrator):
        super().__init__("Backend Developer Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Backend Developer Agent: Building API services...")
        await self.orchestrator.update_task_progress(task_id, 10, session)

        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = self.orchestrator.context.memory.get("file_contents", {})

        backend_prefixes = ("backend/", "app/", "api/", "server/", ".py", ".go", ".java")
        backend_files = [f for f in target_files if any(f.startswith(p) or f.endswith(p) for p in backend_prefixes)]
        if not backend_files:
            backend_files = target_files

        if not backend_files:
            await self.orchestrator.context.log("Backend Developer Agent: No backend files to modify.")
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No backend files to modify."

        async def process_file(path: str):
            original = file_contents.get(path, "")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a senior backend engineer. Output ONLY raw file content, no markdown."),
                ("human", "{prompt_content}")
            ])
            prompt_content = backend_dev_prompt_template.format(
                task_description=task_description, path=path, original=original
            )
            llm = DevPilotChatModel(session=session, agent_name=self.name)
            chain = chat_prompt | llm
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            new_code = response_msg.content.strip()
            if new_code.startswith("```"):
                lines = new_code.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                new_code = "\n".join(lines)

            tc_id = f"bedev_{task_id}_{uuid.uuid4().hex[:6]}"
            await session.send_ws_message({
                "type": "status", "status": "tool_executing",
                "message": f"Backend Developer writing {path}...",
                "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": new_code}}
            })
            auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": new_code}, auto_apply=auto_apply)
            await session.send_ws_message({
                "type": "tool_result", "tool_call_id": tc_id,
                "name": "write_file", "status": "success", "result": result
            })
            await self.orchestrator.context.log(f"Backend Developer Agent: Updated {path}.")

        await asyncio.gather(*[process_file(p) for p in backend_files])
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Backend services implemented."


class DatabaseAgent(BaseAgent):
    """Designs schemas, migrations, indexes, seed data, and query optimizations. Writes DATABASE_DESIGN.md."""
    def __init__(self, orchestrator):
        super().__init__("Database Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Database Agent: Designing schema and migrations...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior database architect. Design optimal schemas and migration scripts."),
            ("human", "{prompt_content}")
        ])
        prompt_content = database_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        db_design = response_msg.content

        self.orchestrator.context.memory["db_design"] = db_design
        await self.orchestrator.update_task_progress(task_id, 60, session)

        path = "DATABASE_DESIGN.md"
        tc_id = f"db_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing database design to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": db_design}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": db_design}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"Database Agent: Schema and migrations documented in {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Database schema and migrations designed."


class APIAgent(BaseAgent):
    """Creates OpenAPI/Swagger contracts, request/response validation, versioning. Writes API_SPEC.md."""
    def __init__(self, orchestrator):
        super().__init__("API Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("API Agent: Generating OpenAPI contracts...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert API designer. Generate OpenAPI 3.0 specs and validation rules."),
            ("human", "{prompt_content}")
        ])
        prompt_content = api_agent_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        api_spec = response_msg.content

        self.orchestrator.context.memory["api_spec"] = api_spec
        await self.orchestrator.update_task_progress(task_id, 60, session)

        path = "API_SPEC.md"
        tc_id = f"api_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing API specification to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": api_spec}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": api_spec}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"API Agent: OpenAPI specification written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "API contracts and OpenAPI spec generated."


class IntegrationAgent(BaseAgent):
    """Connects and verifies frontend/backend/DB/auth/external APIs are correctly integrated."""
    def __init__(self, orchestrator):
        super().__init__("Integration Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Integration Agent: Verifying full system integration...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        from .async_files import async_get_codebase_contents
        codebase_text = await async_get_codebase_contents(session.workspace_root)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior integration engineer. Verify all system components connect correctly."),
            ("human", "{prompt_content}")
        ])
        prompt_content = integration_prompt_template.format(
            task_description=task_description, codebase_text=codebase_text[:8000]
        )
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        integration_report = response_msg.content

        self.orchestrator.context.memory["integration_report"] = integration_report
        await self.orchestrator.context.log(f"Integration Agent: Integration verified.\n{integration_report[:250]}...")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Integration verification complete."


class SecurityAgent(BaseAgent):
    """OWASP Top 10 audit, XSS/CSRF/SQLi detection, JWT/RBAC checks. Writes SECURITY_REPORT.md."""
    def __init__(self, orchestrator):
        super().__init__("Security Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Security Agent: Running OWASP security audit...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        file_contents = await async_get_codebase_dict(session.workspace_root)
        chunks = chunked_codebase(file_contents)

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        findings = []
        for i, chunk in enumerate(chunks):
            await self.orchestrator.context.log(f"Security Agent: Auditing chunk {i+1}/{len(chunks)}...")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a senior application security engineer. Perform thorough OWASP-based security audits."),
                ("human", "{prompt_content}")
            ])
            prompt_content = security_prompt_template.format(
                task_description=task_description, codebase_text=chunk
            )
            chain = chat_prompt | llm
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            findings.append(response_msg.content)

        security_report = "\n\n".join(findings)

        self.orchestrator.context.memory["security_report"] = security_report
        await self.orchestrator.update_task_progress(task_id, 60, session)

        path = "SECURITY_REPORT.md"
        tc_id = f"sec_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing security report to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": security_report}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": security_report}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"Security Agent: Security audit complete. Report in {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Security audit complete."


class PerformanceAgent(BaseAgent):
    """Optimizes frontend/backend/DB performance: bundles, queries, caching, memory. Writes PERFORMANCE_REPORT.md."""
    def __init__(self, orchestrator):
        super().__init__("Performance Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Performance Agent: Analyzing performance bottlenecks...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        file_contents = await async_get_codebase_dict(session.workspace_root)
        chunks = chunked_codebase(file_contents)

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        findings = []
        for i, chunk in enumerate(chunks):
            await self.orchestrator.context.log(f"Performance Agent: Auditing chunk {i+1}/{len(chunks)}...")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a performance engineering expert. Identify and fix performance issues."),
                ("human", "{prompt_content}")
            ])
            prompt_content = performance_prompt_template.format(
                task_description=task_description, codebase_text=chunk
            )
            chain = chat_prompt | llm
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            findings.append(response_msg.content)

        perf_report = "\n\n".join(findings)

        self.orchestrator.context.memory["perf_report"] = perf_report
        await self.orchestrator.update_task_progress(task_id, 60, session)

        path = "PERFORMANCE_REPORT.md"
        tc_id = f"perf_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing performance report to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": perf_report}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": perf_report}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"Performance Agent: Report written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Performance analysis complete."


class AIReviewerAgent(BaseAgent):
    """Senior Staff Engineer deep review: algorithms, tech debt, SOLID, maintainability."""
    def __init__(self, orchestrator):
        super().__init__("AI Reviewer Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("AI Reviewer Agent: Deep technical review as Staff Engineer...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        file_contents = await async_get_codebase_dict(session.workspace_root)
        chunks = chunked_codebase(file_contents)

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        findings = []
        for i, chunk in enumerate(chunks):
            await self.orchestrator.context.log(f"AI Reviewer Agent: Auditing chunk {i+1}/{len(chunks)}...")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a Staff/Principal Engineer. Perform a deep, honest technical review."),
                ("human", "{prompt_content}")
            ])
            prompt_content = ai_reviewer_prompt_template.format(
                task_description=task_description, codebase_text=chunk
            )
            chain = chat_prompt | llm
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            findings.append(response_msg.content)

        ai_review = "\n\n".join(findings)

        self.orchestrator.context.memory["ai_review"] = ai_review
        await self.orchestrator.context.log(f"AI Reviewer Agent: Deep review complete.\n{ai_review[:250]}...")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "AI deep review complete."


class DevOpsAgent(BaseAgent):
    """Creates Docker, docker-compose, GitHub Actions CI/CD, NGINX config. Writes DEVOPS_CONFIG.md."""
    def __init__(self, orchestrator):
        super().__init__("DevOps Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("DevOps Agent: Creating Docker and CI/CD configuration...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior DevOps engineer. Create production-ready Docker and CI/CD configs."),
            ("human", "{prompt_content}")
        ])
        prompt_content = devops_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        devops_config = response_msg.content

        self.orchestrator.context.memory["devops_config"] = devops_config
        await self.orchestrator.update_task_progress(task_id, 60, session)

        path = "DEVOPS_CONFIG.md"
        tc_id = f"devops_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing DevOps configuration to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": devops_config}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": devops_config}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"DevOps Agent: Configuration written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Docker and CI/CD configuration generated."


class ReleaseAgent(BaseAgent):
    """Prepares production builds: versioning, release notes, deployment checklist, rollback plan. Writes RELEASE_NOTES.md."""
    def __init__(self, orchestrator):
        super().__init__("Release Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Release Agent: Preparing production release package...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        history_summary = "\n".join(self.orchestrator.context.collaboration_log[-30:])

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a release engineer. Prepare comprehensive, professional release documentation."),
            ("human", "{prompt_content}")
        ])
        prompt_content = release_prompt_template.format(
            task_description=task_description, history_summary=history_summary
        )
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        release_notes = response_msg.content

        self.orchestrator.context.memory["release_notes"] = release_notes
        await self.orchestrator.update_task_progress(task_id, 60, session)

        path = "RELEASE_NOTES.md"
        tc_id = f"rel_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing release notes to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": release_notes}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": release_notes}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"Release Agent: Release notes written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Release package prepared."

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
    """Merge two collaboration log lists.

    Only suppresses *consecutive* identical entries (e.g. two back-to-back
    orchestrator heartbeat lines).  Legitimate duplicate messages from different
    agents at different points in time are preserved, since a set-based global
    dedup would silently swallow them and corrupt routing decisions.
    """
    combined = list(left or [])
    for item in (right or []):
        if not combined or combined[-1] != item:
            combined.append(item)
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

MAX_CHARS = 8000

async def async_get_codebase_dict(workspace_root: str) -> dict:
    exclude_dirs = {".git", "node_modules", "venv", "__pycache__", ".devpilot", "dist", "build"}
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}

    def _sync_scan() -> dict:
        is_editor_root = False
        try:
            is_editor_root = (
                os.path.isdir(os.path.join(workspace_root, "backend", "app")) and
                os.path.isdir(os.path.join(workspace_root, "frontend", "src"))
            )
        except Exception:
            pass

        file_dict = {}
        for root, dirs, files in os.walk(workspace_root):
            current_excludes = set(exclude_dirs)
            if is_editor_root and root == os.path.realpath(workspace_root):
                current_excludes.update({"frontend", "backend", "venv"})
            dirs[:] = [d for d in dirs if d not in current_excludes]

            if is_editor_root and os.path.realpath(root) == os.path.realpath(workspace_root):
                files = [f for f in files if f not in {"requirements.txt", "run.py", "README.md"}]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_extensions:
                    continue
                abs_file_path = os.path.join(root, file)
                rel_file_path = os.path.relpath(abs_file_path, workspace_root).replace("\\", "/")
                try:
                    with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    file_dict[rel_file_path] = content
                except Exception:
                    continue
        return file_dict

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_scan)


def chunked_codebase(file_contents: dict, max_chars=MAX_CHARS):
    chunks, current, size = [], [], 0
    for path, content in file_contents.items():
        entry = f"### {path}\n{content}\n"
        if size + len(entry) > max_chars and current:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(entry)
        size += len(entry)
    if current:
        chunks.append("\n".join(current))
    return chunks

async def maybe_summarise_log(state: AgentState, session) -> AgentState:
    log = state.get("collaboration_log", [])
    if len(log) > 10:
        to_summarise = log[:-5]
        fresh_log = log[-5:]
        summary_prompt = (
            "You are a summarization system for agent collaboration history.\n"
            "Summarize the following steps taken by the agents so far into a concise bullet list "
            "focusing only on what was successfully built, modified, tested, or verified. "
            "Keep the summary under 150 words.\n\n"
            "Steps to summarize:\n" + "\n".join(to_summarise)
        )
        try:
            from .adapters.router import ModelRouter
            router = ModelRouter()
            messages = [{"role": "user", "content": summary_prompt}]
            summary_text = await router.completion(
                session.profile, 
                messages, 
                "You are an assistant that summarizes logs.",
                is_agent=True,
                task_type="summarize"
            )
            summary_line = f"[Summary of prior steps]: {summary_text.strip()}"
            state["collaboration_log"] = [summary_line] + fresh_log
            if session:
                session.collaboration_log = state["collaboration_log"]
        except Exception as e:
            logger.error(f"Failed to summarize collaboration log: {e}")
    return state

async def orchestrator_node(state: AgentState) -> AgentState:
    state["step_count"] += 1
    
    orchestrator = state["orchestrator"]
    max_steps = 30
    if hasattr(orchestrator, "max_steps") and isinstance(orchestrator.max_steps, int):
        max_steps = orchestrator.max_steps
        
    if state["step_count"] >= max_steps:
        state["next_agents"] = []  # routes to END
        state["agent_tasks"] = {}
        if state["session"]:
            await state["session"].send_ws_message({
                "type": "text_delta",
                "content": "⚠️ Step limit reached. Handover note: Execution paused as maximum step limit was reached."
            })
        return state

    # Summarize collaboration log if it grows too long to save context tokens
    session = state.get("session")
    state = await maybe_summarise_log(state, session)

    if hasattr(orchestrator, "agents") and isinstance(orchestrator.agents, dict):
        agents_description = "\n".join(
            f"- {name}: {agent.__doc__ or 'No description.'}"
            for name, agent in orchestrator.agents.items()
        )
    else:
        agents_description = "No description available."

    history_summary = "\n".join(state["collaboration_log"])
    memory_summary = json.dumps(state["memory"])
    
    completed_agents = [
        t.get("agent") for t in state.get("subtasks", [])
        if t.get("status") in ("completed", "success") and t.get("agent")
    ]
    
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a master software architect routing coordinator. Output ONLY valid JSON."),
        ("human", "{prompt_content}")
    ])
    prompt_content = orchestrator_prompt_template.format(
        task_description=state["task_description"],
        agents_description=agents_description,
        history_summary=history_summary,
        memory_summary=memory_summary,
        completed_agents=", ".join(completed_agents) if completed_agents else "None"
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
        # --- Strip markdown fences if present ---
        clean_res = response.strip()
        if clean_res.startswith("```json"):
            clean_res = clean_res[7:]
        if clean_res.startswith("```"):
            clean_res = clean_res[3:]
        if clean_res.endswith("```"):
            clean_res = clean_res[:-3]
        clean_res = clean_res.strip()

        # --- Parse JSON then validate with Pydantic ---
        raw_decision = json.loads(clean_res)

        # Normalise: some LLMs emit {"agent": ...} instead of {"agents": [...]}
        if "agents" not in raw_decision and "agent" in raw_decision:
            raw_decision["agents"] = [raw_decision["agent"]]
        if "descriptions" not in raw_decision and "description" in raw_decision:
            raw_decision["descriptions"] = [raw_decision["description"]]

        decision = OrchestratorDecision(**raw_decision)

        selected_agents = decision.agents or ["Orchestrator"]
        descriptions = decision.descriptions

        # Build tasks mapping (index-aligned)
        for i, name in enumerate(selected_agents):
            desc = descriptions[i] if i < len(descriptions) else "Execute task"
            agent_tasks[name] = desc

        if decision.reasoning and state["session"]:
            await state["session"].send_ws_message({
                "type": "thinking",
                "content": f"Decision: {decision.reasoning}"
            })
        if state["session"]:
            for name in selected_agents:
                if name != "Orchestrator":
                    await state["session"].send_ws_message({
                        "type": "thinking",
                        "content": f"Routing to {name}..."
                    })
        log_msg = (
            f"Orchestrator: Selected agent(s) {selected_agents} to run in parallel. "
            f"Reasoning: {decision.reasoning}"
        )
        state["collaboration_log"].append(log_msg)
        state["orchestrator"].context.collaboration_log = state["collaboration_log"]
        logger.info(log_msg)
    except (json.JSONDecodeError, ValidationError) as e:
        log_msg = f"Orchestrator: Decision parse/validation error, defaulting to complete: {str(e)}"
        state["collaboration_log"].append(log_msg)
        state["orchestrator"].context.collaboration_log = state["collaboration_log"]
        logger.warning(log_msg)
        selected_agents = ["Orchestrator"]
        agent_tasks = {"Orchestrator": "Task complete"}
    except Exception as e:
        log_msg = f"Orchestrator: Unexpected error in decision routing: {str(e)}"
        state["collaboration_log"].append(log_msg)
        state["orchestrator"].context.collaboration_log = state["collaboration_log"]
        logger.error(log_msg)
        selected_agents = ["Orchestrator"]
        agent_tasks = {"Orchestrator": "Task complete"}

    state["next_agents"] = selected_agents
    state["agent_tasks"] = agent_tasks

    # Serialize to Redis after orchestrator node planning
    is_mock = False
    if session:
        class_name = session.__class__.__name__
        if "Mock" in class_name or "MagicMock" in class_name:
            is_mock = True
            
    if not is_mock:
        try:
            from .state import redis_client
            if session and hasattr(session, "workspace_root"):
                workspace_id = os.path.basename(session.workspace_root) or "default"
                await redis_client.set(f"session:{workspace_id}:ctx", json.dumps(state["memory"]), ex=3600)
        except Exception as e:
            logger.error(f"Failed to persist context to Redis in orchestrator_node: {e}")
            
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
        
        orchestrator = state["orchestrator"]
        session = state["session"]
        is_mock = False
        if session:
            class_name = session.__class__.__name__
            if "Mock" in class_name or "MagicMock" in class_name:
                is_mock = True
                
        # Emit WebSocket event at the start of agent node
        if not is_mock:
            try:
                await orchestrator.update_task_progress(subtask_id, 10, session, "running")
            except Exception as e:
                logger.error(f"Error updating start task progress: {e}")
        
        await session.send_ws_message({
            "type": "agent_state",
            "active_agent": agent_name,
            "active_task": agent_description,
            "subtasks": state["subtasks"],
            "collaboration_log": state["collaboration_log"]
        })
        
        agent = orchestrator.agents[agent_name]
        status = "completed"
        progress = 100
        try:
            await agent.execute(agent_description, session, subtask_id)
        except Exception as e:
            status = "failed"
            progress = 100
            await orchestrator.context.log(f"Orchestrator: Error executing agent {agent_name}: {str(e)}")
            
        # Emit WebSocket event at the end of agent node
        if not is_mock:
            try:
                await orchestrator.update_task_progress(subtask_id, progress, session, status)
            except Exception as e:
                logger.error(f"Error updating end task progress: {e}")
                
        await session.send_ws_message({
            "type": "agent_state",
            "active_agent": agent_name,
            "active_task": "Step finished",
            "subtasks": state["subtasks"],
            "collaboration_log": state["collaboration_log"]
        })
        
        # Serialize to Redis after agent execution
        if not is_mock:
            try:
                from .state import redis_client
                if session and hasattr(session, "workspace_root"):
                    workspace_id = os.path.basename(session.workspace_root) or "default"
                    await redis_client.set(f"session:{workspace_id}:ctx", json.dumps(state["memory"]), ex=3600)
            except Exception as e:
                logger.error(f"Failed to persist context to Redis in agent turn: {e}")
                
        return state
    return node

def route_next(state: AgentState):
    next_agents = state.get("next_agents", [])
    valid_agents = []
    for name in next_agents:
        if name in state["orchestrator"].agents:
            valid_agents.append(name)
    if not valid_agents:
        return "end"
    if len(valid_agents) == 1:
        return valid_agents[0]
    return valid_agents

class AgentOrchestrator:
    def __init__(self, max_steps: int = 30):
        self.max_steps = max_steps
        self.context = SharedContext()
        self.event_bus = EventBus()
        self.agents = {
            # Tier 1: Planning
            "Planner Agent": PlannerAgent(self),
            "Frontend Planner Agent": FrontendPlannerAgent(self),
            "Backend Planner Agent": BackendPlannerAgent(self),
            "Requirement Analysis Agent": RequirementAnalysisAgent(self),
            # Tier 2: Architecture
            "Software Architect Agent": SoftwareArchitectAgent(self),
            # Tier 3: Development
            "File System Agent": FileSystemAgent(self),
            "Coding Agent": CodingAgent(self),
            "Frontend Developer Agent": FrontendDeveloperAgent(self),
            "Backend Developer Agent": BackendDeveloperAgent(self),
            "Database Agent": DatabaseAgent(self),
            "API Agent": APIAgent(self),
            # Tier 4: Quality Assurance
            "Integration Agent": IntegrationAgent(self),
            "Testing Agent": TestingAgent(self),
            "Debugging Agent": DebuggingAgent(self),
            "Security Agent": SecurityAgent(self),
            "Performance Agent": PerformanceAgent(self),
            "Code Review Agent": CodeReviewAgent(self),
            "AI Reviewer Agent": AIReviewerAgent(self),
            # Tier 5: Operations
            "Documentation Agent": DocumentationAgent(self),
            "Git Agent": GitAgent(self),
            "Terminal Agent": TerminalAgent(self),
            "DevOps Agent": DevOpsAgent(self),
            "Release Agent": ReleaseAgent(self),
        }
        agent_names = list(self.agents.keys())
        if len(agent_names) != len(set(agent_names)):
            logger.warning("Duplicate agent mappings detected in orchestrator registry!")

    async def update_task_progress(self, task_id: int, progress: int, session, status: str = None):
        task = next((t for t in self.context.subtasks if t["id"] == task_id), None)
        if task:
            task["progress"] = progress
            if status:
                task["status"] = status
            elif progress == 100:
                task["status"] = "completed"
            else:
                task["status"] = "running"
                
            await session.send_ws_message({
                "type": "task_progress",
                "task_id": task_id,
                "progress": progress,
                "status": task["status"]
            })
            
            # Send standard thinking event for this step
            agent_name = task.get("agent", "Agent")
            desc = task.get("description", "")
            if progress == 100:
                msg = f"✓ Finished {agent_name}"
            else:
                msg = f"Running {agent_name}: {desc} ({progress}%)"
                
            await session.send_ws_message({
                "type": "thinking",
                "content": msg
            })

    async def run_task(self, task_description: str, session) -> str:
        # ── Trivial input guard: don't spin up 23 agents for simple messages ──
        trivial_patterns = [
            r'^\s*(hi|hello|hey|yo|sup|hiya|howdy|thanks|thank you|ty|thx)\s*[!.?]?\s*$',
            r'^\s*(ok|okay|yes|no|sure|cool|got it|alright|great|perfect|nice|good)\s*[!.?]?\s*$',
            r'^\s*what\s+(is|are|does|do)\s+\w[\w\s]{0,40}\??\s*$',
            r'^\s*(explain|describe|tell me about|what is)\s+\w[\w\s]{0,50}\??\s*$',
        ]
        for pattern in trivial_patterns:
            if re.match(pattern, task_description.strip(), re.IGNORECASE):
                await session.send_ws_message({
                    "type": "status",
                    "status": "thinking",
                    "message": "Thinking..."
                })
                response = await session._run_llm_query(
                    ASK_MODE_SYSTEM_PROMPT,
                    task_description,
                    agent_name="Ask"
                )
                await session.send_ws_message({
                    "type": "text_delta",
                    "content": response
                })
                await session.send_ws_message({"type": "session_done"})
                return ""

        await self.context.log("Orchestrator: Initializing dynamic agent router session plan...")
        self.context.subtasks = []
        
        # 1. Run Planner Agent first to plan subtasks
        planner = self.agents["Planner Agent"]
        await planner.execute(task_description, session, task_id=0)
        
        if len(self.context.subtasks) > 1:
            await self.context.log("Orchestrator: Multiple independent subtasks planned. Delegating to LangGraph supervisor...")
            
            from parallel_agent_system.core.state import SubTask as ParallelSubTask, GraphState as ParallelGraphState
            from parallel_agent_system.graph.supervisor import build_supervisor_graph
            from parallel_agent_system.core.config import SystemConfig
            from parallel_agent_system.runtime.secret_registry import SecretRegistry
            import uuid
            
            # Map backend agent names to parallel agent_types (SubTask.agent_type literals)
            def map_agent_name(name: str) -> str:
                name_l = name.lower()
                if "security" in name_l:
                    return "security"
                elif "performance" in name_l:
                    return "performance"
                elif "debug" in name_l:
                    return "debug"
                elif "database" in name_l or "db" in name_l:
                    return "database"
                elif "api" in name_l:
                    return "api"
                elif "integration" in name_l:
                    return "integration"
                elif "devops" in name_l or "docker" in name_l:
                    return "devops"
                elif "release" in name_l:
                    return "release"
                elif "git" in name_l:
                    return "git"
                elif "terminal" in name_l:
                    return "terminal"
                elif "planner" in name_l or "architect" in name_l:
                    return "architect"
                elif "requirement" in name_l:
                    return "requirement"
                elif "test" in name_l:
                    return "test"
                elif "doc" in name_l:
                    return "docs"
                elif "review" in name_l:
                    return "review"
                elif "frontend" in name_l:
                    return "frontend"
                elif "backend" in name_l:
                    return "backend"
                return "code"

            # Map old integer task IDs to new UUID string IDs
            id_map = {}
            for st in self.context.subtasks:
                id_map[st["id"]] = f"task_{uuid.uuid4().hex[:8]}"

            parallel_subtasks = []
            for st in self.context.subtasks:
                new_id = id_map[st["id"]]
                depends_on_list = []
                for dep_id in st.get("dependencies", []):
                    if dep_id in id_map:
                        depends_on_list.append(id_map[dep_id])
                
                p_task = ParallelSubTask(
                    id=new_id,
                    agent_type=map_agent_name(st["agent"]),
                    description=st["description"],
                    workspace_dir=f"./workspace/agent-{new_id[:8]}",
                    depends_on=depends_on_list
                )
                parallel_subtasks.append(p_task)

            # Set up LLM key
            api_key = session.profile.get("api_key") or ""
            SecretRegistry.register("LLM_API_KEY", api_key)
            
            config = SystemConfig()
            graph = build_supervisor_graph(config)
            
            initial_state: ParallelGraphState = {
                "run_id": f"run_{uuid.uuid4().hex[:8]}",
                "goal": task_description,
                "subtasks": parallel_subtasks,
                "results": [],
                "global_cost_usd": 0.0,
                "iteration": 1,
                "status": "pending",
                "human_confirmation_required": False,
                "messages": [],
                "session": session
            }
            
            session.parallel_subtasks = []
            for st in parallel_subtasks:
                session.parallel_subtasks.append({
                    "id": st.id,
                    "agent": st.agent_type.capitalize() + " Agent",
                    "description": st.description,
                    "status": "pending",
                    "progress": 0
                })
                
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": "Orchestrator Agent",
                "active_task": "Starting parallel graph execution...",
                "subtasks": session.parallel_subtasks,
                "collaboration_log": session.collaboration_log
            })
            
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
            final_state = await graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": thread_id}}
            )
            
            # Map results back to orchestrator context
            self.context.subtasks = session.parallel_subtasks
            self.context.collaboration_log = session.collaboration_log
            
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": "Orchestrator",
                "active_task": "All parallel tasks completed",
                "subtasks": self.context.subtasks,
                "collaboration_log": self.context.collaboration_log
            })
            
        else:
            # Fallback to default sequential routing workflow
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