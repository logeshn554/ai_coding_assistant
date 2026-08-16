import re
import hashlib
from enum import Enum
from typing import Dict, List, Tuple, Set, Optional

# Permission Capability Categories
class Capability(str, Enum):
    READ_FILES = "READ_FILES"
    WRITE_FILES = "WRITE_FILES"
    DELETE_FILES = "DELETE_FILES"
    RUN_COMMAND = "RUN_COMMAND"
    INSTALL_PACKAGE = "INSTALL_PACKAGE"
    NETWORK = "NETWORK"
    BROWSER = "BROWSER"
    DATABASE = "DATABASE"
    GIT = "GIT"
    GIT_PUSH = "GIT_PUSH"
    REMOTE_ACCESS = "REMOTE_ACCESS"
    SECRETS = "SECRETS"
    SYSTEM = "SYSTEM"

# Policy Presets
POLICY_SAFE = "Safe"
POLICY_BALANCED = "Balanced"
POLICY_AUTONOMOUS = "Autonomous"
POLICY_CUSTOM = "Custom"

# Scopes (backwards compatible)
SCOPE_ONCE = "once"
SCOPE_SESSION = "session"
SCOPE_PROJECT = "project"
SCOPE_DENIED = "deny"

# Command Risk Categories (backwards compatible)
RISK_SAFE = "safe"
RISK_MUTATIVE = "mutative"
RISK_DESTRUCTIVE = "destructive"

DEFAULT_POLICY_MATRIX: Dict[str, Dict[str, bool]] = {
    POLICY_SAFE: {
        Capability.READ_FILES: True,
        Capability.WRITE_FILES: False,
        Capability.DELETE_FILES: False,
        Capability.RUN_COMMAND: False,
        Capability.INSTALL_PACKAGE: False,
        Capability.NETWORK: False,
        Capability.BROWSER: True,
        Capability.DATABASE: False,
        Capability.GIT: True,
        Capability.GIT_PUSH: False,
        Capability.REMOTE_ACCESS: False,
        Capability.SECRETS: False,
        Capability.SYSTEM: False,
    },
    POLICY_BALANCED: {
        Capability.READ_FILES: True,
        Capability.WRITE_FILES: True,
        Capability.DELETE_FILES: False,
        Capability.RUN_COMMAND: True,
        Capability.INSTALL_PACKAGE: False,
        Capability.NETWORK: True,
        Capability.BROWSER: True,
        Capability.DATABASE: True,
        Capability.GIT: True,
        Capability.GIT_PUSH: False,
        Capability.REMOTE_ACCESS: False,
        Capability.SECRETS: False,
        Capability.SYSTEM: False,
    },
    POLICY_AUTONOMOUS: {
        Capability.READ_FILES: True,
        Capability.WRITE_FILES: True,
        Capability.DELETE_FILES: False,
        Capability.RUN_COMMAND: True,
        Capability.INSTALL_PACKAGE: True,
        Capability.NETWORK: True,
        Capability.BROWSER: True,
        Capability.DATABASE: True,
        Capability.GIT: True,
        Capability.GIT_PUSH: False,
        Capability.REMOTE_ACCESS: True,
        Capability.SECRETS: False,
        Capability.SYSTEM: False,
    }
}

