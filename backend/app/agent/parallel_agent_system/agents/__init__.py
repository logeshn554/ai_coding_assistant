from parallel_agent_system.agents.base import BaseParallelAgent
from parallel_agent_system.agents.code_agent import CodeAgent
from parallel_agent_system.agents.docs_agent import DocsAgent
from parallel_agent_system.agents.review_agent import ReviewAgent
from parallel_agent_system.agents.specialist_agents import (
    ApiAgent,
    ArchitectAgent,
    BackendAgent,
    DatabaseAgent,
    DebugAgent,
    DevOpsAgent,
    FrontendAgent,
    GitAgent,
    IntegrationAgent,
    PerformanceAgent,
    PlannerAgent,
    ReleaseAgent,
    RequirementAgent,
    SecurityAgent,
    TerminalAgent,
)
from parallel_agent_system.agents.test_agent import TestAgent

AGENT_REGISTRY: dict[str, type[BaseParallelAgent]] = {
    "code": CodeAgent,
    "test": TestAgent,
    "docs": DocsAgent,
    "review": ReviewAgent,
    "frontend": FrontendAgent,
    "backend": BackendAgent,
    "security": SecurityAgent,
    "performance": PerformanceAgent,
    "debug": DebugAgent,
    "database": DatabaseAgent,
    "api": ApiAgent,
    "integration": IntegrationAgent,
    "devops": DevOpsAgent,
    "release": ReleaseAgent,
    "git": GitAgent,
    "terminal": TerminalAgent,
    "planner": PlannerAgent,
    "architect": ArchitectAgent,
    "requirement": RequirementAgent,
}

__all__ = [
    "AGENT_REGISTRY",
    "ApiAgent",
    "ArchitectAgent",
    "BackendAgent",
    "BaseParallelAgent",
    "CodeAgent",
    "DatabaseAgent",
    "DebugAgent",
    "DevOpsAgent",
    "DocsAgent",
    "FrontendAgent",
    "GitAgent",
    "IntegrationAgent",
    "PerformanceAgent",
    "PlannerAgent",
    "ReleaseAgent",
    "RequirementAgent",
    "ReviewAgent",
    "SecurityAgent",
    "TerminalAgent",
    "TestAgent",
]
