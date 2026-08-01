import pytest
from parallel_agent_system.core.state import SubTask, AgentResult
from parallel_agent_system.core.config import SystemConfig
from parallel_agent_system.runtime.workspace_factory import WorkspaceFactory
from parallel_agent_system.runtime.event_store import RedisEventStore, get_redis_client, MemoryRedisStream
from parallel_agent_system.monitor.stuck_detector import AgentMonitor
from parallel_agent_system.agents.base import BaseParallelAgent
from parallel_agent_system.agents.code_agent import CodeAgent
from parallel_agent_system.runtime.agent_runtime import ActionEvent, ObservationEvent, Action, Observation


@pytest.mark.asyncio
async def test_workspace_factory():
    """Verify that WorkspaceFactory generates a valid sandboxed DockerWorkspace with correct names and port bindings."""
    task = SubTask(
        id="test-task-12345678",
        agent_type="code",
        description="Implement key functions",
        workspace_dir="/workspace/agent-test",
        priority=1
    )
    workspace = await WorkspaceFactory.create_docker(task)
    assert workspace.container_name == "agent-test-tas"
    assert workspace.image == "ghcr.io/openhands/runtime:latest"
    assert workspace.host_port > 0
    assert workspace.cleaned is False
    await workspace.cleanup()
    assert workspace.cleaned is True


@pytest.mark.asyncio
async def test_event_store_mock_redis():
    """Verify that RedisEventStore appends and tails events successfully using the in-memory stream fallback."""
    # Force use of MemoryRedisStream
    client = get_redis_client()
    assert client is MemoryRedisStream

    store = RedisEventStore(run_id="run-1", subtask_id="task-1")
    
    # Append events
    ev1 = ActionEvent(action=Action(content="ls"), cost_usd=0.01)
    ev2 = ObservationEvent(observation=Observation(content="file.py"), cost_usd=0.02)
    
    await store.append(ev1)
    await store.append(ev2)
    
    # Collect streamed events
    streamed = []
    async for event in store.tail():
        streamed.append(event)
        if len(streamed) == 2:
            break
            
    assert len(streamed) == 2
    assert isinstance(streamed[0], ActionEvent)
    assert isinstance(streamed[1], ObservationEvent)
    assert streamed[0].action.content == "ls"
    assert streamed[1].observation.content == "file.py"


def test_agent_monitor_guardrails():
    """Verify loop detectors, monologue streak limits, and budget watchdogs."""
    config = SystemConfig(
        max_agent_cost_usd=1.0,
        monologue_threshold=3,
        repeat_pair_threshold=4
    )
    monitor = AgentMonitor(subtask_id="task-1", config=config)

    # 1. Check budget limits
    assert monitor.over_budget() is False
    monitor.observe(ActionEvent(action=Action(content="run task"), cost_usd=0.5))
    assert monitor.over_budget() is False
    monitor.observe(ActionEvent(action=Action(content="run task"), cost_usd=0.6))
    assert monitor.over_budget() is True

    # 2. Check monologue streak detection
    monitor2 = AgentMonitor(subtask_id="task-2", config=config)
    # Consecutive non-tool-calls increment monologue
    monitor2.observe(ActionEvent(action=Action(content="thought", is_tool_call=False)))
    monitor2.observe(ActionEvent(action=Action(content="thought", is_tool_call=False)))
    assert monitor2.is_stuck() is False
    monitor2.observe(ActionEvent(action=Action(content="thought", is_tool_call=False)))
    assert monitor2.is_stuck() is True

    # 3. Check loop repeat pairs detection
    monitor3 = AgentMonitor(subtask_id="task-3", config=config)
    act = ActionEvent(action=Action(type="bash", content="ls"))
    obs = ObservationEvent(observation=Observation(content="x"))
    
    for _ in range(3):
        monitor3.observe(act)
        monitor3.observe(obs)
        assert monitor3.is_stuck() is False

    # 4th repeat triggers stuck state
    monitor3.observe(act)
    monitor3.observe(obs)
    assert monitor3.is_stuck() is True


@pytest.mark.asyncio
async def test_agent_run_success():
    """Verify that specialist agents complete successfully and clean up resources."""
    config = SystemConfig()
    agent = CodeAgent(config=config)
    
    subtask = SubTask(
        id="task-code-1",
        agent_type="code",
        description="Verify calculations",
        workspace_dir="/workspace/agent-code-1"
    )

    result = await agent.run(subtask)
    assert result.status == "success"
    assert result.subtask_id == "task-code-1"
    assert result.files_changed == ["src/hello.py"]


@pytest.mark.asyncio
async def test_agent_run_stuck_error():
    """Verify that agent monitor successfully intercepts stuck states and returns appropriate statuses."""
    config = SystemConfig(repeat_pair_threshold=4)
    agent = CodeAgent(config=config)
    
    subtask = SubTask(
        id="task-stuck-1",
        agent_type="code",
        # Custom mock keyword triggers loop emission
        description="trigger stuck",
        workspace_dir="/workspace/agent-stuck-1"
    )

    result = await agent.run(subtask)
    assert result.status == "stuck"
    assert "stuck" in result.output
    assert result.iterations > 0


@pytest.mark.asyncio
async def test_agent_run_budget_error():
    """Verify that agent monitor successfully intercepts budget exhaustion and returns appropriate statuses."""
    config = SystemConfig(max_agent_cost_usd=5.0)
    agent = CodeAgent(config=config)
    
    subtask = SubTask(
        id="task-budget-1",
        agent_type="code",
        # Custom mock keyword triggers expensive actions
        description="trigger budget",
        workspace_dir="/workspace/agent-budget-1"
    )

    result = await agent.run(subtask)
    assert result.status == "budget_exceeded"
    assert "limit hit" in result.output
