"""DevPilot Agent Intelligence Package.

Provides 14-phase agent control-flow infrastructure:
  - IntentRouter        : classify user intent before execution
  - ContextCollector    : auto-read referenced files/symbols before LLM call
  - PlanningEngine      : generate step-by-step task graph
  - TaskMemory          : persist execution state for reliable continue/resume
  - KnowledgeStore      : semantic workspace index (classes, functions, imports)
  - ConfidenceScorer    : score decisions; low confidence → collect more context
  - Validator           : pre-done checklist (files exist? syntax ok?)
  - Critic              : self-review pass (did I actually solve the request?)
  - WorkflowEngine      : per-intent specialized workflows
  - ToolPolicy          : deterministic tool selection rules
  - RecoveryManager     : structured retry/fallback on tool failure
  - ExecutionLogger     : structured JSON execution logs
"""
from .intent_router import IntentRouter, IntentType
from .context_collector import ContextCollector
from .task_memory import TaskMemory, TaskStep, TaskStatus
from .planning_engine import PlanningEngine
from .execution_logger import ExecutionLogger
from .tool_policy import ToolPolicy
from .recovery_manager import RecoveryManager
from .knowledge_store import KnowledgeStore
from .confidence_scorer import ConfidenceScorer
from .validator import Validator
from .critic import Critic
from .workflow_engine import WorkflowEngine
from ..session.agent_session import AgentSession

__all__ = [
    "IntentRouter", "IntentType",
    "ContextCollector",
    "TaskMemory", "TaskStep", "TaskStatus",
    "PlanningEngine",
    "ExecutionLogger",
    "ToolPolicy",
    "RecoveryManager",
    "KnowledgeStore",
    "ConfidenceScorer",
    "Validator",
    "Critic",
    "WorkflowEngine",
    "AgentSession",
]
