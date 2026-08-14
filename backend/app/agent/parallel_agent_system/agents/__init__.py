from parallel_agent_system.agents.base import BaseParallelAgent
from parallel_agent_system.agents.code_agent import CodeAgent
from parallel_agent_system.agents.test_agent import TestAgent
from parallel_agent_system.agents.docs_agent import DocsAgent
from parallel_agent_system.agents.review_agent import ReviewAgent
from parallel_agent_system.agents.specialist_agents import (
    FrontendAgent,
    BackendAgent,
    SecurityAgent,
    PerformanceAgent,
    DebugAgent,
    DatabaseAgent,
    ApiAgent,
    IntegrationAgent,
    DevOpsAgent,
    ReleaseAgent,
    GitAgent,
    TerminalAgent,
    PlannerAgent,
    ArchitectAgent,
    RequirementAgent,
)


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
    "BaseParallelAgent",
    "CodeAgent",
    "TestAgent",
    "DocsAgent",
    "ReviewAgent",
    "FrontendAgent",
    "BackendAgent",
    "SecurityAgent",
    "PerformanceAgent",
    "DebugAgent",
    "DatabaseAgent",
    "ApiAgent",
    "IntegrationAgent",
    "DevOpsAgent",
    "ReleaseAgent",
    "GitAgent",
    "TerminalAgent",
    "PlannerAgent",
    "ArchitectAgent",
    "RequirementAgent",
    "AGENT_REGISTRY",
]
