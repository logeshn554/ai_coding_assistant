from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemConfig(BaseSettings):
    """System configuration parameters loaded from environment variables."""
    
    # LLM configurations
    llm_model: str = "claude-sonnet-4-6"
    decomposer_model: str = "claude-haiku-4-5-20251001"  # cheap for decompose

    # OpenHands condenser configurations
    condenser_max_size: int = 80
    condenser_keep_first: int = 4

    # Budget controls (MANDATORY)
    max_agent_cost_usd: float = 5.0       # per individual agent
    max_global_cost_usd: float = 30.0     # entire run
    max_iterations_per_agent: int = 100
    max_retries: int = 3

    # Evaluator-optimizer: maximum code → review → refine cycles before routing to END.
    # Prevents infinite loops when the Coding Agent cannot resolve a high-severity issue.
    max_refinement_cycles: int = 2

    # Stuck detector thresholds
    repeat_pair_threshold: int = 4
    monologue_threshold: int = 3
    ping_pong_threshold: int = 6

    # Infrastructure configurations
    redis_url: str = "redis://localhost:6379"
    postgres_url: str = "postgresql://langgraph:langgraph@localhost:5432/langgraph"
    langsmith_project: str = "parallel-agent-system"

    # Confirmation policy
    confirmation_policy: Literal["always", "never", "risky"] = "risky"
    risk_threshold: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
