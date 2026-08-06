"""
Kernel Policy Engine — Enforces tool allowlists/denylists and sandboxed file-path constraints.

Supports:
  - Role-based and agent-type-based tool authorization
  - Directory path scoping (sandbox boundary validation)
  - Write vs. Read permissions validation
  - Risk-level checks for commands
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from agent_os.kernel.interfaces import IKernelService

logger = logging.getLogger("agentos.kernel.policy_engine")


class PolicyEngine(IKernelService):
    """Enforces execution policies, sandboxing, and tool allowlists per agent type."""

    def __init__(self, workspace_root: str = "") -> None:
        self._workspace_root = workspace_root
        
        # Tool allowlists per agent type
        self._agent_tool_allowlists: Dict[str, Set[str]] = {
            "code": {"read_file", "write_file", "edit_file", "grep_search", "list_dir", "run_terminal_command"},
            "test": {"read_file", "run_terminal_command", "list_dir"},
            "review": {"read_file", "grep_search", "list_dir"},
            "security": {"read_file", "grep_search", "list_dir"},
            "docs": {"read_file", "write_file", "edit_file", "list_dir"},
            "planner": {"read_file", "list_dir", "grep_search"},
            "architect": {"read_file", "list_dir", "grep_search"},
            "git": {"read_file", "run_terminal_command", "list_dir"},
            "terminal": {"run_terminal_command", "list_dir"},
        }

        # Global denylist of tools
        self._global_tool_denylist: Set[str] = set()

        # Restricted directories (even inside workspace root)
        self._restricted_subdirs: Set[str] = {
            ".git", ".env", "node_modules", "venv", ".venv", "__pycache__"
        }

    def on_init(self) -> None:
        logger.info("Initializing PolicyEngine service")

    def on_shutdown(self) -> None:
        logger.info("Shutting down PolicyEngine service")

    @property
    def workspace_root(self) -> str:
        return self._workspace_root

    @workspace_root.setter
    def workspace_root(self, root: str) -> None:
        self._workspace_root = root

    def set_agent_tool_policy(self, agent_type: str, allowed_tools: Set[str]) -> None:
        """Define which tools a specific agent type is allowed to call."""
        self._agent_tool_allowlists[agent_type] = allowed_tools

    def set_global_tool_denylist(self, blacklisted_tools: Set[str]) -> None:
        """Define tools that can never be executed under any policy."""
        self._global_tool_denylist = blacklisted_tools

    def is_tool_allowed(self, agent_type: str, tool_name: str) -> bool:
        """Check if a tool is permitted for the given agent type."""
        if tool_name in self._global_tool_denylist:
            logger.warning(f"Tool blocked: '{tool_name}' is globally blacklisted.")
            return False

        # If agent type is unknown, default to a safe read-only policy
        allowed_tools = self._agent_tool_allowlists.get(agent_type)
        if allowed_tools is None:
            # Fallback safe policies
            return tool_name in {"read_file", "list_dir", "grep_search"}

        # Check explicit tool allowlist
        if tool_name not in allowed_tools:
            logger.warning(f"Tool blocked: Agent '{agent_type}' is not allowed to run '{tool_name}'")
            return False

        return True

    def is_path_safe(self, path_str: str, write_requested: bool = False) -> bool:
        """Check if a path is safe and within sandboxed boundaries."""
        if not self._workspace_root:
            # If no workspace root is configured, allow all path checks (local development fallback)
            return True

        try:
            target_path = Path(path_str).resolve()
            root_path = Path(self._workspace_root).resolve()

            # 1. Enforce sandbox boundary (must be inside workspace root)
            if not str(target_path).startswith(str(root_path)):
                logger.warning(f"Sandbox violation: Target path '{path_str}' is outside workspace root '{self._workspace_root}'")
                return False

            # 2. Block restricted directory structures (e.g. modifying git metadata or virtual environments)
            parts = target_path.relative_to(root_path).parts
            for part in parts:
                if part in self._restricted_subdirs:
                    if write_requested:
                        logger.warning(f"Path access blocked: Write requested to restricted directory part '{part}' in '{path_str}'")
                        return False

            return True
        except Exception as e:
            logger.error(f"Error validating path safety for '{path_str}': {e}")
            return False


# ── Singleton ───────────────────────────────────────────────────────────────

policy_engine = PolicyEngine()
