"""
Canonical Permission Engine — Core security authority for AgentRuntime.

Enforces workspace boundary checks, secret redaction, command risk policies,
network allowlists, and execution modes (Strict, Assisted, Autonomous) with fail-closed semantics.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from .audit_logger import AuditLogger, AuditRecord
from .network_policy import NetworkMode, NetworkPolicyEngine
from .permission_model import ActionType, Permission, PermissionDecision, ResourceType, RiskLevel
from .secret_redactor import SecretRedactor
from .terminal_sandbox import TerminalSandbox
from .workspace_guard import WorkspaceGuard

logger = logging.getLogger("devpilot.security.permission_engine")


class PermissionEngine:
    """Canonical Security & Permission Engine."""

    _instances: Dict[str, "PermissionEngine"] = {}

    def __init__(self, workspace_root: str, mode: str = "Assisted") -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.mode = mode  # Strict | Assisted | Autonomous
        self.workspace_guard = WorkspaceGuard(self.workspace_root)
        self.terminal_sandbox = TerminalSandbox(self.workspace_root)
        self.network_policy = NetworkPolicyEngine(mode=NetworkMode.ALLOWLIST)
        self.audit_logger = AuditLogger()

    @classmethod
    def get_instance(cls, workspace_root: str, mode: str = "Assisted") -> "PermissionEngine":
        root = os.path.abspath(workspace_root)
        if root not in cls._instances:
            cls._instances[root] = cls(root, mode=mode)
        return cls._instances[root]

    def evaluate_tool_call(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> PermissionDecision:
        """Evaluate permission for any tool execution call with fail-closed security."""
        try:
            name = tool_name.lower().strip()

            # 1. Target file / directory validation
            target_path = arguments.get("path") or arguments.get("TargetFile") or arguments.get("file_path") or arguments.get("symbol")
            if target_path and isinstance(target_path, str):
                # Secret file check
                if SecretRedactor.is_secret_file(target_path):
                    record = AuditRecord(
                        session_id=session_id,
                        action="read_secret_file",
                        resource=target_path,
                        risk=RiskLevel.CRITICAL.value,
                        decision="DENIED",
                    )
                    self.audit_logger.log_record(record)
                    return PermissionDecision(allowed=False, reason=f"Access to protected secret file '{target_path}' is denied", risk_level=RiskLevel.CRITICAL)

                # Workspace boundary check
                if name in ("read_file", "write_file", "edit_file", "delete_file", "list_directory"):
                    if not self.workspace_guard.is_within_workspace(target_path):
                        record = AuditRecord(
                            session_id=session_id,
                            action=name,
                            resource=target_path,
                            risk=RiskLevel.HIGH.value,
                            decision="DENIED",
                        )
                        self.audit_logger.log_record(record)
                        return PermissionDecision(allowed=False, reason=f"Path traversal outside workspace blocked: '{target_path}'", risk_level=RiskLevel.HIGH)

            # 2. Command execution risk classification
            if name == "run_command":
                cmd = arguments.get("command") or arguments.get("CommandLine") or ""
                analysis = self.terminal_sandbox.analyze_command(cmd)

                if analysis.is_injection:
                    return PermissionDecision(allowed=False, reason=f"Command injection syntax blocked: '{cmd}'", risk_level=RiskLevel.CRITICAL)

                requires_approval = self._mode_requires_approval(analysis.risk)
                if requires_approval:
                    return PermissionDecision(allowed=True, requires_approval=True, reason=f"Command '{cmd}' requires user approval (Risk: {analysis.risk.value})", risk_level=analysis.risk)

            # 3. Mode-based tool action risk evaluation
            tool_risk = self._classify_tool_risk(name)
            requires_approval = self._mode_requires_approval(tool_risk)

            record = AuditRecord(
                session_id=session_id,
                action=name,
                resource=str(target_path or "workspace"),
                risk=tool_risk.value,
                decision="APPROVED" if not requires_approval else "PENDING_APPROVAL",
            )
            self.audit_logger.log_record(record)

            return PermissionDecision(
                allowed=True,
                requires_approval=requires_approval,
                reason=f"Tool '{name}' authorized under mode {self.mode}",
                risk_level=tool_risk,
            )

        except Exception as e:
            # Fail-closed security rule (Step 27 requirement)
            logger.error(f"Policy evaluation error for tool {tool_name}: {e}. Failing closed.")
            return PermissionDecision(allowed=False, reason=f"Security policy evaluation error: {e}", risk_level=RiskLevel.CRITICAL)

    def _classify_tool_risk(self, tool_name: str) -> RiskLevel:
        if tool_name in ("read_file", "search_files", "list_directory", "symbol_lookup", "git_status", "git_diff"):
            return RiskLevel.LOW
        elif tool_name in ("write_file", "edit_file", "create_file", "run_test"):
            return RiskLevel.MEDIUM
        elif tool_name in ("delete_file", "run_command"):
            return RiskLevel.HIGH
        elif tool_name in ("git_push", "force_push"):
            return RiskLevel.CRITICAL
        return RiskLevel.MEDIUM

    def _mode_requires_approval(self, risk: RiskLevel) -> bool:
        if self.mode == "Strict":
            return risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
        elif self.mode == "Assisted":
            return risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        elif self.mode == "Autonomous":
            return risk == RiskLevel.CRITICAL
        return risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
