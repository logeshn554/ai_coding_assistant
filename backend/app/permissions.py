import re
import hashlib
from typing import Dict, List, Tuple

# Scopes
SCOPE_ONCE = "once"
SCOPE_SESSION = "session"
SCOPE_PROJECT = "project"
SCOPE_DENIED = "deny"

# Command Risk Categories
RISK_SAFE = "safe"
RISK_MUTATIVE = "mutative"
RISK_DESTRUCTIVE = "destructive"

class PermissionManager:
    def __init__(self, config_manager, workspace_root: str):
        self.config_manager = config_manager
        self._workspace_root = workspace_root
        self.session_permissions = set()  # set of command hashes approved for this session

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

    def _get_project_id(self) -> str:
        # Use workspace root path to uniquely identify the project
        if not self.workspace_root:
            return "global"
        return hashlib.md5(self.workspace_root.encode("utf-8")).hexdigest()

    def _get_command_pattern(self, command: str) -> str:
        # Normalize command (strip extra whitespace, normalize slash direction, etc.)
        if not command or not isinstance(command, str):
            return ""
        cmd = command.strip().replace("\\", "/")
        return cmd

    def get_command_risk(self, command: str) -> str:
        if not command or not isinstance(command, str) or not command.strip():
            raise ValueError("A non-empty command is required.")
        cmd = command.strip().lower()
        
        # Destructive patterns (commands that cause irreversible loss or mass deletion)
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
            # Remote code execution / piping web inputs into interpreters
            r"\b(curl|wget)\b.*\b(sh|bash|powershell|pwsh)\b",
            r"\|\s*(sh|bash|powershell|pwsh)\b",
            # Fork bombs
            r":\(\)\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
            # Destructive redirects to core system/auth files
            r">\s*.*\.ssh/authorized_keys",
            r">\s*.*etc/passwd",
            r">\s*.*\.(bashrc|bash_profile|zshrc|profile|profile_history)",
        ]
        if any(re.search(pat, cmd) for pat in destructive_patterns):
            return RISK_DESTRUCTIVE
            
        # Safe patterns (purely read-only / information queries)
        safe_patterns = [
            r"^pwd$", r"^ls\b", r"^dir\b", r"^echo\b", r"^cat\b", r"^type\b",
            r"^git status\b", r"^git diff\b", r"^git branch\b", r"^git log\b"
        ]
        if any(re.search(pat, cmd) for pat in safe_patterns):
            return RISK_SAFE
            
        # Everything else is mutative (compiles, installs, writes, etc.)
        return RISK_MUTATIVE

    def check_permission(self, command: str) -> Tuple[bool, str, str]:
        """
        Checks if a command is approved.
        Returns (is_approved, risk_level, reason)
        """
        risk = self.get_command_risk(command)
        cmd_pattern = self._get_command_pattern(command)

        # Destructive commands ALWAYS require confirmation
        if risk == RISK_DESTRUCTIVE:
            return False, risk, "This command is destructive and always requires explicit user confirmation."

        # Check in-memory session permissions
        if cmd_pattern in self.session_permissions:
            return True, risk, "Approved for this session."

        # Check project-persistent permissions
        project_id = self._get_project_id()
        project_perms = self.config_manager.get_project_permissions(project_id)
        if cmd_pattern in project_perms:
            return True, risk, "Approved for this project."

        # Otherwise, needs confirmation
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
