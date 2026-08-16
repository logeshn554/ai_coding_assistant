"""
Permission Model & Risk Classification — Step 3, 4 requirements.

Defines canonical Permission data models, actions, resources, risk levels (LOW, MEDIUM, HIGH, CRITICAL),
and PermissionDecision records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionType(str, Enum):
    READ = "read"
    WRITE = "write"
    CREATE = "create"
    DELETE = "delete"
    EXECUTE = "execute"
    NETWORK = "network"
    GIT = "git"
    INSTALL = "install"
    SECRET_ACCESS = "secret_access"


class ResourceType(str, Enum):
    WORKSPACE = "workspace"
    FILE = "file"
    DIRECTORY = "directory"
    PROCESS = "process"
    NETWORK = "network"
    GIT_REPOSITORY = "git_repository"
    ENVIRONMENT = "environment"


@dataclass
class Permission:
    """Canonical permission object representing an action on a resource."""
    resource: ResourceType
    action: ActionType
    target: str
    risk: RiskLevel = RiskLevel.LOW
    scope: str = "workspace"  # workspace | session | global

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource.value,
            "action": self.action.value,
            "target": self.target,
            "risk": self.risk.value,
            "scope": self.scope,
        }


@dataclass
class PermissionDecision:
    """Outcome of a permission evaluation by PermissionEngine."""
    allowed: bool
    requires_approval: bool = False
    reason: str = ""
    permission: Permission | None = None
    risk_level: RiskLevel = RiskLevel.LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "reason": self.reason,
            "permission": self.permission.to_dict() if self.permission else None,
            "risk_level": self.risk_level.value,
        }
