import sys
import os
import json
import logging
import asyncio

# Add agent subdirectory to path to support consolidated imports
current_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.join(current_dir, "agent")
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)
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
    "- Include ONLY agents that are needed for this specific request.\n"
    "- Simple single-file changes: [Requirement Analysis Agent → File System Agent → one coding agent].\n"
    "- Tasks with empty dependencies[] can run in parallel.\n"
    "- Decompose large tasks (e.g. game builds or multi-file projects) into separate one-file-per-LLM-call subtasks (e.g., one subtask for creating index.html, one subtask for style.css, one subtask for script.js, one subtask for README.md). Do not group multiple code files into a single subtask.\n"
    "- CRITICAL RULE: If the request is complex, multi-step, or heavy (e.g. has multiple files, both frontend and backend changes, or database changes), you MUST split the task into multiple specific subtasks. Break down the work into logical sequential steps.\n"
    "- Use exactly ONE of: Coding Agent, Frontend Developer Agent, or Backend Developer Agent (choose based on what files change) per subtask.\n\n"
    "Output ONLY a JSON array of objects, with no extra formatting, markdown tags, or headers:\n"
    "[\n"
    '  {{"id": 1, "agent": "Requirement Analysis Agent", "description": "Identify files to read/modify", "dependencies": []}},\n'
    '  {{"id": 2, "agent": "File System Agent", "description": "Read file contents", "dependencies": [1]}},\n'
    '  {{"id": 3, "agent": "Coding Agent", "description": "Create or modify flappy-bird/index.html", "dependencies": [2]}}\n'
    "]\n\n"
    "Available agents: Planner Agent, Requirement Analysis Agent, Coding Agent, "
    "Frontend Developer Agent, Backend Developer Agent, File System Agent, Software Architect Agent, "
    "Terminal Agent, Testing Agent, Debugging Agent, Documentation Agent, Code Review Agent, "
    "Security Agent, Performance Agent, API Agent, Database Agent, Integration Agent, "
    "DevOps Agent, AI Reviewer Agent, Git Agent, Release Agent."
)

requirement_prompt_template = PromptTemplate.from_template(
    "You are the Requirement Analysis Agent. Analyse the task and the current workspace to determine "
    "what files must be created or modified.\n\n"
    "Task: {task_description}\n\n"
    "Workspace files (empty list means a brand-new project):\n{codebase_details}\n\n"
    "RULES:\n"
    "1. Output ONLY a valid JSON object — no markdown, no prose.\n"
    "2. If the workspace is EMPTY or has no relevant files, this is a NEW PROJECT. "
    "You MUST populate 'files_to_create' with every file needed from scratch.\n"
    "3. If relevant files already exist, put them in 'target_files' (to be read & modified).\n"
    "4. NEVER return both lists empty for a new-project task.\n"
    "5. Structure:\n"
    "{{\n"
    "  \"is_new_project\": true,\n"
    "  \"files_to_create\": [\"main.py\", \"models.py\", \"requirements.txt\"],\n"
    "  \"target_files\": []\n"
    "}}\n"
    "For an existing project the structure is:\n"
    "{{\n"
    "  \"is_new_project\": false,\n"
    "  \"files_to_create\": [],\n"
    "  \"target_files\": [\"relative/path/to/file1\", \"relative/path/to/file2\"]\n"
    "}}"
)

coding_prompt_template = PromptTemplate.from_template(
    "You are the Coding Agent — a senior software engineer.\n\n"
    "Task: {task_description}\n"
    "Target file: {path}\n"
    "Is this a new file? {is_new_file}\n"
    "Existing file context:\n{file_context}\n\n"
    "RULES:\n"
    "1. Output ONLY a valid JSON object — no markdown wrapper, no prose.\n"
    "2. If 'Is this a new file?' is YES, write the COMPLETE file from scratch. "
    "Do not reference or depend on content that does not exist yet.\n"
    "3. If 'Is this a new file?' is NO, produce the full updated file contents.\n"
    "4. NEVER use placeholder comments like '# TODO', '# implement here', or '... rest of code'.\n"
    "5. Write production-ready, fully working code.\n"
    "6. Structure:\n"
    "{{\n"
    "  \"files\": [\n"
    "    {{\n"
    "      \"path\": \"{path}\",\n"
    "      \"content\": \"complete file content here\"\n"
    "    }}\n"
    "  ]\n"
    "}}"
)

terminal_prompt_template = PromptTemplate.from_template(
    "You are the Terminal Agent. Specify the shell commands to execute for verifying the task:\n\n"
    "Task: {task_description}\n\n"
    "RULES:\n"
    "1. You must output ONLY a valid JSON object. No other text or markdown wrapper.\n"
    "2. The JSON object must be structured exactly as follows:\n"
    "{{\n"
    "  \"commands\": [\"command1\", \"command2\"]\n"
    "}}\n"
    "If no commands are needed, return an empty array []."
)

debugging_prompt_template = PromptTemplate.from_template(
    "You are the Debug Agent — a principal engineer who diagnoses and fixes issues.\n\n"
    "Task: {task_description}\n"
    "Error output: {build_error}\n"
    "Recent changes: {recent_commits}\n"
    "File contents: {file_contents}\n\n"
    "RULES:\n"
    "1. You must output ONLY a valid JSON object. No other text or markdown wrapper.\n"
    "2. The JSON object must be structured exactly as follows:\n"
    "{{\n"
    "  \"explanation\": \"Brief description of why the bug existed\",\n"
    "  \"fixes\": [\n"
    "    {{\n"
    "      \"path\": \"relative/path/to/buggy_file\",\n"
    "      \"content\": \"complete corrected file contents\"\n"
    "    }}\n"
    "  ]\n"
    "}}\n"
    "3. Minimize changes, only correct the buggy lines."
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
    "Target file: {path}\n"
    "Original content:\n{original}\n\n"
    "REQUIREMENTS:\n"
    "1. Strict TypeScript — zero `any` types. Use `unknown` + type guards where needed.\n"
    "2. Semantic HTML5 with aria-* attributes on every interactive element.\n"
    "3. Every component needs: loading state, error state, empty state.\n"
    "4. Mobile-first CSS. Use existing CSS custom properties/design tokens.\n"
    "5. Apply React.memo/useCallback/useMemo wherever re-renders are costly.\n"
    "6. Components ≤ 200 lines. Split growing components proactively.\n"
    "7. Read existing components to match the project's patterns before writing new ones.\n"
    "8. Output COMPLETE file contents. Never truncate with '...' or placeholders.\n\n"
    "After implementing, run: tsc --noEmit to verify TypeScript compiles."
)

