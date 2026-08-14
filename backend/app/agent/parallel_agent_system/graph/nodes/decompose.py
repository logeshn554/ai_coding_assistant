from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import SubTask, GraphState
from parallel_agent_system.runtime.secret_registry import SecretRegistry


class RawSubTask(BaseModel):
    """Temporary Pydantic model for structured LLM parsing."""
    id: str = Field(description="A short, unique stable identifier slug for this task, e.g. 'implement-module' or 'test-module'")
    agent_type: Literal[
        "code", "frontend", "backend", "test", "docs", "review",
        "security", "performance", "debug", "database", "api",
        "integration", "devops", "release", "git", "terminal",
        "planner", "architect", "requirement"
    ]
    description: str = Field(description="Precise description of what needs to be done")
    priority: int = Field(default=0, description="Task execution priority")
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of other task identifier slugs (id) that MUST complete first"
    )


class DecomposedTasksList(BaseModel):
    """Wrapper model representing the full list of decomposed tasks."""
    tasks: list[RawSubTask]


DECOMPOSE_SYSTEM_PROMPT = """You are a master distributed task decomposer.
Decompose the user's software engineering goal into a list of parallel subtasks.
Each subtask will be assigned to one of the specialist agents matching its type (e.g., 'code', 'test', 'review', 'database', etc.).

Rules to enforce:
1. Every task MUST have a short, unique stable identifier 'id' slug (e.g. 'implement-module').
2. 'depends_on' MUST strictly contain the 'id' slugs of dependency tasks (not their natural language descriptions).
3. 'code' tasks MUST come before 'test' tasks that verify the same module.
4. 'review' tasks MUST depend on their respective 'code' and 'test' tasks.
5. Keep the list size to at most 8 subtasks.
"""


async def decompose_task_node(state: GraphState) -> dict:
    """
    Calls the LLM to decompose the goal into N SubTasks.
    Converts slug-based dependencies into unique UUID strings.
    """
    if state.get("subtasks"):
        return {"status": "running", "results": state.get("results", [])}

    config = SystemConfig()
    api_key = SecretRegistry.get("LLM_API_KEY")
    session = state.get("session")

    import os as _os

    # Offline/Test Fallback mode: only activate via explicit env var or missing API key
    _mock_mode = _os.environ.get("AGENT_RUNTIME_MODE", "").lower() == "mock"
    if not api_key or api_key.startswith("mock") or _mock_mode:
        raw_tasks = [
            RawSubTask(
                id="implement-module",
                agent_type="code",
                description="Implement the primary module",
                priority=10,
                depends_on=[]
            ),
            RawSubTask(
                id="test-module",
                agent_type="test",
                description="Write unit tests for the primary module",
                priority=5,
                depends_on=["implement-module"]
            ),
            RawSubTask(
                id="review-module",
                agent_type="review",
                description="Security and style review",
                priority=1,
                depends_on=[
                    "implement-module",
                    "test-module"
                ]
            )
        ]
    else:
        if session:
            from backend.app.orchestrator import DevPilotChatModel
            llm = DevPilotChatModel(session=session, agent_name="Decomposer Agent")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", DECOMPOSE_SYSTEM_PROMPT + "\n\nResponse MUST be a valid JSON object matching this schema:\n"
                           "{\n  \"tasks\": [\n    {\n      \"id\": \"task-id-slug\",\n      \"agent_type\": \"code\"|\"test\"|\"review\"|...,\n      \"description\": \"...\",\n      \"priority\": 0,\n      \"depends_on\": []\n    }\n  ]\n}\n"
                           "Output only the JSON block without markdown fences, prose, or markdown formatting."),
                ("user", "Decompose this goal: {goal}")
            ])
            
            chain = prompt | llm
            response = await chain.ainvoke({"goal": state["goal"]})
            text_res = response.content if hasattr(response, "content") else str(response)
            
            # Robust JSON parsing
            import re
            import json
            text_res = re.sub(r"```json\s*", "", text_res)
            text_res = re.sub(r"```\s*", "", text_res)
            text_res = text_res.strip()
            match = re.search(r"(\{.*\})", text_res, re.DOTALL)
            if match:
                text_res = match.group(1)
            parsed = json.loads(text_res)
            if "tasks" in parsed:
                validated = DecomposedTasksList(tasks=[RawSubTask(**t) for t in parsed["tasks"]])
            else:
                if isinstance(parsed, list):
                    validated = DecomposedTasksList(tasks=[RawSubTask(**t) for t in parsed])
                else:
                    raise ValueError("JSON does not match the DecomposedTasksList schema")
            raw_tasks = validated.tasks
        else:
            # Setup LangChain LLM with structured output mapping for test fallback
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=config.decomposer_model,
                openai_api_key=api_key,
                temperature=0.0
            )
            structured_llm = llm.with_structured_output(DecomposedTasksList)

            prompt = ChatPromptTemplate.from_messages([
                ("system", DECOMPOSE_SYSTEM_PROMPT),
                ("user", "Decompose this goal: {goal}")
            ])

            chain = prompt | structured_llm
            response = await chain.ainvoke({"goal": state["goal"]})
            raw_tasks = response.tasks

    # Enforce maximum 8 subtasks limit
    raw_tasks = raw_tasks[:8]

    # Map slug ID -> SubTask instance and assign UUID IDs
    slug_to_uuid = {}
    subtasks = []

    for t in raw_tasks:
        subtask_id = str(uuid4())
        slug_to_uuid[t.id] = subtask_id
        
        # Workspace directory can default to a namespaced sandbox path
        workspace_dir = f"/workspace/agent-{subtask_id[:8]}"
        task_instance = SubTask(
            id=subtask_id,
            agent_type=t.agent_type,
            description=t.description,
            workspace_dir=workspace_dir,
            priority=t.priority,
            depends_on=[] # We resolve depends_on to IDs in the second pass
        )
        subtasks.append(task_instance)

    # Second pass: Resolve slug dependencies into subtask UUIDs
    for i, t in enumerate(raw_tasks):
        current_task = subtasks[i]
        resolved_depends_on = []
        for dep_slug in t.depends_on:
            target_uuid = slug_to_uuid.get(dep_slug)
            if target_uuid:
                resolved_depends_on.append(target_uuid)
            else:
                # Retain the unresolved slug so DAG validation catches and flags it downstream
                resolved_depends_on.append(dep_slug)
        current_task.depends_on = resolved_depends_on

    return {
        "subtasks": subtasks,
        "status": "running"
    }
