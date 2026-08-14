"""
Canonical Security, Permissions, and Sandboxing Package.
"""

from .audit_logger import AuditLogger, AuditRecord
from .environment_isolation import EnvironmentIsolation
from .network_policy import NetworkMode, NetworkPolicyEngine
from .permission_engine import PermissionEngine
from .permission_model import ActionType, Permission, PermissionDecision, ResourceType, RiskLevel
from .prompt_injection_guard import PromptInjectionGuard
from .secret_redactor import SecretRedactor
from .terminal_sandbox import CommandAnalysisResult, TerminalSandbox
from .workspace_guard import WorkspaceGuard
from .secure_fs import SecureFileSystem
from .sandbox import SandboxManager, SandboxExecutor, ExecutionPolicy, ExecutionResult, ExecutionStatus, global_sandbox_manager

__all__ = [
    "PermissionEngine",
    "Permission",
    "PermissionDecision",
    "RiskLevel",
    "ActionType",
    "ResourceType",
    "WorkspaceGuard",
    "SecretRedactor",
    "EnvironmentIsolation",
    "TerminalSandbox",
    "CommandAnalysisResult",
    "NetworkPolicyEngine",
    "NetworkMode",
    "AuditLogger",
    "AuditRecord",
    "PromptInjectionGuard",
    "WorkspacePolicy",
    "Capability",
    "DEFAULT_EXCLUDE_DIRS",
    "SandboxManager",
    "SandboxExecutor",
    "ExecutionPolicy",
    "ExecutionResult",
    "ExecutionStatus",
    "global_sandbox_manager",
    "SecureFileSystem",
]
