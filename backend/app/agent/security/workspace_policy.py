"""
Workspace Policy Engine — Single source of truth for workspace boundary rules,
exclusions, capability permissions, file limits, and execution policies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class Capability(str, Enum):
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    TERMINAL_EXEC = "terminal.exec"
    TERMINAL_EXEC_PRIVILEGED = "terminal.exec_privileged"
    NETWORK_FETCH = "network.fetch"


DEFAULT_EXCLUDE_DIRS: set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".devpilot",
    "dist",
    "build",
    ".pytest_cache",
}

DEFAULT_EXCLUDE_FILES: set[str] = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_rsa.pub",
}


@dataclass
class WorkspacePolicy:
    """Canonical Workspace Security & Operation Policy."""

    workspace_root: str
    exclude_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_DIRS))
    exclude_files: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_FILES))
    max_file_size_bytes: int = 10_000_000  # 10 MB
    max_output_bytes: int = 1_000_000       # 1 MB
    default_command_timeout: float = 60.0    # 60s
    allowed_capabilities: set[Capability] = field(
        default_factory=lambda: {
            Capability.FILESYSTEM_READ,
            Capability.FILESYSTEM_WRITE,
            Capability.FILESYSTEM_DELETE,
            Capability.TERMINAL_EXEC,
            Capability.NETWORK_FETCH,
        }
    )

    def is_excluded_directory(self, dir_name: str) -> bool:
        """Check if directory name is in exclusion policy."""
        return dir_name in self.exclude_dirs

    def is_excluded_file(self, file_name: str) -> bool:
        """Check if filename matches protected secret or excluded file policy."""
        name = os.path.basename(file_name)
        return name in self.exclude_files or name.startswith(".env")

    def has_capability(self, capability: Capability) -> bool:
        """Check if requested capability is permitted by policy."""
        return capability in self.allowed_capabilities

    def validate_capability(self, capability: Capability) -> None:
        """Raise PermissionError if capability is not allowed."""
        if not self.has_capability(capability):
            raise PermissionError(f"Capability '{capability.value}' is denied under active WorkspacePolicy.")
