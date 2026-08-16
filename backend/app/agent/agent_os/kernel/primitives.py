from dataclasses import dataclass, field
from typing import Any


@dataclass
class Capability:
    name: str
    description: str = ""

@dataclass
class Agent:
    agent_id: str
    agent_type: str
    status: str = "idle"
    capabilities: list[Capability] = field(default_factory=list)

@dataclass
class Budget:
    max_tokens: int = 0
    max_cost_usd: float = 0.0
    consumed_tokens: int = 0
    consumed_cost_usd: float = 0.0

@dataclass
class Task:
    task_id: str
    name: str
    status: str = "PENDING"  # PENDING, RUNNING, SUCCEEDED, FAILED
    dependencies: list[str] = field(default_factory=list)
    priority: int = 0
    budget: Budget | None = None

@dataclass
class Action:
    action_id: str
    action_type: str  # read_file, write_file, run_command, etc.
    target: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"  # PENDING, APPROVED, DENIED, SUCCESS, ERROR

@dataclass
class Resource:
    name: str
    resource_type: str  # file, directory, network, process
    path: str | None = None

@dataclass
class Policy:
    name: str
    policy_type: str
    rules: dict[str, Any] = field(default_factory=dict)

@dataclass
class Permission:
    agent_type: str
    resource: Resource
    access_level: str  # read, write, execute, all

@dataclass
class Checkpoint:
    checkpoint_id: str
    timestamp: float
    file_snapshots: dict[str, str] = field(default_factory=dict) # path -> content_hash

@dataclass
class Transaction:
    transaction_id: str
    status: str = "ACTIVE"  # ACTIVE, COMMITTED, ROLLED_BACK
    updates: dict[str, str] = field(default_factory=dict) # file_path -> new_content

@dataclass
class Event:
    event_id: str
    event_type: str
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)
