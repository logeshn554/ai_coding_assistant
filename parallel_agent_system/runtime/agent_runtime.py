from typing import Any, AsyncGenerator
from pydantic import BaseModel, Field


# --- Native Event and Action Models ---

class Event(BaseModel):
    """Base event representation."""
    cost_usd: float = 0.0


class Action(BaseModel):
    """Represents an action taken by an agent (e.g. tool execution, bash commands)."""
    type: str = "bash"
    content: str = ""
    is_tool_call: bool = True


class ActionEvent(Event):
    """Event emitted when an action is executed."""
    action: Action


class Observation(BaseModel):
    """Represents the feedback or stdout observed from executing an action."""
    content: str = ""


class ObservationEvent(Event):
    """Event emitted when an observation is received."""
    observation: Observation


# --- Native Execution Runtime Models ---

class DockerWorkspace:
    """Isolated environment simulation representing a container workspace."""
    
    def __init__(
        self,
        image: str,
        host_port: int,
        volumes: dict[str, Any],
        environment: dict[str, str],
        container_name: str,
        auto_remove: bool = True
    ):
        self.image = image
        self.host_port = host_port
        self.volumes = volumes
        self.environment = environment
        self.container_name = container_name
        self.auto_remove = auto_remove
        self.cleaned = False

    async def cleanup(self) -> None:
        """Cleans up host mounts and terminates execution containers."""
        import asyncio
        import shutil
        import os
        import logging as _logging
        logger = _logging.getLogger("parallel_agent_system.runtime")

        # 1. Stop and remove the Docker container
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", self.container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Docker rm command timed out. Unresponsive daemon.")
            logger.info("Successfully stopped and removed container '%s'", self.container_name)
        except Exception as e:
            logger.warning("Failed to stop container '%s' using docker CLI: %s", self.container_name, e)

        # 2. Unmount or delete agent_workspace_path volumes (e.g. /tmp/agent-*) (Bug 22)
        for host_path, volume_info in self.volumes.items():
            if volume_info.get("mode") == "rw":
                try:
                    if os.path.exists(host_path):
                        await asyncio.to_thread(shutil.rmtree, host_path, ignore_errors=True)
                        logger.info("Successfully cleaned up host path: %s", host_path)
                except Exception as e:
                    logger.warning("Failed to remove host path %s: %s", host_path, e)

        self.cleaned = True


class LLM:
    """Parameters representing an LLM model and connection credentials."""
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key


class Tool:
    """Agent Tool definition."""
    def __init__(self, name: str):
        self.name = name


class LLMSummarizingCondenser:
    """Memory condenser compressing execution state context."""
    def __init__(self, llm: LLM, max_size: int = 80, keep_first: int = 4):
        self.llm = llm
        self.max_size = max_size
        self.keep_first = keep_first


class FinishAction(BaseModel):
    """Final finish action containing summary thoughts and file modifications."""
    final_thought: str = "Task completed successfully."
    outputs: dict[str, Any] = Field(default_factory=dict)


class ConversationState:
    """State containing the final execution output."""
    def __init__(self):
        self.last_finish_action = FinishAction()


class Agent:
    """Built-in Agent class holding settings, tools, prompts, and memory managers."""
    def __init__(self, llm: LLM, tools: list[Tool], condenser: Any, system_prompt: str):
        self.llm = llm
        self.tools = tools
        self.condenser = condenser
        self.system_prompt = system_prompt


class Conversation:
    """Active conversation session connecting an Agent with their Workspace."""
    
    def __init__(self, agent: Agent, workspace: DockerWorkspace):
        self.agent = agent
        self.workspace = workspace
        self.state = ConversationState()

    async def stream(self, description: str) -> AsyncGenerator[Event, None]:
        """Simulates streaming events for the agent's tasks, supporting custom test hooks."""
        is_stuck_test = "trigger stuck" in description.lower()
        is_budget_test = "trigger budget" in description.lower()

        if is_stuck_test:
            # Emit repeat loops to trigger StuckError
            action = Action(type="bash", content="ls", is_tool_call=True)
            observation = Observation(content="file.txt")
            for _ in range(5):
                yield ActionEvent(action=action, cost_usd=0.01)
                yield ObservationEvent(observation=observation, cost_usd=0.01)
        elif is_budget_test:
            # Emit high costs to trigger BudgetExceeded
            yield ActionEvent(action=Action(content="run massive job"), cost_usd=10.0)
        else:
            # Standard successful path
            yield ActionEvent(action=Action(type="bash", content="cat hello.py"), cost_usd=0.02)
            yield ObservationEvent(observation=Observation(content="print('hello')"), cost_usd=0.02)
            yield ActionEvent(action=Action(type="bash", content="pytest"), cost_usd=0.05)
            yield ObservationEvent(observation=Observation(content="3 passed"), cost_usd=0.05)
            
            # Populate files changed in output
            self.state.last_finish_action.outputs = {"files_changed": ["src/hello.py"]}