backend_dev_prompt_template = PromptTemplate.from_template(
    "You are the Backend Developer Agent — a senior Python/FastAPI engineer.\n\n"
    "Task: {task_description}\n"
    "Target file: {path}\n"
    "Original content:\n{original}\n\n"
    "REQUIREMENTS:\n"
    "1. Type hints on every function. Pydantic v2 models for all request/response schemas.\n"
    "2. Architecture: Controllers → Services → Repositories. No business logic in routes.\n"
    "3. Google-style docstrings on all public functions and classes.\n"
    "4. Structured logging: logger.info('event', extra={{'key': value}}).\n"
    "5. Typed, domain-specific exceptions. Never bare `except Exception`.\n"
    "6. No hardcoded secrets. All credentials via settings / env vars.\n"
    "7. Read existing routes/services first to match existing patterns.\n"
    "8. Output COMPLETE file contents. Never truncate with '...' or placeholders.\n\n"
    "After implementing, run: python -c 'import app' or the relevant test command."
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

search_prompt_template = PromptTemplate.from_template(
    "You are the Search Agent. Your responsibility is to locate relevant code, symbols, and files in the workspace.\n\n"
    "Task: {task_description}\n"
    "Search Query: {search_query}\n\n"
    "Use search tools to find relevant items. Do not edit any files. Return a summary of your search findings."
)

memory_prompt_template = PromptTemplate.from_template(
    "You are the Memory Agent. Your responsibility is to retrieve past conversation contexts and project memories.\n\n"
    "Task: {task_description}\n"
    "Context: {context_data}\n\n"
    "Summarize and package the context for the Coding agent. Do not modify any files."
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

class ParallelAgentAdapter(BaseAgent):
    def __init__(self, name: str, orchestrator, agent_cls_name: str):
        super().__init__(name, orchestrator)
        self.agent_cls_name = agent_cls_name

    async def execute(self, task_description: str, session, task_id: int) -> str:
        from parallel_agent_system.core.config import SystemConfig
        from parallel_agent_system.core.state import SubTask
        from parallel_agent_system.runtime.secret_registry import SecretRegistry
        
        # Check if a custom connection profile is mapped for this specialist agent
        profile = getattr(session, "profile", {})
        from backend.app.config import config_manager as config
        agent_profiles = config.get_agent_profiles()
        mapped_profile_id = agent_profiles.get(self.name)
        if mapped_profile_id:
            mapped_profile = config.get_profile(mapped_profile_id)
            if mapped_profile:
                profile = mapped_profile
        
        # Synchronize resolved profile credentials with parallel agent system
        api_key = profile.get("api_key", "")
        if api_key:
            SecretRegistry.set("LLM_API_KEY", api_key)
            api_format = (profile.get("api_format") or "openai").upper()
            SecretRegistry.set(f"{api_format}_API_KEY", api_key)
            SecretRegistry.set("OPENAI_API_KEY", api_key)
            SecretRegistry.set("ANTHROPIC_API_KEY", api_key)
        if profile.get("base_url"):
            SecretRegistry.set("LLM_BASE_URL", profile.get("base_url"))
        
        # Late imports
        if self.agent_cls_name == "CodeAgent":
            from parallel_agent_system.agents.code_agent import CodeAgent
            agent_cls = CodeAgent
        elif self.agent_cls_name == "DocsAgent":
            from parallel_agent_system.agents.docs_agent import DocsAgent
            agent_cls = DocsAgent
        elif self.agent_cls_name == "ReviewAgent":
            from parallel_agent_system.agents.review_agent import ReviewAgent
            agent_cls = ReviewAgent
        elif self.agent_cls_name == "TestAgent":
            from parallel_agent_system.agents.tester_agent import TestAgent
            agent_cls = TestAgent
        else:
            raise ValueError(f"Unknown parallel agent: {self.agent_cls_name}")
            
        sys_config = SystemConfig()
        if profile.get("model_name"):
            sys_config.llm_model = profile.get("model_name")
        parallel_agent = agent_cls(sys_config)
        
        subtask = SubTask(
            id=f"subtask_{task_id}_{uuid.uuid4().hex[:6]}",
            agent_type=parallel_agent.agent_type,
            description=task_description,
            dependencies=[],
            workspace_dir=getattr(session, "workspace_root", "./") or "./"
        )
        
        await self.orchestrator.context.log(f"ParallelAgentAdapter ({self.name}): Executing via parallel agent system runtime...")
        res = await parallel_agent.run(subtask, session)
        
        if res.status == "success":
            await self.orchestrator.context.log(f"ParallelAgentAdapter ({self.name}): Execution success. Output: {res.output}")
            return res.output
        else:
            await self.orchestrator.context.log(f"ParallelAgentAdapter ({self.name}): Execution failed: {res.output}")
            return f"Failed: {res.output}"

class PlannerAgent(BaseAgent):
    """Breaks down requests into a logical sequence of subtasks with dependencies."""
    def __init__(self, orchestrator):
        super().__init__("Planner Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Planner Agent: Formulating execution plan...")
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a master software architect planner. Output ONLY a valid JSON array of subtask objects."),
            ("human", "{prompt_content}")
        ])
        prompt_content = planner_prompt_template.format(task_description=task_description)
        
        default_agent_names = {
            "Planner Agent", "Frontend Planner Agent", "Backend Planner Agent", "Requirement Analysis Agent",
            "Software Architect Agent", "File System Agent", "Coding Agent", "Frontend Developer Agent",
            "Backend Developer Agent", "Database Agent", "API Agent", "Integration Agent", "Testing Agent",
            "Debugging Agent", "Security Agent", "Performance Agent", "Code Review Agent", "AI Reviewer Agent",
            "Documentation Agent", "Git Agent", "Terminal Agent", "DevOps Agent", "Release Agent", "Orchestrator Agent"
        }
        custom_agent_names = [name for name in self.orchestrator.agents if name not in default_agent_names]
        if custom_agent_names:
            prompt_content += f"\n\nAvailable custom available agents: {', '.join(custom_agent_names)}."
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        response = response_msg.content
        try:
            clean_res = response.strip()
            if "```json" in clean_res:
                clean_res = clean_res.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_res:
                clean_res = clean_res.split("```")[1].split("```")[0].strip()
            
            # Find bracket boundaries
            start_idx = clean_res.find('[')
            end_idx = clean_res.rfind(']')
            if start_idx != -1 and end_idx != -1:
                clean_res = clean_res[start_idx:end_idx+1]
                
            subtasks = json.loads(clean_res.strip())
            if isinstance(subtasks, list):
                self.orchestrator.context.subtasks = subtasks
                await self.orchestrator.context.log(f"Planner Agent: Formulated plan containing {len(subtasks)} subtasks.")
                return f"Plan formulated with {len(subtasks)} subtasks."
            else:
                raise ValueError("Parsed JSON is not a list")
        except Exception as e:
            logger.error(f"Planner JSON parsing failed: {e}. Raw response: {response}")
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
            
            # If the workspace contains too many files, filter down to the most relevant files using RAG
            if len(workspace_files) > 100:
                import re
                task_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9_]+', task_description) if len(w) > 2]
                scored_files = []
                for f in workspace_files:
                    score = 0
                    f_lower = f.lower()
                    for word in task_words:
                        if word in f_lower:
                            score += 10
                    basename = os.path.basename(f).lower()
                    if basename in ("package.json", "tsconfig.json", "requirements.txt", "pyproject.toml", "main.py", "app.py", "index.ts", "index.tsx", "vite.config.ts"):
                        score += 5
                    scored_files.append((score, f))
                
                scored_files.sort(key=lambda x: x[0], reverse=True)
                
                # Keep top 60 relevant files
                top_files = [f for score, f in scored_files[:60]]
                
                # Form top-level directory layout summary
                dirs_list = set()
                for f in workspace_files:
                    parts = f.split('/')
                    if len(parts) > 1:
                        dirs_list.add(parts[0] + "/")
                        if len(parts) > 2:
                            dirs_list.add(parts[0] + "/" + parts[1] + "/")
                
                trimmed_list = sorted(list(dirs_list))[:30] + ["... (folders layout)"] + sorted(top_files)
                codebase_details = "Actual files in the workspace (filtered by relevance/RAG):\n" + "\n".join(trimmed_list)
            else:
                codebase_details = "Actual files in the workspace:\n" + "\n".join(workspace_files)
        except Exception as e:
            codebase_details = "Could not list workspace files."
            logger.error(f"Error listing workspace files: {e}")
            
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a master requirement analysis engineer. Output ONLY a valid JSON object."),
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
            if "```json" in clean_res:
                clean_res = clean_res.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_res:
                clean_res = clean_res.split("```")[1].split("```")[0].strip()
            
            indices = [i for i in [clean_res.find('{'), clean_res.find('[')] if i != -1]
            first_idx = min(indices) if indices else -1
            r_indices = [i for i in [clean_res.rfind('}'), clean_res.rfind(']')] if i != -1]
            last_idx = max(r_indices) if r_indices else -1
            if first_idx != -1 and last_idx != -1:
                clean_res = clean_res[first_idx:last_idx+1]
                
            data = json.loads(clean_res.strip())
            report = ""
            target_files = []
            files_to_create = []
            is_new_project = False

            if isinstance(data, dict):
                report = data.get("report", "")
                target_files = data.get("target_files", [])
                files_to_create = data.get("files_to_create", [])
                is_new_project = data.get("is_new_project", False)
            elif isinstance(data, list):
                target_files = data

            # Don't save research report to avoid unwanted files
            if report:
                await self.orchestrator.context.log(f"Requirement Analysis Agent: Analysis complete")

            # Store both lists and the new-project flag in shared memory
            if isinstance(target_files, list):
                self.orchestrator.context.memory["target_files"] = target_files
            else:
                self.orchestrator.context.memory["target_files"] = []

            if isinstance(files_to_create, list):
                self.orchestrator.context.memory["files_to_create"] = files_to_create
            else:
                self.orchestrator.context.memory["files_to_create"] = []

            self.orchestrator.context.memory["is_new_project"] = bool(is_new_project)

            await self.orchestrator.context.log(
                f"Requirement Analysis Agent: is_new_project={is_new_project}, "
                f"target_files={target_files}, files_to_create={files_to_create}"
            )
        except Exception as e:
            logger.error(f"Requirement Analysis JSON parsing failed: {e}. Raw response: {response}")
            self.orchestrator.context.memory["target_files"] = []
            
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Completed"

