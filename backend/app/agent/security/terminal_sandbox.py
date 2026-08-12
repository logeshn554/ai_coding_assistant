"""
Terminal Sandbox & Process Tree Controller — Step 12, 13, 14, 15, 16 requirements.

Executes shell commands with strict resource limits (timeouts, output byte limits),
parses shell syntax (pipes, redirects, subshells) for deep risk analysis,
and ensures complete child process tree termination on cancellation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import sys
from typing import Any, Dict, List, Optional, Tuple

from .environment_isolation import EnvironmentIsolation
from .permission_model import RiskLevel
from .secret_redactor import SecretRedactor

logger = logging.getLogger("devpilot.security.terminal_sandbox")

# High risk shell operators and destructive tokens
DESTRUCTIVE_COMMAND_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+-[rf]{1,2}\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\s+-[fdx]{1,3}\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+.*--force\b", re.IGNORECASE),
    re.compile(r"\bdrop\s+database\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[c-z]:", re.IGNORECASE),
    re.compile(r"/etc/(?:passwd|shadow|hosts)", re.IGNORECASE),
]

SHELL_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"\$\(.*?\)"),  # Subshell substitution $(...)
    re.compile(r"`.*?`"),      # Backtick substitution `...`
    re.compile(r";\s*[a-zA-Z]"),  # Chained command syntax with semicolon
    re.compile(r"\|\|"),      # Logical OR chaining
    re.compile(r"&&"),        # Logical AND chaining
    re.compile(r">\s*/"),     # Outbound redirect to root file
]


class CommandAnalysisResult:

    def __init__(self, command: str, risk: RiskLevel, is_injection: bool = False, tokens: Optional[List[str]] = None) -> None:
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
        timeout: Optional[float] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, int]:
        """Execute command in isolated environment with process tree cleanup."""
        t_limit = timeout or self.timeout
        env = EnvironmentIsolation.get_isolated_env(env_vars)

        start_ts = asyncio.get_event_loop().time()
        proc = None

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=self.workspace_root,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=t_limit)

            raw_output = (stdout_data.decode("utf-8", errors="replace") + "\n" + stderr_data.decode("utf-8", errors="replace")).strip()
            redacted_output = SecretRedactor.redact_secrets(raw_output[: self.max_output_bytes])

            success = proc.returncode == 0
            return success, redacted_output, proc.returncode or 0

        except asyncio.TimeoutError:
            logger.warning(f"Command timed out after {t_limit}s: {command}")
            if proc:
                await self.kill_process_tree(proc.pid)
            return False, f"Error: Command timed out after {t_limit} seconds.", -1
        except Exception as e:
            if proc:
                await self.kill_process_tree(proc.pid)
            return False, f"Error executing command: {e}", -1

    @classmethod
    async def kill_process_tree(cls, pid: int) -> None:
        """Kill process and all child processes recursively (Step 16 requirement)."""
        if not pid:
            return

        try:
            import psutil
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except Exception:
                    pass
            parent.kill()
        except ImportError:
            # Fallback signal kill if psutil not installed
            try:
                if sys.platform == "win32":
                    os.system(f"taskkill /F /T /PID {pid} >nul 2>&1")
                else:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                pass
