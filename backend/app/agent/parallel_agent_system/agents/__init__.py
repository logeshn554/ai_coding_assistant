from parallel_agent_system.agents.base import BaseParallelAgent
from parallel_agent_system.agents.code_agent import CodeAgent
from parallel_agent_system.agents.test_agent import TestAgent
from parallel_agent_system.agents.docs_agent import DocsAgent
from parallel_agent_system.agents.review_agent import ReviewAgent


AGENT_REGISTRY: dict[str, type[BaseParallelAgent]] = {
    "code": CodeAgent,
    "test": TestAgent,
    "docs": DocsAgent,
    "review": ReviewAgent,
}

__all__ = [
    "BaseParallelAgent",
    "CodeAgent",
    "TestAgent",
    "DocsAgent",
    "ReviewAgent",
    "AGENT_REGISTRY",
]