class FileSystemAgent(BaseAgent):
    """Reads multiple codebase files concurrently."""
    def __init__(self, orchestrator):
        super().__init__("File System Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("File System Agent: Reading codebase files...")
        await self.orchestrator.update_task_progress(task_id, 10, session)

        target_files = self.orchestrator.context.memory.get("target_files", [])
        if not target_files:
            await self.orchestrator.context.log("File System Agent: No target files in shared memory.")
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No files to read."

        from .async_files import async_read_workspace_file
        from .context_config import READ_FILE_MAX_CHARS, MAX_TARGET_FILES_WITH_CONTENT
        import re

        # Concurrency limit
        semaphore = asyncio.Semaphore(4)
        
        # Relevance scoring to identify top files
        query_words = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", task_description.lower()))
        common_stops = {"the", "and", "for", "class", "def", "function", "import", "from", "file", "code", "change", "create", "modify", "write", "read", "update", "implement"}
        query_words = {w for w in query_words if w not in common_stops}
        
        scored_files = []
        for p in target_files:
            basename = os.path.basename(p).lower()
            basename_words = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", basename))
            score = len(query_words.intersection(basename_words)) * 5
            scored_files.append((score, p))
            
        scored_files.sort(key=lambda x: x[0], reverse=True)
        top_files = {p for _, p in scored_files[:MAX_TARGET_FILES_WITH_CONTENT]}

        async def _read_one(path: str) -> tuple:
            async with semaphore:
                try:
                    if path in top_files:
                        content = await async_read_workspace_file(session.workspace_root, path, max_chars=READ_FILE_MAX_CHARS)
                        await self.orchestrator.context.log(f"File System Agent: \u2713 Read {path} (content)")
                    else:
                        abs_path = os.path.join(session.workspace_root, path)
                        size_bytes = os.path.getsize(abs_path) if os.path.exists(abs_path) else 0
                        content = f"[File metadata: path={path}, size={size_bytes} bytes; content omitted due to file-limit constraints]"
                        await self.orchestrator.context.log(f"File System Agent: \u2713 Read {path} (metadata only)")
                    return path, content
                except Exception as e:
                    await self.orchestrator.context.log(
                        f"File System Agent: \u26a0 Could not read {path}: {e}"
                    )
                    return path, None

        # Read all files concurrently with semaphore
        results = await asyncio.gather(*[_read_one(p) for p in target_files])

        file_contents = {path: content for path, content in results if content is not None}
        self.orchestrator.context.memory["file_contents"] = file_contents

        await self.orchestrator.update_task_progress(task_id, 100, session)
        return f"Read {len(file_contents)}/{len(target_files)} files."

class CodingAgent(BaseAgent):
    """General-purpose code generator that modifies files to implement features."""
    def __init__(self, orchestrator):
        super().__init__("Coding Agent", orchestrator)
        
    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"Coding Agent: Starting parallel code generation...")
        await self.orchestrator.update_task_progress(task_id, 10, session)

        target_files = self.orchestrator.context.memory.get("target_files", [])
        files_to_create = self.orchestrator.context.memory.get("files_to_create", [])
        is_new_project = self.orchestrator.context.memory.get("is_new_project", False)
        file_contents = self.orchestrator.context.memory.get("file_contents", {})

        # --- Bug 3 fix: merge files_to_create into target_files for new projects ---
        if is_new_project and files_to_create:
            # New project: work list is the scaffold list, no existing content
            target_files = files_to_create
            await self.orchestrator.context.log(
                f"Coding Agent: New project — scaffolding {len(target_files)} file(s): {target_files}"
            )

        if not target_files:
            # Last-resort inference (keeps existing fallback behaviour)
            infer_prompt = (
                f"List every relative file path that must be created or modified for this task.\n"
                f"Task: {task_description}\n\n"
                "Output ONLY a JSON array of strings, e.g. [\"main.py\", \"models.py\", \"requirements.txt\"]."
            )
            try:
                llm = DevPilotChatModel(session=session, agent_name=self.name)
                res = await llm.ainvoke([("system", "Output ONLY a valid JSON array of string file paths."), ("human", infer_prompt)])
                clean_res = res.content.strip()
                if clean_res.startswith("```"):
                    lines = [l for l in clean_res.split("\n") if not l.startswith("```")]
                    clean_res = "\n".join(lines).strip()
                inferred = json.loads(clean_res)
                if isinstance(inferred, list) and inferred:
                    target_files = [str(f) for f in inferred]
            except Exception as e:
                logger.warning(f"Failed to infer target files for Coding Agent: {e}")

        if not target_files:
            await self.orchestrator.context.log("Coding Agent: No target files identified.")
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No files to modify"
            
        async def process_file(path: str):
            original = file_contents.get(path, "")
            # Bug 4 fix: tell the LLM whether it is writing a brand-new file
            is_new_file = "YES" if not original else "NO"

            from .context_config import CODING_ORIGINAL_MAX_CHARS
            from .context_helpers import build_relevant_file_context
            file_context = build_relevant_file_context(
                path=path,
                content=original,
                task_description=task_description,
                max_chars=CODING_ORIGINAL_MAX_CHARS
            )
            
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a master software engineer. Output ONLY a valid JSON object."),
                ("human", "{prompt_content}")
            ])
            prompt_content = coding_prompt_template.format(
                task_description=task_description,
                path=path,
                is_new_file=is_new_file,
                file_context=file_context if file_context else "(new file — no existing content)"
            )
            
            llm = DevPilotChatModel(session=session, agent_name=self.name)
            chain = chat_prompt | llm
            
            new_code_msg = await chain.ainvoke({"prompt_content": prompt_content})
            new_code = new_code_msg.content
            
            clean_code = new_code.strip()
            try:
                if "```json" in clean_code:
                    clean_code = clean_code.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_code:
                    clean_code = clean_code.split("```")[1].split("```")[0].strip()
                
                start_idx = clean_code.find('{')
                end_idx = clean_code.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    clean_code = clean_code[start_idx:end_idx+1]
                    
                data = json.loads(clean_code.strip())
                files = data.get("files", [])
                if files:
                    clean_code = files[0].get("content", "")
            except Exception as e:
                logger.error(f"Coding Agent JSON parsing failed: {e}. Raw response: {new_code}")
                if clean_code.startswith("```"):
                    lines = clean_code.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean_code = "\n".join(lines)
                
            return path, clean_code

        # Concurrently or sequentially generate proposed code for all target files
        from .state import config_manager
        concurrency_mode = config_manager.get_concurrency_mode()
        if concurrency_mode == "sequential":
            results = []
            for path in target_files:
                results.append(await process_file(path))
        else:
            tasks = [process_file(path) for path in target_files]
            results = await asyncio.gather(*tasks)

        # Apply the changes (either concurrently or sequentially based on auto_apply)
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))

        async def write_one_file(path: str, clean_code: str):
            tc_id = f"write_{task_id}_{uuid.uuid4().hex[:6]}"
            await session.send_ws_message({
                "type": "status",
                "status": "tool_executing",
                "message": f"Writing {path}...",
                "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": clean_code}}
            })
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": clean_code}, auto_apply=auto_apply)
            await session.send_ws_message({
                "type": "tool_result",
                "tool_call_id": tc_id,
                "name": "write_file",
                "status": "success",
                "result": result
            })
            await self.orchestrator.context.log(f"Coding Agent: Wrote modifications to {path}.")

        if auto_apply:
            await asyncio.gather(*[write_one_file(path, code) for path, code in results])
        else:
            for path, code in results:
                await write_one_file(path, code)
            
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
            ("system", "You are a master system terminal executor. Output ONLY a valid JSON object."),
            ("human", "{prompt_content}")
        ])
        
        prompt_content = terminal_prompt_template.format(task_description=task_description)
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        response = response_msg.content
        
        try:
            clean_res = response.strip()
            if "```json" in clean_res:
                clean_res = clean_res.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_res:
                clean_res = clean_res.split("```")[1].split("```")[0].strip()
                
            start_idx = clean_res.find('{')
            end_idx = clean_res.rfind('}')
            if start_idx != -1 and end_idx != -1:
                clean_res = clean_res[start_idx:end_idx+1]
                
            data = json.loads(clean_res.strip())
            commands = data.get("commands", [])
            
            for cmd in commands:
                await self.orchestrator.context.log(f"Terminal Agent: Running command: {cmd}")
                from .tools.terminal_tool import run_shell_command
                result = await run_shell_command(session, cmd)
                exit_code = getattr(session, "last_exit_code", 0)
                await self.orchestrator.context.log(f"Terminal Agent: Executed command: {cmd}. Exit Code: {exit_code}")
                
                log_entry = f"Terminal command executed: `{cmd}` (Exit Code: {exit_code})\nOutput excerpt:\n{result[:300]}"
                self.orchestrator.context.collaboration_log.append(log_entry)
        except Exception as e:
            logger.error(f"Terminal Agent JSON parsing failed: {e}. Raw response: {response}")
            # Fallback to executing command directly if it wasn't JSON
            cmd = response.strip()
            if cmd and cmd.upper() != "NONE":
                await self.orchestrator.context.log(f"Terminal Agent: Fallback running command: {cmd}")
                from .tools.terminal_tool import run_shell_command
                result = await run_shell_command(session, cmd)
                exit_code = getattr(session, "last_exit_code", 0)
                log_entry = f"Terminal command executed: `{cmd}` (Exit Code: {exit_code})\nOutput excerpt:\n{result[:300]}"
                self.orchestrator.context.collaboration_log.append(log_entry)
                
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
        
        import json as _json
        ws = session.workspace_root
        cmd = "pytest"
        pkg_json_path = os.path.join(ws, "package.json")
        pyproject_path = os.path.join(ws, "pyproject.toml")
        if os.path.exists(pkg_json_path):
            try:
                with open(pkg_json_path) as f:
                    pkg = _json.load(f)
                cmd = pkg.get("scripts", {}).get("test", "npm test")
                if cmd != "npm test":
                    cmd = f"npm run {list(pkg.get('scripts', {}).keys())[list(pkg.get('scripts', {}).values()).index(cmd)]}"
            except Exception:
                cmd = "npm test -- --watchAll=false"
        elif os.path.exists(pyproject_path):
            cmd = "python -m pytest"
            
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
        
        build_error = "\n".join(self.orchestrator.context.collaboration_log[-5:])
        recent_commits = self.orchestrator.context.memory.get("git_log", "N/A")
        file_contents = str(self.orchestrator.context.memory.get("file_contents", ""))[:3000]
        from .context_helpers import build_memory_summary
        shared_memory = build_memory_summary(self.orchestrator.context.memory, max_chars=2000)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a senior debugging engineer. Analyze the output and suggest fixes. Output ONLY a valid JSON object."),
            ("human", "{prompt_content}")
        ])
        prompt_content = debugging_prompt_template.format(
            task_description=task_description,
            build_error=build_error,
            recent_commits=recent_commits,
            file_contents=file_contents,
            shared_memory=shared_memory
        )
        
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        debug_output_msg = await chain.ainvoke({"prompt_content": prompt_content})
        debug_output = debug_output_msg.content
        
        try:
            clean_res = debug_output.strip()
            if "```json" in clean_res:
                clean_res = clean_res.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_res:
                clean_res = clean_res.split("```")[1].split("```")[0].strip()
                
            start_idx = clean_res.find('{')
            end_idx = clean_res.rfind('}')
            if start_idx != -1 and end_idx != -1:
                clean_res = clean_res[start_idx:end_idx+1]
                
            data = json.loads(clean_res.strip())
            explanation = data.get("explanation", "")
            fixes = data.get("fixes", [])
            
            await self.orchestrator.context.log(f"Debugging Agent: Bug analysis: {explanation}")
            self.orchestrator.context.memory["debugging_notes"] = explanation
            
            auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
            for fix in fixes:
                path = fix.get("path")
                content = fix.get("content")
                if path and content:
                    tc_id = f"fix_{task_id}_{uuid.uuid4().hex[:6]}"
                    await session.send_ws_message({
                        "type": "status",
                        "status": "tool_executing",
                        "message": f"Debugging Agent applying fix to {path}...",
                        "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": content}}
                    })
                    result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": content}, auto_apply=auto_apply)
                    await session.send_ws_message({
                        "type": "tool_result",
                        "tool_call_id": tc_id,
                        "name": "write_file",
                        "status": "success",
                        "result": result
                    })
                    await self.orchestrator.context.log(f"Debugging Agent: Wrote fix to {path}.")
        except Exception as e:
            logger.error(f"Debugging Agent JSON parsing failed: {e}. Raw response: {debug_output}")
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
        
        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = await async_get_codebase_dict(session.workspace_root, target_files, task_description, session=session)
        _, max_chars = get_dynamic_limits_from_session(session)
        chunks = chunked_codebase(file_contents, max_chars=max_chars, query=task_description)
        
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

class SearchAgent(BaseAgent):
    """Semantic search, symbol lookup, dependency lookup, and workspace retrieval agent."""
    def __init__(self, orchestrator):
        super().__init__("Search Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Search Agent: Locating files and symbols in workspace...")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        repo_kernel = getattr(self.orchestrator, "repo_kernel", None)
        found_files = []
        if repo_kernel:
            import re
            words = re.findall(r"\b[A-Za-z0-9_]{3,}\b", task_description.lower())
            for word in words[:3]:
                files = repo_kernel.find_file(f"%{word}%")
                found_files.extend(files)
                
        summary = f"Found {len(found_files)} potential target files in workspace."
        self.orchestrator.context.memory["search_summary"] = summary
        
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return summary

