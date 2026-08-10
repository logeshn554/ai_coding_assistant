from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Capability:
    name: str
    description: str = ""

@dataclass
class Agent:
    agent_id: str
    agent_type: str
    status: str = "idle"
    capabilities: List[Capability] = field(default_factory=list)

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
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    budget: Optional[Budget] = None

@dataclass
class Action:
    action_id: str
    action_type: str  # read_file, write_file, run_command, etc.
    target: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "PENDING"  # PENDING, APPROVED, DENIED, SUCCESS, ERROR

@dataclass
class Resource:
    name: str
    resource_type: str  # file, directory, network, process
    path: Optional[str] = None

@dataclass
class Policy:
    name: str
    policy_type: str
    rules: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Permission:
    agent_type: str
    resource: Resource
    access_level: str  # read, write, execute, all

@dataclass
class Checkpoint:
    checkpoint_id: str
    timestamp: float
    file_snapshots: Dict[str, str] = field(default_factory=dict) # path -> content_hash

@dataclass
class Transaction:
    transaction_id: str
    status: str = "ACTIVE"  # ACTIVE, COMMITTED, ROLLED_BACK
    updates: Dict[str, str] = field(default_factory=dict) # file_path -> new_content

@dataclass
class Event:
    event_id: str
    event_type: str
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)