class PermissionManager:
    """Centralized Permission Engine enforcing security boundaries across all IDE tools and agents."""

    def __init__(self, config_manager, workspace_root: str):
        self.config_manager = config_manager
        self._workspace_root = workspace_root
        self.session_permissions: Set[str] = set()
        self.active_policy: str = POLICY_BALANCED
        self.custom_overrides: Dict[str, bool] = {}

    @property
    def workspace_root(self) -> str:
        if self._workspace_root:
            return self._workspace_root
        try:
            from .state import workspace_state
            return workspace_state.root
        except Exception:
            return ""

    @workspace_root.setter
    def workspace_root(self, val: str) -> None:
        self._workspace_root = val

    def set_policy(self, policy_name: str, custom_matrix: Optional[Dict[str, bool]] = None):
        """Sets the active security policy mode."""
        if policy_name in [POLICY_SAFE, POLICY_BALANCED, POLICY_AUTONOMOUS, POLICY_CUSTOM]:
            self.active_policy = policy_name
            if custom_matrix:
                self.custom_overrides = custom_matrix

    def check_capability(self, capability: Capability, details: str = "") -> Tuple[bool, str]:
        """Checks whether a specific agent capability is allowed under the current policy."""
        # 1. Custom Overrides
        if capability.value in self.custom_overrides:
            allowed = self.custom_overrides[capability.value]
            return allowed, f"Custom policy override for {capability.value}: {'Allowed' if allowed else 'Denied'}"

        # 2. Preset Matrix
        matrix = DEFAULT_POLICY_MATRIX.get(self.active_policy, DEFAULT_POLICY_MATRIX[POLICY_BALANCED])
        allowed = matrix.get(capability.value, False)

        if allowed:
            return True, f"Allowed under {self.active_policy} policy."
        else:
            return False, f"Capability {capability.value} requires user approval under {self.active_policy} policy."

    def _get_project_id(self) -> str:
        if not self.workspace_root:
            return "global"
        return hashlib.sha256(self.workspace_root.encode("utf-8")).hexdigest()

    def _get_command_pattern(self, command: str) -> str:
        if not command or not isinstance(command, str):
            return ""
        return command.strip().replace("\\", "/")

    def get_command_risk(self, command: str) -> str:
        if not command or not isinstance(command, str) or not command.strip():
            raise ValueError("A non-empty command is required.")
        cmd = command.strip().lower()
        
        destructive_patterns = [
            r"\brm\s+-[a-z]*r[a-z]*f\b",
            r"\brm\s+-[a-z]*f[a-z]*r\b",
            r"\bgit\s+reset\s+--hard\b",
            r"\bgit\s+clean\s+-[a-z]*f\b",
            r"\bdrop\s+(table|database|schema)\b",
            r"\bformat\s+[a-z]:",
            r"\bdel\s+/[fsq]\b",
            r"\brd\s+/[sq]\b",
            r"\bremove-item\b.*-force\b",
            r"\bdd\s+if=",
            r"\bmkfs\b",
            r"\btruncate\s+table\b",
            r"\b(curl|wget)\b.*\b(sh|bash|powershell|pwsh)\b",
            r"\|\s*(sh|bash|powershell|pwsh)\b",
            r":\(\)\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
            r">\s*.*\.ssh/authorized_keys",
            r">\s*.*etc/passwd",
            r">\s*.*\.(bashrc|bash_profile|zshrc|profile|profile_history)",
        ]
        if any(re.search(pat, cmd) for pat in destructive_patterns):
            return RISK_DESTRUCTIVE
            
        safe_patterns = [
            r"^pwd$", r"^ls\b", r"^dir\b", r"^echo\b", r"^cat\b", r"^type\b",
            r"^git status\b", r"^git diff\b", r"^git branch\b", r"^git log\b"
        ]
        if any(re.search(pat, cmd) for pat in safe_patterns):
            return RISK_SAFE
            
        return RISK_MUTATIVE

    def check_permission(self, command: str) -> Tuple[bool, str, str]:
        """Checks if a terminal command is approved under risk and policy criteria."""
        risk = self.get_command_risk(command)
        cmd_pattern = self._get_command_pattern(command)

        if risk == RISK_DESTRUCTIVE:
            return False, risk, "This command is destructive and always requires explicit user confirmation."

        if cmd_pattern in self.session_permissions:
            return True, risk, "Approved for this session."

        project_id = self._get_project_id()
        project_perms = self.config_manager.get_project_permissions(project_id)
        if cmd_pattern in project_perms:
            return True, risk, "Approved for this project."

        # Check policy capability
        allowed, reason = self.check_capability(Capability.RUN_COMMAND, command)
        if allowed:
            return True, risk, reason

        return False, risk, "This command requires user authorization."

    def grant_permission(self, command: str, scope: str):
        cmd_pattern = self._get_command_pattern(command)
        if scope == SCOPE_SESSION:
            self.session_permissions.add(cmd_pattern)
        elif scope == SCOPE_PROJECT:
            project_id = self._get_project_id()
            self.config_manager.add_project_permission(project_id, cmd_pattern)

    def revoke_project_permission(self, command: str):
        cmd_pattern = self._get_command_pattern(command)
        project_id = self._get_project_id()
        self.config_manager.remove_project_permission(project_id, cmd_pattern)