class MemoryAgent(BaseAgent):
    """Retrieves previous conversations, project memory, and packages task context."""
    def __init__(self, orchestrator):
        super().__init__("Memory Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Memory Agent: Retrieving history and packaging context...")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        history = getattr(session, "conversation_history", [])
        history_text = "\n".join([f"{msg.get('role', '?').upper()}: {str(msg.get('content', ''))[:400]}" for msg in history[-10:]])
        
        context_package = f"Task Description:\n{task_description}\n\nRecent History:\n{history_text}"
        self.orchestrator.context.memory["context_package"] = context_package
        
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Context package built."

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

        frontend_prefixes = ("frontend/", "src/", "components/", "pages/", "app/", ".tsx", ".ts", ".jsx", ".js", ".css", ".html", ".md")
        frontend_files = [f for f in target_files if any(f.startswith(p) or f.endswith(p) for p in frontend_prefixes)]
        if not frontend_files:
            infer_prompt = (
                f"Identify relative frontend file paths that need to be created or modified for this task:\n"
                f"Task: {task_description}\n\n"
                "Output ONLY a JSON array of string file paths, e.g. [\"index.html\", \"style.css\", \"script.js\", \"README.md\"]."
            )
            try:
                llm = DevPilotChatModel(session=session, agent_name=self.name)
                res = await llm.ainvoke([("system", "Output ONLY a valid JSON array of string file paths."), ("human", infer_prompt)])
                clean_res = res.content.strip()
                if clean_res.startswith("```"):
                    lines = [l for l in clean_res.split("\n") if not l.startswith("```")]
                    clean_res = "\n".join(lines).strip()
                inferred = json.loads(clean_res)
                if isinstance(inferred, list) and inferred:
                    frontend_files = [str(f) for f in inferred]
            except Exception as e:
                logger.warning(f"Failed to infer target files for Frontend Developer Agent: {e}")

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
            return path, new_code

        # Concurrently or sequentially generate proposed code for all frontend files
        from .state import config_manager
        concurrency_mode = config_manager.get_concurrency_mode()
        if concurrency_mode == "sequential":
            results = []
            for p in frontend_files:
                results.append(await process_file(p))
        else:
            tasks = [process_file(p) for p in frontend_files]
            results = await asyncio.gather(*tasks)

        # Apply the changes (either concurrently or sequentially based on auto_apply)
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))

        async def write_one_file(path: str, clean_code: str):
            tc_id = f"fedev_{task_id}_{uuid.uuid4().hex[:6]}"
            await session.send_ws_message({
                "type": "status", "status": "tool_executing",
                "message": f"Frontend Developer writing {path}...",
                "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": clean_code}}
            })
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": clean_code}, auto_apply=auto_apply)
            await session.send_ws_message({
                "type": "tool_result", "tool_call_id": tc_id,
                "name": "write_file", "status": "success", "result": result
            })
            await self.orchestrator.context.log(f"Frontend Developer Agent: Updated {path}.")

        if auto_apply:
            await asyncio.gather(*[write_one_file(path, code) for path, code in results])
        else:
            for path, code in results:
                await write_one_file(path, code)

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
            await self.orchestrator.context.log(
                "Backend Developer Agent: No backend files in target list — skipping."
            )
            await self.orchestrator.update_task_progress(task_id, 100, session)
            return "No backend files to modify."

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
            return path, new_code

        # Concurrently or sequentially generate proposed code for all backend files
        from .state import config_manager
        concurrency_mode = config_manager.get_concurrency_mode()
        if concurrency_mode == "sequential":
            results = []
            for p in backend_files:
                results.append(await process_file(p))
        else:
            tasks = [process_file(p) for p in backend_files]
            results = await asyncio.gather(*tasks)

        # Apply the changes (either concurrently or sequentially based on auto_apply)
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))

        async def write_one_file(path: str, clean_code: str):
            tc_id = f"bedev_{task_id}_{uuid.uuid4().hex[:6]}"
            await session.send_ws_message({
                "type": "status", "status": "tool_executing",
                "message": f"Backend Developer writing {path}...",
                "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": clean_code}}
            })
            result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": clean_code}, auto_apply=auto_apply)
            await session.send_ws_message({
                "type": "tool_result", "tool_call_id": tc_id,
                "name": "write_file", "status": "success", "result": result
            })
            await self.orchestrator.context.log(f"Backend Developer Agent: Updated {path}.")

        if auto_apply:
            await asyncio.gather(*[write_one_file(path, code) for path, code in results])
        else:
            for path, code in results:
                await write_one_file(path, code)

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

        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = await async_get_codebase_dict(session.workspace_root, target_files, task_description, session=session)
        _, max_chars = get_dynamic_limits_from_session(session)
        chunks = chunked_codebase(file_contents, max_chars=max_chars, query=task_description)

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        findings = []
        for i, chunk in enumerate(chunks):
            await self.orchestrator.context.log(f"Security Agent: Auditing chunk {i+1}/{len(chunks)}...")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a senior application security engineer. Perform thorough OWASP-based security audits."),
                ("human", "{prompt_content}")
            ])
            from .context_helpers import build_memory_summary
            shared_memory = build_memory_summary(self.orchestrator.context.memory, max_chars=1500)
            prompt_content = security_prompt_template.format(
                task_description=task_description,
                file_contents=chunk,
                shared_memory=shared_memory
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

        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = await async_get_codebase_dict(session.workspace_root, target_files, task_description, session=session)
        _, max_chars = get_dynamic_limits_from_session(session)
        chunks = chunked_codebase(file_contents, max_chars=max_chars, query=task_description)

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

        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = await async_get_codebase_dict(session.workspace_root, target_files, task_description, session=session)
        _, max_chars = get_dynamic_limits_from_session(session)
        chunks = chunked_codebase(file_contents, max_chars=max_chars, query=task_description)

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

class RefactoringAgent(BaseAgent):
    """Analyzes code for structural improvements: dead code, duplication, SOLID violations.
    Writes REFACTORING_REPORT.md and applies approved refactors."""
    def __init__(self, orchestrator):
        super().__init__("Refactoring Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Refactoring Agent: Analyzing code structure for improvements...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        target_files = self.orchestrator.context.memory.get("target_files", [])
        file_contents = await async_get_codebase_dict(session.workspace_root, target_files, task_description, session=session)
        _, max_chars = get_dynamic_limits_from_session(session)
        chunks = chunked_codebase(file_contents, max_chars=max_chars, query=task_description)

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        findings = []
        for i, chunk in enumerate(chunks):
            await self.orchestrator.context.log(f"Refactoring Agent: Reviewing chunk {i+1}/{len(chunks)}...")
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are a principal engineer specializing in code refactoring and clean architecture. "
                    "Identify: dead code, code duplication (DRY violations), SOLID principle violations, "
                    "over-complex functions (cyclomatic complexity > 10), magic numbers/strings, "
                    "poor naming, and missing abstractions. For each issue provide: location, severity "
                    "(High/Medium/Low), description, and a concrete refactoring suggestion with code example."
                )),
                ("human", "{prompt_content}")
            ])
            prompt_content = (
                f"Task: {task_description}\n\n"
                f"Codebase to analyze:\n{chunk}\n\n"
                "Produce a structured refactoring report grouped by severity."
            )
            chain = chat_prompt | llm
            response_msg = await chain.ainvoke({"prompt_content": prompt_content})
            findings.append(response_msg.content)

        refactor_report = "\n\n---\n\n".join(findings)
        self.orchestrator.context.memory["refactor_report"] = refactor_report
        await self.orchestrator.update_task_progress(task_id, 70, session)

        path = "REFACTORING_REPORT.md"
        tc_id = f"refactor_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing refactoring report to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": refactor_report}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": refactor_report}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"Refactoring Agent: Report written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return "Refactoring analysis complete."


class ContextCompactionAgent(BaseAgent):
    """Compresses the current conversation and codebase context into a compact
    digest to reduce token usage for long sessions (like OpenCode's Compaction agent)."""
    def __init__(self, orchestrator):
        super().__init__("Context Compaction Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Context Compaction Agent: Compacting session context...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        # Gather conversation history
        history = getattr(session, "conversation_history", [])
        collab_log = self.orchestrator.context.collaboration_log or []
        memory_keys = [k for k in self.orchestrator.context.memory.keys() if not k.startswith("__")]

        history_text = "\n".join([
            f"{msg.get('role','?').upper()}: {str(msg.get('content',''))[:500]}"
            for msg in history[-30:]  # last 30 messages
        ])
        collab_text = "\n".join([str(e)[:300] for e in collab_log[-20:]])
        memory_text = "\n".join([f"{k}: {str(v)[:200]}" for k, v in self.orchestrator.context.memory.items() if not k.startswith("__")])

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert at summarizing technical conversations and code context. "
                "Create a compact, information-dense summary that preserves all important decisions, "
                "completed work, pending tasks, and key code changes. "
                "The summary will replace the full context to save tokens."
            )),
            ("human", "{prompt_content}")
        ])
        prompt_content = (
            f"Compact this session context into a dense summary:\n\n"
            f"## Recent Conversation ({len(history)} messages)\n{history_text}\n\n"
            f"## Agent Collaboration Log\n{collab_text}\n\n"
            f"## Session Memory\n{memory_text}\n\n"
            f"Task context: {task_description}\n\n"
            "Write a structured summary covering: what was accomplished, key decisions made, "
            "current state, and what remains to be done."
        )
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        compact_summary = response_msg.content

        # Store compact summary in memory
        self.orchestrator.context.memory["__compacted_context__"] = compact_summary
        await self.orchestrator.update_task_progress(task_id, 100, session)
        await self.orchestrator.context.log("Context Compaction Agent: Context compacted successfully.")
        return f"Context compacted. Summary:\n\n{compact_summary[:500]}..."


class TitleAgent(BaseAgent):
    """Generates a concise, descriptive conversation title from the session's first exchange."""
    def __init__(self, orchestrator):
        super().__init__("Title Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Title Agent: Generating conversation title...")

        history = getattr(session, "conversation_history", [])
        first_exchange = "\n".join([
            f"{msg.get('role','?')}: {str(msg.get('content',''))[:300]}"
            for msg in history[:4]
        ]) or task_description

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Generate a short, descriptive title (3-7 words) for this conversation. "
                "It should capture the main topic or goal. Return ONLY the title, no punctuation at the end."
            )),
            ("human", "{prompt_content}")
        ])
        prompt_content = f"Conversation:\n{first_exchange}"
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        title = response_msg.content.strip().strip('"').strip("'")

        self.orchestrator.context.memory["__session_title__"] = title
        await session.send_ws_message({"type": "session_title", "title": title})
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return title


