from typing import Any

from agent_os.kernel.interfaces import ITaskStateMachine


class StateManager:
    """Manages the current task metadata, active agents, step progress, and execution errors."""
    def __init__(self, state_machine: ITaskStateMachine) -> None:
        self.state_machine = state_machine
        self._current_task: str | None = None
        self._active_agents: list[str] = []
        self._task_status: str = "PENDING"  # PENDING, RUNNING, SUCCEEDED, FAILED
        self._completed_steps: list[dict[str, Any]] = []
        self._errors: list[str] = []

    @property
    def current_task(self) -> str | None:
        return self._current_task

    def set_current_task(self, task: str) -> None:
        self._current_task = task
        self._task_status = "RUNNING"

    @property
    def active_agents(self) -> list[str]:
        return self._active_agents

    def add_active_agent(self, agent_name: str) -> None:
        if agent_name not in self._active_agents:
            self._active_agents.append(agent_name)

    def remove_active_agent(self, agent_name: str) -> None:
        if agent_name in self._active_agents:
            self._active_agents.remove(agent_name)

    @property
    def task_status(self) -> str:
        return self._task_status

    def set_task_status(self, status: str) -> None:
        self._task_status = status.upper()

    @property
    def completed_steps(self) -> list[dict[str, Any]]:
        return self._completed_steps

    def add_completed_step(self, step_name: str, agent: str, result: Any = None) -> None:
        self._completed_steps.append({
            "step": step_name,
            "agent": agent,
            "result": result
        })

    @property
    def errors(self) -> list[str]:
        return self._errors

    def add_error(self, error: str) -> None:
        self._errors.append(error)
        self._task_status = "FAILED"

    def clear(self) -> None:
        self._current_task = None
        self._active_agents.clear()
        self._task_status = "PENDING"
        self._completed_steps.clear()
        self._errors.clear()
