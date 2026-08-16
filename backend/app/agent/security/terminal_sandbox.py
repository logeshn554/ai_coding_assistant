"""
Terminal Sandbox & Process Tree Controller — Step 12, 13, 14, 15, 16 requirements.

Executes shell commands with strict resource limits (timeouts, output byte limits),
parses shell syntax (pipes, redirects, subshells) for deep risk analysis,
and ensures complete child process tree termination on cancellation.
"""

from __future__ import annotations

import logging
import os
import re

from .permission_model import RiskLevel

logger = logging.getLogger("devpilot.security.terminal_sandbox")

# High risk shell operators and destructive tokens
DESTRUCTIVE_COMMAND_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\s+-[rf]{1,2}\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\s+-[fdx]{1,3}\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+.*--force\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[c-z]:", re.IGNORECASE),
]

SHELL_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\$\(.*?\)"),  # Subshell substitution $(...)
    re.compile(r"`.*?`"),      # Backtick substitution `...`
    re.compile(r";\s*[a-zA-Z]"),  # Chained command syntax with semicolon
    re.compile(r"\|\|"),      # Logical OR chaining
    re.compile(r"&&"),        # Logical AND chaining
    re.compile(r">\s*/"),     # Outbound redirect to root file
    re.compile(r"/etc/(?:passwd|shadow|hosts)", re.IGNORECASE),
]

# Commands that attempt to access secret/credential files through the terminal.
# These are CRITICAL risk regardless of execution mode — blocked before execution.
# This closes the gap where file-API secret protection does not cover the shell.
SECRET_FILE_ACCESS_PATTERNS: list[re.Pattern] = [
    # Direct reads of secret files
    re.compile(r"\bcat\b.*\.(env|key|pem|crt|cer|p12|pfx|jks|keystore|secret)\b", re.IGNORECASE),
    re.compile(r"\btype\b.*\.(env|key|pem|crt|cer|p12|pfx|jks|keystore|secret)\b", re.IGNORECASE),
    re.compile(r"\bless\b.*\.(env|key|pem|crt|cer|p12|pfx|jks|keystore|secret)\b", re.IGNORECASE),
    re.compile(r"\bmore\b.*\.(env|key|pem|crt|cer|p12|pfx|jks|keystore|secret)\b", re.IGNORECASE),
    re.compile(r"\bhead\b.*\.(env|key|pem|crt|cer|p12|pfx|jks|keystore|secret)\b", re.IGNORECASE),
    re.compile(r"\btail\b.*\.(env|key|pem|crt|cer|p12|pfx|jks|keystore|secret)\b", re.IGNORECASE),
    re.compile(r"\bnano\b.*\.(env|key|pem|crt)\b", re.IGNORECASE),
    re.compile(r"\bvim?\b.*\.(env|key|pem|crt)\b", re.IGNORECASE),
    # Explicit .env file reads (with or without extension)
    re.compile(r"\bcat\b.*[/\\]\.env\b", re.IGNORECASE),
    re.compile(r"\bcat\s+\.env\b", re.IGNORECASE),
    # Environment variable dumps that expose secrets
    re.compile(r"\bprintenv\b", re.IGNORECASE),
    re.compile(r"\benv\b\s*$"),             # bare `env` command
    re.compile(r"\bset\b\s*$"),             # bare `set` command
    re.compile(r"\bexport\b\s+-p\b"),       # export -p dumps all vars
    # /proc memory reads (linux credential theft)
    re.compile(r"/proc/\d+/(mem|environ|maps)", re.IGNORECASE),
    re.compile(r"/proc/self/(mem|environ|maps)", re.IGNORECASE),
    # SSH key access
    re.compile(r"\bcat\b.*\.ssh/", re.IGNORECASE),
    re.compile(r"\bcat\b.*(id_rsa|id_ecdsa|id_ed25519|authorized_keys)", re.IGNORECASE),
    # AWS/GCP/Azure credential files
    re.compile(r"\bcat\b.*\.aws/(credentials|config)\b", re.IGNORECASE),
    re.compile(r"\bcat\b.*\.config/gcloud/", re.IGNORECASE),
    # History files that may contain secrets
    re.compile(r"\bcat\b.*\.(bash_history|zsh_history|history)\b", re.IGNORECASE),
]