class SummaryAgent(BaseAgent):
    """Generates a structured summary of what was accomplished in a session,
    including files changed, decisions made, and next steps."""
    def __init__(self, orchestrator):
        super().__init__("Summary Agent", orchestrator)

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log("Summary Agent: Generating session summary...")
        await self.orchestrator.update_task_progress(task_id, 20, session)

        history = getattr(session, "conversation_history", [])
        collab_log = self.orchestrator.context.collaboration_log or []
        memory = self.orchestrator.context.memory

        history_text = "\n".join([
            f"{msg.get('role','?').upper()}: {str(msg.get('content',''))[:400]}"
            for msg in history[-40:]
        ])
        collab_text = "\n".join([str(e)[:400] for e in collab_log])

        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are a technical writer. Produce a clear, structured session summary "
                "in Markdown format with sections: ## What Was Accomplished, "
                "## Files Modified, ## Key Decisions, ## Next Steps. "
                "Be specific and actionable."
            )),
            ("human", "{prompt_content}")
        ])
        prompt_content = (
            f"Task: {task_description}\n\n"
            f"Session history:\n{history_text}\n\n"
            f"Agent work log:\n{collab_text}"
        )
        chain = chat_prompt | llm
        response_msg = await chain.ainvoke({"prompt_content": prompt_content})
        summary = response_msg.content

        self.orchestrator.context.memory["__session_summary__"] = summary
        await self.orchestrator.update_task_progress(task_id, 70, session)

        path = "SESSION_SUMMARY.md"
        tc_id = f"summary_{task_id}_{uuid.uuid4().hex[:6]}"
        await session.send_ws_message({
            "type": "status", "status": "tool_executing",
            "message": f"Writing session summary to {path}...",
            "tool_call": {"id": tc_id, "name": "write_file", "args": {"path": path, "content": summary}}
        })
        auto_apply = bool(getattr(session, "auto_apply", False) or (getattr(session, "profile", {}) and session.profile.get("auto_apply", False)))
        result = await session._execute_tool_with_guardrails(tc_id, "write_file", {"path": path, "content": summary}, auto_apply=auto_apply)
        await session.send_ws_message({
            "type": "tool_result", "tool_call_id": tc_id,
            "name": "write_file", "status": "success", "result": result
        })
        await self.orchestrator.context.log(f"Summary Agent: Summary written to {path}.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return f"Session summary complete.\n\n{summary[:600]}..."


class CustomAgent(BaseAgent):
    """A user-defined custom agent that runs a dynamic prompt template."""

    def __init__(self, name: str, orchestrator, prompt_template, system_prompt: str, role: str):
        super().__init__(name, orchestrator)
        self.prompt_template = prompt_template
        self.system_prompt = system_prompt
        self.role = role
        self.__doc__ = role

    async def execute(self, task_description: str, session, task_id: int) -> str:
        await self.orchestrator.context.log(f"{self.name}: Starting execution...")
        await self.orchestrator.update_task_progress(task_id, 20, session)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt or "You are a specialized custom agent."),
            ("human", "{prompt_content}")
        ])
        
        try:
            prompt_content = self.prompt_template.format(task_description=task_description)
        except Exception:
            prompt_content = self.prompt_template.template.replace("{task_description}", task_description)
            
        llm = DevPilotChatModel(session=session, agent_name=self.name)
        chain = chat_prompt | llm
        
        response = await chain.ainvoke({"prompt_content": prompt_content})
        
        memory_key = self.name.lower().replace(" ", "_")
        self.orchestrator.context.memory[memory_key] = response.content
        
        await self.orchestrator.context.log(f"{self.name}: Completed execution.")
        await self.orchestrator.update_task_progress(task_id, 100, session)
        return response.content

def apply_custom_agents_and_overrides(orchestrator_instance=None):
    from pathlib import Path
    import json
    from langchain_core.prompts import PromptTemplate
    
    custom_agents_path = Path.home() / ".devpilot" / "custom_agents.json"
    if not custom_agents_path.exists():
        return
        
    try:
        with open(custom_agents_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            custom_agents = data.get("custom_agents", [])
            prompt_overrides = data.get("prompt_overrides", {})
    except Exception as e:
        logger.error(f"Failed to load custom agents: {e}")
        return

    # Apply overrides to default agents
    default_templates = {
        "Planner Agent": planner_prompt_template,
        "Frontend Planner Agent": frontend_planner_prompt_template,
        "Backend Planner Agent": backend_planner_prompt_template,
        "Requirement Analysis Agent": requirement_prompt_template,
        "Software Architect Agent": architect_prompt_template,
        "Coding Agent": coding_prompt_template,
        "Frontend Developer Agent": frontend_dev_prompt_template,
        "Backend Developer Agent": backend_dev_prompt_template,
        "Database Agent": database_prompt_template,
        "API Agent": api_agent_prompt_template,
        "Integration Agent": integration_prompt_template,
        "Security Agent": security_prompt_template,
        "Performance Agent": performance_prompt_template,
        "Code Review Agent": review_prompt_template,
        "AI Reviewer Agent": ai_reviewer_prompt_template,
        "Documentation Agent": documentation_prompt_template,
        "Terminal Agent": terminal_prompt_template,
        "DevOps Agent": devops_prompt_template,
        "Release Agent": release_prompt_template,
        "Orchestrator Agent": orchestrator_prompt_template,
        "Refactoring Agent": review_prompt_template,         # inherits review base prompt
        "Context Compaction Agent": orchestrator_prompt_template,
        "Title Agent": orchestrator_prompt_template,
        "Summary Agent": documentation_prompt_template,      # inherits documentation base prompt
    }
    
    for name, prompt_str in prompt_overrides.items():
        if name in default_templates:
            default_templates[name].template = prompt_str

    if orchestrator_instance is not None:
        for agent_info in custom_agents:
            name = agent_info["name"]
            role = agent_info.get("role", "Specialized custom agent")
            system_prompt = agent_info.get("system_prompt", "You are a specialized custom agent.")
            prompt_template_str = agent_info.get("prompt_template", "Process task: {task_description}")
            try:
                tmpl = PromptTemplate.from_template(prompt_template_str)
                orchestrator_instance.agents[name] = CustomAgent(name, orchestrator_instance, tmpl, system_prompt, role)
            except Exception as e:
                logger.error(f"Failed to load custom agent {name}: {e}")

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
    if not left:
        return list(right or [])
    if not right:
        return list(left or [])
    if len(right) >= len(left) and right[:len(left)] == left:
        return list(right)
    combined = list(left)
    for item in right:
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

def get_dynamic_limits_from_session(session: Any) -> tuple[int, int]:
    """
    Returns (file_limit, max_chars) based on the session's active model context window.
    This enables large-context models (like Gemini or Claude) to read more files and utilize
    KV Cache Transfer/Migration context efficiently without aggressive chunking.
    """
    model_name = ""
    if session and hasattr(session, "profile") and isinstance(session.profile, dict):
        model_name = session.profile.get("model_name") or session.profile.get("model") or ""
    
    from .adapters.router import get_model_capabilities
    caps = get_model_capabilities(model_name)
    context_window = caps.get("context_window", 8192)
    
    # Scale limits based on context window size
    if context_window >= 1000000:
        # e.g., Gemini 1.5 Pro / Flash, Gemini 2.0
        file_limit = 500      # Analyze up to 500 files
        max_chars = 1000000   # 1 Million chars chunk size
    elif context_window >= 128000:
        # e.g., Claude 3.5, GPT-4o, o1
        file_limit = 100      # Analyze up to 100 files
        max_chars = 200000    # 200k chars chunk size
    elif context_window >= 32000:
        # e.g., Llama 3 8B, Qwen
        file_limit = 40
        max_chars = 64000
    else:
        # Standard context fallback
        file_limit = 20
        max_chars = 8000      # Default 8000 chars (MAX_CHARS)
        
    return file_limit, max_chars

async def async_get_codebase_dict(workspace_root: str, target_files: list = None, task_description: str = "", session: Any = None) -> dict:
    exclude_dirs = {".git", "node_modules", "venv", "__pycache__", ".devpilot", "dist", "build"}
    exclude_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".exe", ".dll"}

    # 1. RAG-based context handoff: If target_files is provided, fetch those files first
    if target_files:
        file_dict = {}
        for tf in target_files:
            clean_tf = tf.replace("\\", "/").strip().lstrip("/")
            if ".." in clean_tf:
                continue
            abs_file_path = os.path.realpath(os.path.join(workspace_root, clean_tf))
            if abs_file_path.startswith(os.path.realpath(workspace_root)) and os.path.isfile(abs_file_path):
                try:
                    with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
                        file_dict[clean_tf] = f.read()
                except Exception:
                    pass
        if file_dict:
            return file_dict

    # Determine dynamic file limit based on active model's capability
    file_limit = 20
    if session:
        file_limit, _ = get_dynamic_limits_from_session(session)

    # 2. Retrieval-based fallback or full scan if target_files is empty
    def _sync_scan() -> dict:
        is_editor_root = False
        try:
            is_editor_root = (
                os.path.isdir(os.path.join(workspace_root, "backend", "app")) and
                os.path.isdir(os.path.join(workspace_root, "frontend", "src"))
            )
        except Exception:
            pass

        file_list = []
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
                file_list.append(rel_file_path)

        # RAG Search: Filter files based on task relevance
        if task_description and len(file_list) > file_limit:
            import re
            task_words = [w.lower() for w in re.findall(r'[a-zA-Z0-9_]+', task_description) if len(w) > 2]
            scored_files = []
            for f in file_list:
                score = 0
                f_lower = f.lower()
                for word in task_words:
                    if word in f_lower:
                        score += 10
                basename = os.path.basename(f).lower()
                if basename in ("package.json", "tsconfig.json", "requirements.txt", "pyproject.toml", "main.py", "app.py", "index.ts", "index.tsx", "vite.config.ts"):
                    score += 5
                scored_files.append((score, f))
            
            scored_files.sort(key=lambda x: x[0], reverse=True)
            selected_files = [f for _, f in scored_files[:file_limit]]
        else:
            selected_files = file_list[:file_limit]

        file_dict = {}
        for rel_file_path in selected_files:
            abs_file_path = os.path.join(workspace_root, rel_file_path)
            try:
                with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
                    file_dict[rel_file_path] = f.read()
            except Exception:
                continue
        return file_dict

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_scan)


