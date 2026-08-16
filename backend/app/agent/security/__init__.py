"""
Canonical Security, Permissions, and Sandboxing Package.
"""

from .audit_logger import AuditLogger, AuditRecord
from .environment_isolation import EnvironmentIsolation
from .network_policy import NetworkMode, NetworkPolicyEngine
from .permission_engine import PermissionEngine
from .permission_model import (
    ActionType,
    Permission,
    PermissionDecision,
    ResourceType,
    RiskLevel,
)
from .prompt_injection_guard import PromptInjectionGuard
from .sandbox import (
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    SandboxExecutor,
    SandboxManager,
    global_sandbox_manager,
)
from .secret_redactor import SecretRedactor
from .secure_fs import SecureFileSystem
from .terminal_sandbox import CommandAnalysisResult, TerminalSandbox
from .workspace_guard import WorkspaceGuard
from .workspace_policy import DEFAULT_EXCLUDE_DIRS, Capability, WorkspacePolicy

__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "ActionType",
    "AuditLogger",
    "AuditRecord",
    "Capability",
    "CommandAnalysisResult",
    "EnvironmentIsolation",
    "ExecutionPolicy",
    "ExecutionResult",
    "ExecutionStatus",
    "NetworkMode",
    "NetworkPolicyEngine",
    "Permission",
    "PermissionDecision",
    "PermissionEngine",
    "PromptInjectionGuard",
    "ResourceType",
    "RiskLevel",
    "SandboxExecutor",
    "SandboxManager",
    "SecretRedactor",
    "SecureFileSystem",
    "TerminalSandbox",
    "WorkspaceGuard",
    "WorkspacePolicy",
    "global_sandbox_manager",
]
