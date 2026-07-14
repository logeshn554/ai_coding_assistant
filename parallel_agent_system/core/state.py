import operator
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SubTask(BaseModel):
    """Represents a decomposed subtask to be executed by a specialist agent."""
    id: str
    agent_type: Literal["code", "test", "docs", "review"]
    description: str
    workspace_dir: str
    priority: int = 0
    depends_on: list[str] = Field(default_factory=list)  # list of other subtask IDs


class AgentResult(BaseModel):
    """The result output of a single subtask execution by an agent."""
    subtask_id: str
    agent_type: str
    status: Literal["success", "failed", "stuck", "budget_exceeded"]
    output: str
    files_changed: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    iterations: int = 0
    event_log_key: str
    error: str | None = None


class GraphState(TypedDict):
    """The central state schema for the LangGraph StateGraph orchestrator."""
    run_id: str
    goal: str
    subtasks: list[SubTask]
    results: Annotated[list[AgentResult], operator.add]
    global_cost_usd: float
    iteration: int
    status: Literal["pending", "running", "reducing", "monitoring", "complete", "failed"]
    human_confirmation_required: bool
    messages: Annotated[list[BaseMessage], add_messages]