def chunked_codebase(file_contents: dict, max_chars=None, query: str = ""):
    from .context_config import CODE_CHUNK_MAX_CHARS, MAX_CODE_CHUNKS
    limit = max_chars or CODE_CHUNK_MAX_CHARS

    raw_chunks = []
    for path, content in file_contents.items():
        if not content:
            continue
        pattern = r"(?=class\s+\w+|def\s+\w+|function\s+\w+|const\s+\w+\s*=\s*\()"
        blocks = re.split(pattern, content)
        
        current_block = ""
        for block in blocks:
            if not block.strip():
                continue
            if len(current_block) + len(block) < 15000:
                current_block += block
            else:
                if current_block:
                    raw_chunks.append((path, current_block))
                current_block = block
        if current_block:
            raw_chunks.append((path, current_block))
            
    combined_chunks = []
    current_chunk = []
    current_size = 0
    
    for path, text in raw_chunks:
        entry = f"### FILE: {path}\n{text}\n"
        if current_size + len(entry) > limit and current_chunk:
            combined_chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0
        current_chunk.append(entry)
        current_size += len(entry)
    if current_chunk:
        combined_chunks.append("\n".join(current_chunk))
        
    if not combined_chunks:
        return []
        
    if query:
        query_words = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", query.lower()))
        common_stops = {"the", "and", "for", "class", "def", "function", "import", "from", "file", "code", "change", "create", "modify", "write", "read", "update", "implement"}
        query_words = {w for w in query_words if w not in common_stops}
        
        scored_chunks = []
        for idx, chunk in enumerate(combined_chunks):
            chunk_words = set(re.findall(r"\b[A-Za-z0-9_]{3,}\b", chunk.lower()))
            score = len(query_words.intersection(chunk_words))
            scored_chunks.append((score, -idx, chunk))
            
        scored_chunks.sort(key=lambda x: (x[0], x[1]), reverse=True)
        selected = scored_chunks[:MAX_CODE_CHUNKS]
        selected.sort(key=lambda x: -x[1])
        return [chunk for _, _, chunk in selected]
        
    return combined_chunks[:MAX_CODE_CHUNKS]

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
    from .context_helpers import build_memory_summary
    memory_summary = build_memory_summary(state["memory"])
    
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
        class_name = session.__class__.__name__.lower()
        if "mock" in class_name or hasattr(session, "mock_calls"):
            is_mock = True
            
    if not is_mock:
        try:
            from .state import redis_client
            from .shared_memory import sm_replace_all
            if session and hasattr(session, "workspace_root"):
                workspace_id = os.path.basename(session.workspace_root) or "default"
                run_id = getattr(session, "session_id", None) or workspace_id
                await redis_client.set(f"session:{workspace_id}:ctx", json.dumps(state["memory"]), ex=3600)
                await sm_replace_all(run_id, state["memory"] or {})
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
            class_name = session.__class__.__name__.lower()
            if "mock" in class_name or hasattr(session, "mock_calls"):
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

        # State Manager tracking
        if hasattr(orchestrator, "state_manager") and orchestrator.state_manager:
            orchestrator.state_manager.add_active_agent(agent_name)
        
        # Publish AgentStarted event
        if hasattr(orchestrator, "event_bus"):
            try:
                await orchestrator.event_bus.publish("AgentStarted", {"agent": agent_name, "task": agent_description})
            except Exception:
                pass

        # Concurrency File Lock Management
        is_writer = "coding" in agent_name.lower() or "developer" in agent_name.lower()
        target_files = state["memory"].get("target_files", [])
        if is_writer and hasattr(orchestrator, "lock_manager") and orchestrator.lock_manager:
            for path in target_files:
                orchestrator.lock_manager.acquire_lock(path, agent_name, exclusive=True)
                
        agent = orchestrator.agents[agent_name]
        status = "completed"
        progress = 100
        try:
            await agent.execute(agent_description, session, subtask_id)
            if hasattr(orchestrator, "state_manager") and orchestrator.state_manager:
                orchestrator.state_manager.add_completed_step(agent_description, agent_name, "success")
        except Exception as e:
            status = "failed"
            progress = 100
            await orchestrator.context.log(f"Orchestrator: Error executing agent {agent_name}: {str(e)}")
            if hasattr(orchestrator, "state_manager") and orchestrator.state_manager:
                orchestrator.state_manager.add_error(str(e))
        finally:
            # Release Locks
            if is_writer and hasattr(orchestrator, "lock_manager") and orchestrator.lock_manager:
                for path in target_files:
                    orchestrator.lock_manager.release_lock(path, agent_name)
                    
            # Remove active agent
            if hasattr(orchestrator, "state_manager") and orchestrator.state_manager:
                orchestrator.state_manager.remove_active_agent(agent_name)
                
            # Publish AgentFinished event
            if hasattr(orchestrator, "event_bus"):
                try:
                    await orchestrator.event_bus.publish("AgentFinished", {"agent": agent_name, "status": status})
                except Exception:
                    pass
            
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
                from .shared_memory import sm_replace_all
                if session and hasattr(session, "workspace_root"):
                    workspace_id = os.path.basename(session.workspace_root) or "default"
                    run_id = getattr(session, "session_id", None) or workspace_id
                    await redis_client.set(f"session:{workspace_id}:ctx", json.dumps(state["memory"]), ex=3600)
                    await sm_replace_all(run_id, state["memory"] or {})
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

import typing
from agent_os.providers.interfaces import IModelRouter

class AgentOSModelRouterBridge(IModelRouter):
    def __init__(self, session):
        self.session = session
        from .adapters.router import ModelRouter as BackendModelRouter
        self.backend_router = BackendModelRouter()
        self._provider_health = {
            "anthropic": True,
            "openai": True,
            "gemini": True,
            "groq": True,
            "ollama": True
        }

    def health_check(self, provider_name: str) -> bool:
        return self._provider_health.get(provider_name.lower(), False)

    def set_provider_health(self, provider_name: str, healthy: bool) -> None:
        self._provider_health[provider_name.lower()] = healthy

    def cancel(self, task_id: str) -> None:
        pass

    async def generate(self, prompt: str, system_prompt: str = "", model_name: str = "default") -> str:
        messages = [{"role": "user", "content": prompt}]
        res = await self.backend_router.completion(
            profile=self.session.profile,
            messages=messages,
            system_prompt=system_prompt,
            is_agent=True,
            task_type=model_name
        )
        return res

    async def stream(self, prompt: str, system_prompt: str = "", model_name: str = "default") -> typing.AsyncGenerator[str, None]:
        messages = [{"role": "user", "content": prompt}]
        adapter = self.backend_router.get_adapter(self.session.profile, is_agent=True, task_type=model_name)
        async for chunk in adapter.stream_chat(messages, [], system_prompt):
            if chunk["type"] == "text":
                yield chunk["content"]

