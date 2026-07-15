from typing import Any

from parallel_agent_system.runtime.agent_runtime import Agent, Conversation, LLM, Tool, LLMSummarizingCondenser
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.core.state import SubTask, AgentResult
from parallel_agent_system.core.errors import StuckError, BudgetExceeded
from parallel_agent_system.runtime.workspace_factory import WorkspaceFactory
from parallel_agent_system.runtime.event_store import RedisEventStore
from parallel_agent_system.runtime.secret_registry import SecretRegistry
from parallel_agent_system.runtime.skills_loader import SkillsLoader
from parallel_agent_system.monitor.stuck_detector import AgentMonitor


BASE_SYSTEM_PROMPT = """You are a specialist '{agent_type}' agent.
Your current task is: {task}

Conventions and skills active for this task:
{skills}
"""


class BaseParallelAgent:
    """Base class for all specialist agents running inside parallel Docker environments."""
    
    agent_type: str = "base"
    default_tools: list[str] = []

    def __init__(self, config: SystemConfig):
        self.config = config
        
        # Late-bind the LLM API Key from the secret registry
        api_key = SecretRegistry.get("LLM_API_KEY")
        self.llm = LLM(
            model=config.llm_model,
            api_key=api_key,
        )
        
        # Initialize memory summarizer condenser
        self.condenser = LLMSummarizingCondenser(
            llm=self.llm,
            max_size=config.condenser_max_size,
            keep_first=config.condenser_keep_first
        )

    async def run(self, subtask: SubTask, session=None) -> AgentResult:
        """
        Spins up isolated workspace, executes the agent stream loop, and collects final results.
        Enforces execution stuck loops, monologue streaks, and budget boundaries.
        """
        # Create isolated Docker workspace per subtask
        workspace = await WorkspaceFactory.create_docker(subtask)
        
        # Instantiate agent execution configurations
        agent = Agent(
            llm=self.llm,
            tools=self._build_tools(),
            condenser=self.condenser,
            system_prompt=self._build_system_prompt(subtask),
        )
        
        # Open conversation session attached to workspace
        conversation = Conversation(agent=agent, workspace=workspace)
        
        # Setup Redis stream logs
        event_store = RedisEventStore(run_id=subtask.run_id or subtask.id, subtask_id=subtask.id, attempt=subtask.attempt)
        
        # Initialize stuck and budget loop monitor
        monitor = AgentMonitor(subtask_id=subtask.id, config=self.config)

        async def update_ui(status, progress):
            if session:
                subtask_entry = next((s for s in session.parallel_subtasks if s["id"] == subtask.id), None)
                if not subtask_entry:
                    subtask_entry = {
                        "id": subtask.id,
                        "agent": self.agent_type.capitalize() + " Agent",
                        "description": subtask.description,
                        "status": status,
                        "progress": progress
                    }
                    session.parallel_subtasks.append(subtask_entry)
                else:
                    subtask_entry["status"] = status
                    subtask_entry["progress"] = progress
                
                log_msg = f"Agent {self.agent_type.capitalize()} (Subtask {subtask.id[:8]}): Iteration {monitor.iterations}, Cost: ${monitor.cost:.3f}"
                if log_msg not in session.collaboration_log:
                    session.collaboration_log.append(log_msg)
                    
                await session.send_ws_message({
                    "type": "agent_state",
                    "active_agent": self.agent_type.capitalize() + " Agent",
                    "active_task": subtask.description,
                    "subtasks": session.parallel_subtasks,
                    "collaboration_log": session.collaboration_log
                })

        try:
            # Stream events and check guardrails
            async for event in conversation.stream(subtask.description):
                await event_store.append(event)
                monitor.observe(event)
                await update_ui("running", min(95, 10 + monitor.iterations * 5))
                
                # Enforce safety boundaries
                if monitor.is_stuck():
                    raise StuckError(f"Agent {self.agent_type} stuck on {subtask.id}")
                if monitor.over_budget():
                    raise BudgetExceeded(f"Cost limit hit for {subtask.id}")
                    
        except (StuckError, BudgetExceeded) as e:
            await update_ui("failed", 100)
            return AgentResult(
                subtask_id=subtask.id,
                agent_type=self.agent_type,
                status="stuck" if isinstance(e, StuckError) else "budget_exceeded",
                output=str(e),
                cost_usd=monitor.cost,
                iterations=monitor.iterations,
                event_log_key=event_store.key,
                error=str(e)
            )
        except Exception as e:
            # Uncaught execution errors
            await update_ui("failed", 100)
            return AgentResult(
                subtask_id=subtask.id,
                agent_type=self.agent_type,
                status="failed",
                output=f"Agent execution encountered an unhandled error: {str(e)}",
                cost_usd=monitor.cost,
                iterations=monitor.iterations,
                event_log_key=event_store.key,
                error=str(e)
            )
        finally:
            # Always clean up workspace container
            await workspace.cleanup()

        # Capture final finish thoughts and outputs
        finish = conversation.state.last_finish_action
        files_changed = finish.outputs.get("files_changed", []) if finish.outputs else []

        await update_ui("success", 100)
        return AgentResult(
            subtask_id=subtask.id,
            agent_type=self.agent_type,
            status="success",
            output=finish.final_thought,
            files_changed=files_changed,
            cost_usd=monitor.cost,
            iterations=monitor.iterations,
            event_log_key=event_store.key
        )

    def _build_tools(self) -> list[Tool]:
        """Maps default string tools to Tool structures."""
        return [Tool(name=n) for n in self.default_tools]

    def _build_system_prompt(self, subtask: SubTask) -> str:
        """Loads custom skill guidelines and builds agent prompt."""
        skills = SkillsLoader.load_for_task(subtask.description)
        return BASE_SYSTEM_PROMPT.format(
            agent_type=self.agent_type,
            task=subtask.description,
            skills=skills,
        )
