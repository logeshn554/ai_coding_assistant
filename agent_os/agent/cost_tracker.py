"""
Cost tracking and budget management for agent execution.

Tracks:
  - Token usage per agent/task/run
  - LLM API costs
  - Compute costs
  - Budget enforcement with alerts
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime
from enum import Enum


class CostType(str, Enum):
    """Types of costs tracked."""
    LLM_TOKENS = "llm_tokens"
    LLM_CALLS = "llm_calls"
    TOOL_EXECUTION = "tool_execution"
    COMPUTE = "compute"


@dataclass
class CostEntry:
    """Single cost entry."""
    timestamp: datetime
    cost_type: CostType
    amount: float
    unit: str  # tokens, calls, seconds, etc.
    metadata: Dict = field(default_factory=dict)


@dataclass
class AgentBudget:
    """Budget for an agent execution."""
    agent_id: str
    max_tokens: int = 50000
    max_cost_usd: float = 10.0
    max_tool_calls: int = 100
    max_duration_seconds: int = 3600

    tokens_used: int = 0
    cost_usd: float = 0.0
    tool_calls_made: int = 0
    duration_seconds: int = 0

    exceeded_token_budget: bool = False
    exceeded_cost_budget: bool = False
    exceeded_tool_budget: bool = False
    exceeded_time_budget: bool = False

    def is_within_budget(self) -> bool:
        """Check if all budgets are within limits."""
        return not any([
            self.exceeded_token_budget,
            self.exceeded_cost_budget,
            self.exceeded_tool_budget,
            self.exceeded_time_budget,
        ])

    def check_budgets(self) -> Dict[str, bool]:
        """Check all budgets and return status."""
        return {
            "tokens": self.tokens_used <= self.max_tokens,
            "cost": self.cost_usd <= self.max_cost_usd,
            "tool_calls": self.tool_calls_made <= self.max_tool_calls,
            "duration": self.duration_seconds <= self.max_duration_seconds,
        }


class CostTracker:
    """Tracks costs and manages budgets."""

    # Typical pricing (can be configured per provider)
    PRICING = {
        "gpt-4": {
            "input": 0.00003,  # $0.03 per 1K tokens
            "output": 0.00006,  # $0.06 per 1K tokens
        },
        "gpt-3.5-turbo": {
            "input": 0.0000015,  # $0.0015 per 1K tokens
            "output": 0.000002,  # $0.002 per 1K tokens
        },
        "claude-3-opus": {
            "input": 0.000015,  # $0.015 per 1K tokens
            "output": 0.000075,  # $0.075 per 1K tokens
        },
    }

    def __init__(self):
        """Initialize cost tracker."""
        self.costs: Dict[str, list] = {}  # run_id -> list of CostEntry
        self.budgets: Dict[str, AgentBudget] = {}
        self.run_start_times: Dict[str, datetime] = {}

    def create_budget(self, agent_id: str, **kwargs) -> AgentBudget:
        """Create budget for agent."""
        budget = AgentBudget(agent_id=agent_id, **kwargs)
        self.budgets[agent_id] = budget
        return budget

    def track_token_usage(
        self,
        run_id: str,
        agent_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Track token usage and calculate cost.

        Args:
            run_id: Run identifier
            agent_id: Agent identifier
            model: Model name (e.g., gpt-4)
            input_tokens: Input tokens used
            output_tokens: Output tokens generated

        Returns:
            Cost in USD
        """
        if run_id not in self.costs:
            self.costs[run_id] = []

        # Calculate cost
        pricing = self.PRICING.get(model, self.PRICING["gpt-3.5-turbo"])
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        total_cost = input_cost + output_cost

        # Record entry
        entry = CostEntry(
            timestamp=datetime.utcnow(),
            cost_type=CostType.LLM_TOKENS,
            amount=total_cost,
            unit="usd",
            metadata={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "agent_id": agent_id,
            }
        )
        self.costs[run_id].append(entry)

        # Update budget
        if agent_id in self.budgets:
            budget = self.budgets[agent_id]
            budget.tokens_used += input_tokens + output_tokens
            budget.cost_usd += total_cost

            # Check budgets
            if budget.tokens_used > budget.max_tokens:
                budget.exceeded_token_budget = True
            if budget.cost_usd > budget.max_cost_usd:
                budget.exceeded_cost_budget = True

        return total_cost

    def track_tool_execution(
        self,
        run_id: str,
        agent_id: str,
        tool_name: str,
        duration_seconds: float,
    ) -> None:
        """Track tool execution cost."""
        if run_id not in self.costs:
            self.costs[run_id] = []

        entry = CostEntry(
            timestamp=datetime.utcnow(),
            cost_type=CostType.TOOL_EXECUTION,
            amount=duration_seconds,
            unit="seconds",
            metadata={
                "tool": tool_name,
                "agent_id": agent_id,
            }
        )
        self.costs[run_id].append(entry)

        # Update budget
        if agent_id in self.budgets:
            budget = self.budgets[agent_id]
            budget.tool_calls_made += 1

            if budget.tool_calls_made > budget.max_tool_calls:
                budget.exceeded_tool_budget = True

    def start_run_timer(self, run_id: str) -> None:
        """Start timing a run."""
        self.run_start_times[run_id] = datetime.utcnow()

    def get_run_duration(self, run_id: str) -> float:
        """Get run duration in seconds."""
        if run_id not in self.run_start_times:
            return 0.0
        elapsed = datetime.utcnow() - self.run_start_times[run_id]
        return elapsed.total_seconds()

    def update_budget_duration(self, agent_id: str, run_id: str) -> None:
        """Update duration in budget."""
        if agent_id in self.budgets:
            self.budgets[agent_id].duration_seconds = int(self.get_run_duration(run_id))

            if self.budgets[agent_id].duration_seconds > self.budgets[agent_id].max_duration_seconds:
                self.budgets[agent_id].exceeded_time_budget = True

    def get_run_cost_summary(self, run_id: str) -> Dict:
        """Get cost summary for a run."""
        if run_id not in self.costs:
            return {"total_cost": 0.0, "entries": []}

        entries = self.costs[run_id]
        total_cost = sum(e.amount for e in entries if e.cost_type == CostType.LLM_TOKENS)

        token_entries = [e for e in entries if e.cost_type == CostType.LLM_TOKENS]
        tool_entries = [e for e in entries if e.cost_type == CostType.TOOL_EXECUTION]

        return {
            "total_cost_usd": round(total_cost, 4),
            "token_cost_usd": round(total_cost, 4),
            "total_tokens": sum(
                e.metadata.get("input_tokens", 0) + e.metadata.get("output_tokens", 0)
                for e in token_entries
            ),
            "tool_executions": len(tool_entries),
            "entry_count": len(entries),
        }

    def get_budget_status(self, agent_id: str) -> Dict:
        """Get budget status for agent."""
        if agent_id not in self.budgets:
            return {"error": "Budget not found"}

        budget = self.budgets[agent_id]
        return {
            "agent_id": agent_id,
            "tokens": {
                "used": budget.tokens_used,
                "limit": budget.max_tokens,
                "percent": round(100 * budget.tokens_used / budget.max_tokens, 1),
                "exceeded": budget.exceeded_token_budget,
            },
            "cost_usd": {
                "used": round(budget.cost_usd, 4),
                "limit": budget.max_cost_usd,
                "percent": round(100 * budget.cost_usd / budget.max_cost_usd, 1),
                "exceeded": budget.exceeded_cost_budget,
            },
            "tool_calls": {
                "used": budget.tool_calls_made,
                "limit": budget.max_tool_calls,
                "percent": round(100 * budget.tool_calls_made / budget.max_tool_calls, 1),
                "exceeded": budget.exceeded_tool_budget,
            },
            "duration_seconds": {
                "used": budget.duration_seconds,
                "limit": budget.max_duration_seconds,
                "percent": round(100 * budget.duration_seconds / budget.max_duration_seconds, 1),
                "exceeded": budget.exceeded_time_budget,
            },
            "within_budget": budget.is_within_budget(),
        }

    def alert_on_budget_exceeded(self, agent_id: str) -> Optional[str]:
        """Check if budget exceeded and generate alert."""
        if agent_id not in self.budgets:
            return None

        budget = self.budgets[agent_id]
        alerts = []

        if budget.exceeded_token_budget:
            alerts.append(f"Token budget exceeded: {budget.tokens_used}/{budget.max_tokens}")

        if budget.exceeded_cost_budget:
            alerts.append(f"Cost budget exceeded: ${budget.cost_usd:.2f}/${budget.max_cost_usd}")

        if budget.exceeded_tool_budget:
            alerts.append(f"Tool call budget exceeded: {budget.tool_calls_made}/{budget.max_tool_calls}")

        if budget.exceeded_time_budget:
            alerts.append(f"Time budget exceeded: {budget.duration_seconds}s/{budget.max_duration_seconds}s")

        if alerts:
            return " | ".join(alerts)

        return None