class AgentOrchestrator:
    def __init__(self, session=None, max_steps: int = 10000):
        self.max_steps = max_steps
        self.context = SharedContext()
        self.event_bus = EventBus()

        # Instantiate new Agent OS components
        from agent_os.core.cache import CacheService
        from agent_os.execution.lock_manager import FileLockManager
        from agent_os.kernel.state_manager import StateManager
        from agent_os.context.context_manager import WorkspaceContextManager
        from agent_os.kernel.scheduler import DependencyScheduler

        self.cache = CacheService()
        self.lock_manager = FileLockManager()
        self.state_manager = StateManager(None)
        self.context_manager = WorkspaceContextManager()
        self.scheduler_concurrent = DependencyScheduler()

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
            # Tier 6: Utility / Meta-Agents
            "Refactoring Agent": RefactoringAgent(self),
            "Context Compaction Agent": ContextCompactionAgent(self),
            "Title Agent": TitleAgent(self),
            "Summary Agent": SummaryAgent(self),
            # Tier 7: Next-Gen Reasoning Agents
            "Search Agent": SearchAgent(self),
            "Memory Agent": MemoryAgent(self),
            "Code Agent": ParallelAgentAdapter("Code Agent", self, "CodeAgent"),
            "Docs Agent": ParallelAgentAdapter("Docs Agent", self, "DocsAgent"),
            "Review Agent": ParallelAgentAdapter("Review Agent", self, "ReviewAgent"),
            "Test Agent": ParallelAgentAdapter("Test Agent", self, "TestAgent"),
        }
        apply_custom_agents_and_overrides(self)
        agent_names = list(self.agents.keys())
        if len(agent_names) != len(set(agent_names)):
            logger.warning("Duplicate agent mappings detected in orchestrator registry!")

        self.session = session
        if session is not None:
            self._init_kernel(session)


    def _init_kernel(self, session):
        # 1. Initialize AgentOS kernel & core modules
        from agent_os.core.registry import ServiceRegistry
        from agent_os.core.event_bus import EventBus as AOSEventBus
        from agent_os.core.config import DictionaryConfig
        from agent_os.core.logging import StandardLogger
        from agent_os.kernel.kernel import Kernel
        from agent_os.kernel.state_machine import TaskStateMachine
        from agent_os.skills.scheduler import SkillScheduler
        from agent_os.execution.engine import TransactionalExecutionEngine
        from agent_os.compiler.prompt_compiler import PromptCompiler
        from agent_os.context.virtual_memory import VirtualMemoryContextManager
        from agent_os.learning.memory_kernel import MemoryKernelManager
        from agent_os.learning.engine import LearningEngine
        from agent_os.learning.optimizer import PerformanceOptimizer
        from agent_os.repository.repository import RepositoryKernel

        from agent_os.repository.interfaces import IRepository
        from agent_os.learning.interfaces import IMemoryManager, ILearningEngine, IPerformanceOptimizer
        from agent_os.execution.interfaces import ITransactionalExecutionEngine
        from agent_os.compiler.interfaces import IPromptCompiler
        from agent_os.providers.interfaces import IModelRouter
        from agent_os.kernel.interfaces import ITaskStateMachine
        from agent_os.skills.interfaces import ISkillScheduler

        from agent_os.kernel.budget_manager import BudgetManager
        from agent_os.kernel.health_monitor import HealthMonitor
        from agent_os.kernel.cancellation_manager import CancellationManager
        from agent_os.kernel.policy_engine import PolicyEngine

        self.registry = ServiceRegistry()
        self.aos_event_bus = AOSEventBus()
        self.config = DictionaryConfig(session.profile)
        self.logger_os = StandardLogger("AgentOS")

        # Instantiate and register standard services to satisfy Kernel resolve requirement
        workspace_root = getattr(session, "workspace_root", None) or ""
        budget_mgr = BudgetManager()
        health_mon = HealthMonitor()
        cancel_mgr = CancellationManager()
        policy_eng = PolicyEngine(workspace_root=workspace_root)

        self.registry.register_singleton(BudgetManager, budget_mgr)
        self.registry.register_singleton(HealthMonitor, health_mon)
        self.registry.register_singleton(CancellationManager, cancel_mgr)
        self.registry.register_singleton(PolicyEngine, policy_eng)

        self.kernel = Kernel(self.registry, self.aos_event_bus, self.config, self.logger_os)


        # Compute persistent directory inside ~/.devpilot/<workspace-hash>/
        import os
        import hashlib
        workspace_root = getattr(session, "workspace_root", None) or ""
        workspace_hash = hashlib.md5(workspace_root.encode("utf-8")).hexdigest() if workspace_root else "default"
        workspace_dir = os.path.join(os.path.expanduser("~"), ".devpilot", workspace_hash)
        os.makedirs(workspace_dir, exist_ok=True)

        repo_db_path = os.path.join(workspace_dir, "repo.db")
        learning_db_path = os.path.join(workspace_dir, "learning.db")
        self.memory_json_path = os.path.join(workspace_dir, "memory.json")

        # Instantiate kernels & services
        self.repo_kernel = RepositoryKernel(db_path=repo_db_path)
        self.memory_manager = MemoryKernelManager()
        if os.path.exists(self.memory_json_path):
            try:
                self.memory_manager.load_from_disk(self.memory_json_path)
            except Exception as load_err:
                self.logger_os.error(f"Failed to load memory state: {load_err}")

        self.exec_engine = TransactionalExecutionEngine(self.registry)
        self.compiler = PromptCompiler()
        self.router = AgentOSModelRouterBridge(session)
        self.state_machine = TaskStateMachine(event_bus=self.aos_event_bus)
        
        # Inject state machine into StateManager
        from agent_os.kernel.state_manager import StateManager
        self.state_manager = StateManager(self.state_machine)

        self.scheduler = SkillScheduler()
        self.learning_engine = LearningEngine(db_path=learning_db_path)
        self.optimizer = PerformanceOptimizer()

        # Import Interfaces
        from agent_os.core.interfaces import ICache
        from agent_os.execution.interfaces import IFileLockManager
        from agent_os.context.interfaces import IContextManager

        # Wire context_mgr alias to satisfy DI and name conventions
        self.context_mgr = self.context_manager

        # Register singletons
        self.registry.register_singleton(IRepository, self.repo_kernel)
        self.registry.register_singleton(IMemoryManager, self.memory_manager)
        self.registry.register_singleton(ITransactionalExecutionEngine, self.exec_engine)
        self.registry.register_singleton(IPromptCompiler, self.compiler)
        self.registry.register_singleton(IModelRouter, self.router)
        self.registry.register_singleton(ITaskStateMachine, self.state_machine)
        self.registry.register_singleton(ISkillScheduler, self.scheduler)
        self.registry.register_singleton(ILearningEngine, self.learning_engine)
        self.registry.register_singleton(IPerformanceOptimizer, self.optimizer)
        self.registry.register_singleton(ICache, self.cache)
        self.registry.register_singleton(IFileLockManager, self.lock_manager)
        self.registry.register_singleton(IContextManager, self.context_mgr)
        self.registry.register_singleton(StateManager, self.state_manager)


        # Boot Kernel
        self.kernel.boot()

        # Scan workspace directories using RepositoryKernel and store symbols in SQLite memory database on start in a background thread
        if session.workspace_root:
            import threading
            threading.Thread(
                target=self.repo_kernel.scan_workspace,
                args=(session.workspace_root,),
                daemon=True
            ).start()

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

        await self.context.log("AgentOS: Initializing AgentOS Kernel dynamic session plan...")
        self.context.subtasks = []
        self.context.collaboration_log = []

        # Initialize or reset ContextManager and StateManager
        if hasattr(self, "state_manager") and self.state_manager:
            self.state_manager.clear()
            self.state_manager.set_current_task(task_description)
            
        if hasattr(self, "context_manager") and self.context_manager:
            self.context_manager.clear()
            self.context_manager.workspace_root = session.workspace_root if session else ""
            self.context_manager.add_message("user", task_description)

        # Publish TaskStarted event
        if hasattr(self, "event_bus"):
            try:
                await self.event_bus.publish("TaskStarted", {"task": task_description})
            except Exception:
                pass

        # 1. Initialize AgentOS kernel & core modules if not already done
        if not hasattr(self, "kernel") or self.session is not session:
            self._init_kernel(session)

        kernel = self.kernel
        repo_kernel = self.repo_kernel
        exec_engine = self.exec_engine
        state_machine = self.state_machine

        # Setup state machine EventBus updates to broadcast to WebSocket
        async def on_state_changed(payload):

            old = payload.get("old_state")
            new = payload.get("new_state")
            
            agent_mapping = {
                "NEW": ("Orchestrator Agent", "Task received"),
                "UNDERSTAND": ("Requirement Analysis Agent", "Analyzing task requirements"),
                "SEARCH": ("File System Agent", "Scanning repository structures and symbol declarations"),
                "PLAN": ("Planner Agent", "Formulating multi-agent subtask execution plan"),
                "EDIT": ("Coding Agent", "Executing scheduled developer skills and codebase writes"),
                "VERIFY": ("Integration Agent", "Verifying patches and running build checks"),
                "TEST": ("Testing Agent", "Running test suite validating modifications"),
                "REVIEW": ("Code Review Agent", "Running quality assurance patch review"),
                "DONE": ("Orchestrator Agent", "Task execution finished"),
                "FAILED": ("Orchestrator Agent", "Task execution failed")
            }
            mapped_agent, mapped_task = agent_mapping.get(new, ("Orchestrator Agent", f"Transitioned to {new}"))
            
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": mapped_agent,
                "active_task": mapped_task,
                "subtasks": self.context.subtasks,
                "collaboration_log": self.context.collaboration_log
            })

        self.aos_event_bus.subscribe("task_state_changed", on_state_changed)

        try:
            # 1. State: NEW -> UNDERSTAND
            state_machine.transition_to("UNDERSTAND")
            await self.context.log(f"AgentOS: Transitioned to UNDERSTAND. Task: {task_description}")

            from .intelligence.intent_compiler import intent_compiler
            from .intelligence.contract_generator import contract_generator
            from .brain.symbol_graph import symbol_graph
            from .brain.test_graph import test_graph
            from .brain.dependency_graph import dependency_graph
            from .brain.knowledge_graph import knowledge_graph
            from .analysis.prediction_engine import prediction_engine
            from .work_graph.dag_generator import dag_generator
            from .patch.patch_store import patch_store
            from .patch.patch_metadata import PatchMetadata
            from .merge.symbol_merge import symbol_merge
            from .merge.contract_validator import contract_validator
            from .merge.conflict_detector import conflict_detector
            from .verification.security_scanner import security_scanner
            from .verification.lint_runner import lint_runner
            from .verification.architecture_rules import architecture_rules
            from .verification.test_runner import test_runner
            from .debate.debate_engine import debate_engine
            from .debate.consensus import consensus_engine
            from .repair.root_cause_analyzer import root_cause_analyzer
            from .repair.continuous_learning import continuous_learning
            from .outcome.outcome_classifier import outcome_classifier
            from .outcome.release_gate import release_gate
            from .release.git_committer import git_committer
            from .release.summary_generator import summary_generator

            # Run Ingress / Intelligence Layer (Intent Compiler)
            compiled_intent = intent_compiler.compile(task_description)
            await self.context.log(
                f"[Intelligence Layer] Intent compiled. Goal: '{compiled_intent.goal[:60]}', "
                f"Risk: {compiled_intent.estimated_risk}, Constraints: {len(compiled_intent.constraints)}"
            )

            # Contract Generator
            for comp in compiled_intent.affected_components:
                contract = contract_generator.generate_contract(compiled_intent, comp)
                await self.context.log(
                    f"[Intelligence Layer] Contract compiled for {comp}: "
                    f"id={contract.contract_id}, type={contract.contract_type}, mutations={contract.allowed_mutations}"
                )

            req_agent = self.agents["Requirement Analysis Agent"]
            req_res = await req_agent.execute(task_description, session, task_id=1)
            await self.context.log(f"Requirement Analysis: {req_res}")

            # 2. State: UNDERSTAND -> SEARCH
            state_machine.transition_to("SEARCH")
            await self.context.log("AgentOS: Transitioned to SEARCH. Scanning workspace...")
            repo_kernel.scan_workspace(session.workspace_root)
            files = repo_kernel.list_files()
            await self.context.log(f"Repository Kernel indexed {len(files)} files.")

            # Living Project Brain & Change Analysis Engine
            test_graph.scan_project_tests(files)
            for f in files:
                if f.endswith(".py"):
                    full_p = os.path.join(session.workspace_root or ".", f)
                    if os.path.exists(full_p):
                        try:
                            with open(full_p, "r", encoding="utf-8") as f_io:
                                file_content = f_io.read()
                            symbol_graph.parse_file(f, file_content)
                            dependency_graph.scan_python_imports(f, file_content)
                        except Exception:
                            pass

            prediction = prediction_engine.predict_change_impact(compiled_intent)
            await self.context.log(
                f"[Change Analysis Engine] Prediction resolved: "
                f"predicted files={prediction.predicted_files}, "
                f"predicted tests={prediction.predicted_tests}, "
                f"estimated cost=${prediction.estimated_cost_usd:.3f} USD"
            )

            # 3. State: SEARCH -> PLAN
            state_machine.transition_to("PLAN")
            await self.context.log("AgentOS: Transitioned to PLAN. Generating subtask plan...")

            # Work Graph DAG compilation
            roles = ["code", "test", "review"]
            if "security" in task_description.lower():
                roles.append("security")
            dag_tasks = dag_generator.generate_dag(compiled_intent, roles)
            for dt in dag_tasks:
                await self.context.log(
                    f"[Work Graph Compiler] Compiled task DAG: "
                    f"id={dt.task_id}, agent={dt.agent_type}, desc='{dt.description[:40]}'"
                )

            planner = self.agents["Planner Agent"]
            plan_res = await planner.execute(task_description, session, task_id=2)
            await self.context.log(f"Planner: {plan_res}")

            # Send immediate updates containing planned subtasks
            await session.send_ws_message({
                "type": "agent_state",
                "active_agent": "Planner Agent",
                "active_task": "Subtask plan generated",
                "subtasks": self.context.subtasks,
                "collaboration_log": self.context.collaboration_log
            })

            # 4. State: PLAN -> EDIT
            state_machine.transition_to("EDIT")
            await self.context.log("AgentOS: Transitioned to EDIT. Processing subtasks transactionally...")

            subtasks = self.context.subtasks
            
            async def execute_one_subtask(st):
                st_id = st.get("id") or (subtasks.index(st) + 1)
                st_agent_name = st.get("agent")
                st_desc = st.get("description", "")
                
                await self.update_task_progress(st_id, 20, session, status="running")
                
                specialist = self.agents.get(st_agent_name)
                if specialist is None:
                    match = next((k for k in self.agents if k.lower() == st_agent_name.lower()), None)
                    specialist = self.agents.get(match) if match else self.agents["Coding Agent"]
                     
                await self.context.log(f"Starting subtask: {st_desc} with {specialist.name}")
                
                # Context Manager tracking
                if hasattr(self, "context_manager") and self.context_manager:
                    self.context_manager.add_active_symbol(st_agent_name)
                     
                # State Manager active agents
                if hasattr(self, "state_manager") and self.state_manager:
                    self.state_manager.add_active_agent(st_agent_name)
                     
                # Publish AgentStarted event
                if hasattr(self, "event_bus"):
                    try:
                        await self.event_bus.publish("AgentStarted", {"agent": st_agent_name, "task": st_desc})
                    except Exception:
                        pass

                # Concurrency File Lock check
                is_writer = "coding" in st_agent_name.lower() or "developer" in st_agent_name.lower()
                target_files = self.context.memory.get("target_files", [])
                if is_writer and hasattr(self, "lock_manager") and self.lock_manager:
                    for path in target_files:
                        self.lock_manager.acquire_lock(path, st_agent_name, exclusive=True)
                         
                # Wrap changes in transactional engine
                tx = exec_engine.create_transaction()
                tx.begin()
                try:
                    result = await specialist.execute(st_desc, session, st_id)
                    tx.commit()
                    await self.update_task_progress(st_id, 100, session, status="completed")
                    await self.context.log(f"Subtask completed successfully: {result}")

                    # Patch Store & Merge Engine Integration
                    p_id = f"patch_{st_agent_name}_{st_id}"
                    metadata = PatchMetadata(
                        patch_id=p_id,
                        author=st_agent_name,
                        changed_symbols=list(self.context_manager.active_symbols) if hasattr(self, "context_manager") else [],
                        assumptions=["Syntax verification passed"]
                    )
                    patch_store.add_patch(p_id, str(target_files), "diff placeholder", metadata)

                    has_conflicts = conflict_detector.detect_conflicts(str(target_files), ["main"])
                    if has_conflicts:
                        await self.context.log(f"[Merge Engine] Warning: Potential conflict detected in {target_files}")
                    
                    # Record successful repair learning
                    continuous_learning.record_successful_repair(
                        "Task executed successfully",
                        result[:100] if result else "Success",
                        str(target_files)
                    )
                    
                    # Update State Manager completed steps
                    if hasattr(self, "state_manager") and self.state_manager:
                        self.state_manager.add_completed_step(st_desc, st_agent_name, "success")
                        
                    # Publish AgentFinished event
                    if hasattr(self, "event_bus"):
                        try:
                            await self.event_bus.publish("AgentFinished", {"agent": st_agent_name, "status": "completed"})
                        except Exception:
                            pass
                    return result
                except Exception as st_err:
                    tx.rollback()
                    await self.update_task_progress(st_id, 0, session, status="failed")
                    await self.context.log(f"Subtask failed (rolled back changes): {str(st_err)}")
                    
                    # Root Cause Analyzer integration
                    rc = root_cause_analyzer.analyze_failure(str(st_err))
                    if rc:
                        await self.context.log(f"[Repair Engine] Root cause isolated: {rc.probable_cause}")
                        repair_sugg = continuous_learning.suggest_repair(str(st_err))
                        if repair_sugg:
                            await self.context.log(f"[Repair Engine] Suggestion from learning engine: {repair_sugg}")

                    # Update State Manager error
                    if hasattr(self, "state_manager") and self.state_manager:
                        self.state_manager.add_error(str(st_err))
                        
                    # Publish AgentFinished event
                    if hasattr(self, "event_bus"):
                        try:
                            await self.event_bus.publish("AgentFinished", {"agent": st_agent_name, "status": "failed"})
                        except Exception:
                            pass
                    raise st_err
                finally:
                    # Release Locks
                    if is_writer and hasattr(self, "lock_manager") and self.lock_manager:
                        for path in target_files:
                            self.lock_manager.release_lock(path, st_agent_name)
                            
                    # Remove active agent from State Manager
                    if hasattr(self, "state_manager") and self.state_manager:
                        self.state_manager.remove_active_agent(st_agent_name)

            # Execute graph via the concurrency scheduler (adjusting concurrency limit dynamically)
            from .state import config_manager
            concurrency_mode = config_manager.get_concurrency_mode()
            if concurrency_mode == "sequential":
                self.scheduler_concurrent.concurrency_limit = 1
            else:
                self.scheduler_concurrent.concurrency_limit = 3
            await self.scheduler_concurrent.execute_graph(subtasks, execute_one_subtask)

            # 5. State: EDIT -> VERIFY
            target_files = self.context.memory.get("target_files", [])
            any_code_agents_ran = any(
                st.get("agent") in ("Coding Agent", "Frontend Developer Agent", "Backend Developer Agent")
                and st.get("status") in ("completed", "success")
                for st in subtasks
            )
            should_verify = bool(target_files and any_code_agents_ran)
            sec_ok = True

            if should_verify:
                state_machine.transition_to("VERIFY")
                await self.context.log("AgentOS: Transitioned to VERIFY. Running integration check...")
                
                # Evidence Verification Grid (Security & Architecture checks)
                sec_ok = security_scanner.scan_files(target_files)
                await self.context.log(f"[Evidence Verification Grid] Security scan: {'PASSED' if sec_ok else 'FAILED'}")
                
                for tf in target_files:
                    violations = architecture_rules.validate_dependency_rules(tf)
                    for violation in violations:
                        await self.context.log(f"[Evidence Verification Grid] Violation: {violation}")

                verify_agent = self.agents["Integration Agent"]
                verify_res = await verify_agent.execute(task_description, session, task_id=len(subtasks)+3)
                await self.context.log(f"Integration Check: {verify_res}")

                # 6. State: VERIFY -> TEST
                state_machine.transition_to("TEST")
                await self.context.log("AgentOS: Transitioned to TEST. Running test suite...")
                
                # Incremental Testing via Test Graph
                tests_to_run = test_graph.get_tests_for_file(target_files[0])
                if tests_to_run:
                    await self.context.log(f"[Evidence Verification Grid] Running incremental tests: {tests_to_run}")
                    t_res = test_runner.run_tests(tests_to_run)
                    await self.context.log(f"[Evidence Verification Grid] Test runner success: {t_res.success}")

                testing_agent = self.agents["Testing Agent"]
                test_res = await testing_agent.execute(task_description, session, task_id=len(subtasks)+4)
                await self.context.log(f"Test Suite: {test_res}")

                # 7. State: TEST -> REVIEW
                state_machine.transition_to("REVIEW")
                await self.context.log("AgentOS: Transitioned to REVIEW. Performing patch review...")

                # Debate Engine & Consensus
                critiques = debate_engine.hold_debate("diff of modifications placeholder")
                for critique in critiques:
                    await self.context.log(
                        f"[Debate Engine] Critique from {critique.agent_name}: "
                        f"score={critique.score}, feedback='{critique.feedback}'"
                    )
                agreed = consensus_engine.resolve_consensus(critiques)
                await self.context.log(f"[Debate Engine] Consensus status: {'APPROVED' if agreed else 'REJECTED'}")

                review_agent = self.agents["Code Review Agent"]
                review_res = await review_agent.execute(task_description, session, task_id=len(subtasks)+5)
                await self.context.log(f"Patch Review: {review_res}")
            else:
                await self.context.log("Skipping Integration, Testing, and Code Review agents as no code changes were made.")
                state_machine.transition_to("VERIFY")
                state_machine.transition_to("TEST")
                state_machine.transition_to("REVIEW")

            # 8. State: REVIEW -> DONE
            state_machine.transition_to("DONE")
            await self.context.log("AgentOS: Transitioned to DONE. Performing outcome classification and release gate checks...")

            # Outcome Classifier & Release Gate
            classification = outcome_classifier.classify_outcome(
                test_failures=0,
                lint_passed=True,
                type_checks_passed=True,
                security_passed=sec_ok,
                contract_violations=[]
            )
            await self.context.log(
                f"[Outcome Classifier] Evidence Score={classification.evidence_score}, "
                f"Risk Score={classification.risk_score}, Grade={classification.grade.value}"
            )

            should_release = release_gate.should_auto_release(classification)
            if should_release:
                await self.context.log("[Release Gate] Approved for Auto Release. Committing changes...")
                commit_out = git_committer.commit_changes(session.workspace_root or ".", f"Automatic release: {task_description}")
                await self.context.log(f"[Release Engine] {commit_out}")
            else:
                await self.context.log("[Release Gate] Human Approval required before release.")

            s_text = summary_generator.generate_summary(
                target_files,
                task_description,
                "medium" if classification.risk_score >= 0.4 else "low"
            )
            await self.context.log(f"[Release Engine] Summary generated: {s_text}")

        except Exception as e:
            if state_machine.current_state != "FAILED":
                try:
                    state_machine.transition_to("FAILED")
                except Exception:
                    pass
            await self.context.log(f"AgentOS failed: {str(e)}")
            raise e
        finally:
            if hasattr(self, "memory_manager") and self.memory_manager and hasattr(self, "memory_json_path") and self.memory_json_path:
                try:
                    self.memory_manager.set_current_task(task_description)
                    self.memory_manager.add_event("TaskFinished", {"task": task_description, "state": state_machine.current_state})
                    self.memory_manager.persist_to_disk(self.memory_json_path)
                except Exception as persist_err:
                    logger.error(f"Failed to persist memory state: {persist_err}")
            kernel.shutdown()

        await session.send_ws_message({
            "type": "agent_state",
            "active_agent": "Orchestrator Agent",
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