class CommandAnalysisResult:

    def __init__(self, command: str, risk: RiskLevel, is_injection: bool = False, tokens: list[str] | None = None) -> None:
        self.command = command
        self.risk = risk
        self.is_injection = is_injection
        self.tokens = tokens or []


class TerminalSandbox:
    """Executes commands safely inside a bounded process sandbox."""

    def __init__(self, workspace_root: str, max_output_bytes: int = 1_000_000, timeout: float = 120.0) -> None:
        self.workspace_root = workspace_root
        self.max_output_bytes = max_output_bytes
        self.timeout = timeout

    @classmethod
    def analyze_command(cls, command: str) -> CommandAnalysisResult:
        """Perform deep AST/regex shell analysis on pipes, subshells, and chained syntax."""
        cmd_str = command.strip()
        risk = RiskLevel.LOW
        is_injection = False

        # 0. Secret file access check — CRITICAL, blocked immediately.
        # Must run before injection check so the risk level is set correctly.
        for pat in SECRET_FILE_ACCESS_PATTERNS:
            if pat.search(cmd_str):
                logger.warning(f"Secret file access attempt blocked: '{cmd_str}'")
                return CommandAnalysisResult(command=cmd_str, risk=RiskLevel.CRITICAL, is_injection=True)

        # 1. Shell Injection & Subshell Check
        for pat in SHELL_INJECTION_PATTERNS:
            if pat.search(cmd_str):
                is_injection = True
                risk = RiskLevel.HIGH
                break

        # 2. Destructive Command Check
        for pat in DESTRUCTIVE_COMMAND_PATTERNS:
            if pat.search(cmd_str):
                risk = RiskLevel.CRITICAL
                break

        # 3. Medium risk operations (installs, write scripts)
        if risk == RiskLevel.LOW:
            if any(kw in cmd_str.lower() for kw in ["npm install", "pip install", "yarn add", "pnpm add", "cargo add"]):
                risk = RiskLevel.MEDIUM
            elif any(kw in cmd_str.lower() for kw in ["git push", "git commit"]):
                risk = RiskLevel.HIGH

        return CommandAnalysisResult(command=cmd_str, risk=risk, is_injection=is_injection)


    async def execute_sandboxed_command(
        self,
        command: str,
        timeout: float | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> tuple[bool, str, int]:
        """Execute command in isolated environment with process tree cleanup."""
        analysis = self.analyze_command(command)
        if analysis.is_injection:
            return False, f"Command blocked by security policy: shell injection syntax detected in '{command}'", 126
        if analysis.risk == RiskLevel.CRITICAL:
            return False, f"Command blocked by security policy: critical risk command '{command}'", 126

        import uuid

        from backend.app.agent.security.sandbox import (
            ExecutionPolicy,
            ExecutionStatus,
            global_sandbox_manager,
        )
        t_limit = timeout or self.timeout
        policy = ExecutionPolicy(
            workspace_root=self.workspace_root,
            max_runtime_seconds=t_limit,
            environment_policy=env_vars or {}
        )
        
        exec_id = uuid.uuid4().hex[:12]
        ws_id = os.path.basename(self.workspace_root.rstrip("\\/")) or "ws"
        try:
            sandbox = await global_sandbox_manager.get_or_create(
                workspace_id=ws_id,
                run_id=f"run_{exec_id}",
                policy=policy
            )
            res = await sandbox.execute(command, timeout=t_limit, environment=env_vars)
            success = (res.status == ExecutionStatus.SUCCESS)
            return success, res.combined_output, res.exit_code
        except Exception as e:
            return False, f"Error executing command: {e}", -1

    @classmethod
    async def kill_process_tree(cls, pid: int) -> None:
        """Kill process and all child processes recursively (Step 16 requirement)."""
        from backend.app.processes import kill_process_tree
        kill_process_tree(pid)
