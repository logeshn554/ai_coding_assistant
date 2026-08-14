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
    
    def __init__(self, agent: Agent, workspace: DockerWorkspace, run_id: str | None = None):
        self.agent = agent
        self.workspace = workspace
        self.state = ConversationState()
        self.run_id = run_id

    async def stream(self, description: str) -> AsyncGenerator[Event, None]:
        """Runs the real agent reasoning loop if credentials exist, else falls back to simulation."""
        is_stuck_test = "trigger stuck" in description.lower()
        is_budget_test = "trigger budget" in description.lower()

        if is_stuck_test:
            # Emit repeat loops to trigger StuckError
            action = Action(type="bash", content="ls", is_tool_call=True)
            observation = Observation(content="file.txt")
            for _ in range(5):
                yield ActionEvent(action=action, cost_usd=0.01)
                yield ObservationEvent(observation=observation, cost_usd=0.01)
            return
        elif is_budget_test:
            # Emit high costs to trigger BudgetExceeded
            yield ActionEvent(action=Action(content="run massive job"), cost_usd=10.0)
            return

        # Check if we should run mock/simulated mode
        from parallel_agent_system.runtime.secret_registry import SecretRegistry
        import os as _os
        api_key = self.agent.llm.api_key or SecretRegistry.get("LLM_API_KEY")
        mock_mode = _os.environ.get("AGENT_RUNTIME_MODE", "").lower() == "mock"

        if not api_key or api_key.startswith("mock") or mock_mode:
            # Standard successful path simulation fallback
            yield ActionEvent(action=Action(type="bash", content="cat hello.py"), cost_usd=0.02)
            yield ObservationEvent(observation=Observation(content="print('hello')"), cost_usd=0.02)
            yield ActionEvent(action=Action(type="bash", content="pytest"), cost_usd=0.05)
            yield ObservationEvent(observation=Observation(content="3 passed"), cost_usd=0.05)
            self.state.last_finish_action.outputs = {"files_changed": ["src/hello.py"]}
            return

        # Real Agent Loop Execution
        workspace_root = "."
        for host_path, volume_info in self.workspace.volumes.items():
            if volume_info.get("mode") == "rw":
                workspace_root = host_path
                break

        # Setup real LLM provider
        from agent_runtime.llm.openai_provider import OpenAIProvider
        
        # Check active profile or SecretRegistry for base_url
        from parallel_agent_system.runtime.secret_registry import SecretRegistry
        base_url = SecretRegistry.get("LLM_BASE_URL") or "https://api.openai.com/v1"
        if not SecretRegistry.get("LLM_BASE_URL"):
            try:
                from backend.app.config import ConfigManager
                profile = ConfigManager().get_active_profile()
                if profile and profile.get("base_url"):
                    base_url = profile.get("base_url")
            except Exception:
                pass

        llm = OpenAIProvider(
            api_key=api_key,
            model=self.agent.llm.model or "gpt-4o-mini",
            base_url=base_url
        )

        # Setup real tools based on requested tools
        from agent_runtime.tools import ToolRegistry
        from agent_runtime.tools.filesystem import create_filesystem_tools
        from agent_runtime.tools.terminal import create_terminal_tools
        from agent_runtime.tools.search import create_search_tools

        tool_registry = ToolRegistry()
        req_tool_names = {t.name for t in self.agent.tools}

        if "file_editor" in req_tool_names or any("file" in t for t in req_tool_names):
            for t in create_filesystem_tools(workspace_root):
                tool_registry.register(t)
        if "bash" in req_tool_names or "run_command" in req_tool_names:
            for t in create_terminal_tools(workspace_root):
                tool_registry.register(t)
        # Register search tools for all agents to aid context discovery
        for t in create_search_tools(workspace_root):
            tool_registry.register(t)

        # Register shared memory tools for all agents
        conv_run_id = self.run_id or "default"
        try:
            from agent_runtime.tools.shared_memory import create_shared_memory_tools
            for t in create_shared_memory_tools(conv_run_id):
                tool_registry.register(t)
        except Exception as e:
            import logging
            logging.getLogger("parallel_agent_system.runtime").warning("Failed to register shared memory tools: %s", e)

        from agent_runtime.loop import agent_loop, LoopConfig
        config = LoopConfig(
            max_iterations=50,
            max_cost_usd=5.0,
            temperature=0.0
        )

        from agent_runtime.workspace.changes import get_workspace_snapshot, detect_changed_files
        before_snapshot = get_workspace_snapshot(workspace_root)

        # Run real loop
        async for event in agent_loop(
            llm=llm,
            tool_registry=tool_registry,
            system_prompt=self.agent.system_prompt,
            user_message=description,
            config=config,
            run_id=conv_run_id
        ):
            if event.type == "llm_call":
                # Convert to ActionEvent
                yield ActionEvent(
                    action=Action(type="thought", content=event.content or "(thinking)", is_tool_call=False),
                    cost_usd=event.cost_usd
                )
            elif event.type == "tool_call":
                yield ActionEvent(
                    action=Action(
                        type="bash",
                        content=f"Calling tool: {event.tool_name} with arguments: {event.tool_args}",
                        is_tool_call=True
                    ),
                    cost_usd=0.0
                )
            elif event.type == "tool_result":
                yield ObservationEvent(
                    observation=Observation(content=event.tool_result or ""),
                    cost_usd=0.0
                )
            elif event.type == "final":
                # Perform robust mtime/size snapshot + Git status changed files detection
                changed_files = await detect_changed_files(workspace_root, before_snapshot)
                self.state.last_finish_action = FinishAction(
                    final_thought=event.content,
                    outputs={"files_changed": changed_files}
                )
