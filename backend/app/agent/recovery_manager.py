"""Phase 12 — Recovery Manager.

Structured retry and fallback logic for tool failures.
Prevents the agent from stopping on the first error.

Recovery strategy (in order):
  1. Parse the failure reason
  2. Apply a targeted fix (re-read file, adjust args, etc.)
  3. Retry with corrected approach
  4. Try an alternative tool (edit_file → write_file)
  5. Ask the user only if all automated recovery fails

Tracked failure patterns:
  - edit_file "Target block not found"   → re-read file then retry
  - edit_file "not unique"               → expand target block
  - write_file "permission denied"        → report error to user
  - run_terminal_command non-zero exit    → read error, form hypothesis, retry once
  - API timeout                          → retry with backoff
  - context too large                    → trim history, retry
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("devpilot.agent.recovery_manager")


# ── Failure signatures and their recovery strategies ────────────────────────

_EDIT_TARGET_NOT_FOUND = (
    "target block not found",
    "target not found",
    "could not find",
    "block not found",
    "no match",
    "differs starting at",
    "near-match was detected",
)

_EDIT_NOT_UNIQUE = (
    "not unique",
    "multiple occurrences",
    "ambiguous",
    "found more than one",
)

_PERMISSION_ERRORS = (
    "permission denied",
    "access denied",
    "read-only",
    "forbidden",
)

_TIMEOUT_ERRORS = (
    "timed out",
    "timeout",
    "connection timeout",
    "read timeout",
)

_CONTEXT_TOO_LARGE = (
    "context length",
    "too large",
    "token limit",
    "413",
    "maximum context",
)

_BUILD_ERRORS = (
    "error",
    "failed",
    "exit code",
    "non-zero",
    "traceback",
    "syntaxerror",
    "typeerror",
    "importerror",
    "modulenot",
)


class RecoveryDecision:
    """What the recovery manager recommends after a failure."""
    def __init__(
        self,
        strategy: str,
        should_retry: bool,
        alternative_tool: str | None,
        guidance: str,
        modified_args: dict | None = None,
    ):
        self.strategy = strategy
        self.should_retry = should_retry
        self.alternative_tool = alternative_tool
        self.guidance = guidance
        self.modified_args = modified_args or {}


class RecoveryManager:
    """Analyses tool failures and recommends recovery strategies.

    Usage:
        rm = RecoveryManager()
        decision = rm.analyse_failure("edit_file", args, result, retry_count=1)
        if decision.should_retry:
            # use decision.alternative_tool or decision.modified_args
        elif decision.strategy == "ask_user":
            # emit a clarification request
    """

    def __init__(self):
        self._edit_fail_counts: dict[str, int] = {}  # path → count

    def analyse_failure(
        self,
        tool_name: str,
        args: dict,
        error_output: str,
        retry_count: int = 0,
    ) -> RecoveryDecision:
        """Analyse a tool failure and decide what to do next.

        Args:
            tool_name: The name of the tool that failed.
            args: The arguments the tool was called with.
            error_output: The error text / result from the tool.
            retry_count: How many times this tool has been retried already.

        Returns:
            RecoveryDecision with strategy and guidance.
        """
        err_lower = error_output.lower()

        # ── edit_file failures ───────────────────────────────────────────
        if tool_name in ("edit_file", "patch"):
            if any(sig in err_lower for sig in _EDIT_TARGET_NOT_FOUND):
                if retry_count == 0:
                    return RecoveryDecision(
                        strategy="reread_and_retry",
                        should_retry=True,
                        alternative_tool=None,
                        guidance=(
                            "The target block was not found. Re-read the file NOW to get the "
                            "exact current content, then retry edit_file with the correct target. "
                            "Check for whitespace or newline differences."
                        ),
                    )
                else:
                    path = args.get("path", "unknown")
                    self._edit_fail_counts[path] = self._edit_fail_counts.get(path, 0) + 1
                    return RecoveryDecision(
                        strategy="fallback_write_file",
                        should_retry=True,
                        alternative_tool="write_file",
                        guidance=(
                            f"edit_file has failed {retry_count + 1} times on '{path}'. "
                            "Fall back to write_file: re-read the file, apply the change manually "
                            "to the full content, and write the complete file with write_file."
                        ),
                    )

            if any(sig in err_lower for sig in _EDIT_NOT_UNIQUE):
                return RecoveryDecision(
                    strategy="expand_target",
                    should_retry=True,
                    alternative_tool=None,
                    guidance=(
                        "The target block matches multiple locations. Expand the target to include "
                        "more surrounding context (2-3 additional lines) to make it unique, then retry."
                    ),
                )

        # ── Permission errors (non-retryable) ────────────────────────────
        if any(sig in err_lower for sig in _PERMISSION_ERRORS):
            return RecoveryDecision(
                strategy="ask_user",
                should_retry=False,
                alternative_tool=None,
                guidance=(
                    f"Permission denied accessing the file. The workspace or file may be read-only. "
                    "Check file permissions before continuing."
                ),
            )

        # ── Terminal command failures ─────────────────────────────────────
        if tool_name == "run_terminal_command":
            if any(sig in err_lower for sig in _BUILD_ERRORS):
                if retry_count == 0:
                    return RecoveryDecision(
                        strategy="read_error_and_fix",
                        should_retry=True,
                        alternative_tool=None,
                        guidance=(
                            "The command failed with an error. Read the full error output carefully. "
                            "Form ONE specific hypothesis about the root cause. Make ONE targeted change "
                            "to fix it. Then re-run the command. Do NOT re-run the same command unchanged."
                        ),
                    )
                elif retry_count == 1:
                    return RecoveryDecision(
                        strategy="change_approach",
                        should_retry=True,
                        alternative_tool=None,
                        guidance=(
                            "The command has failed twice with the same approach. "
                            "Change strategy: try a different command, fix a different aspect of the code, "
                            "or check if the issue is in a dependency rather than your code."
                        ),
                    )
                else:
                    return RecoveryDecision(
                        strategy="ask_user",
                        should_retry=False,
                        alternative_tool=None,
                        guidance=(
                            f"The command has failed {retry_count + 1} times. "
                            "Report the exact error to the user and ask for guidance."
                        ),
                    )

            if any(sig in err_lower for sig in _TIMEOUT_ERRORS):
                if retry_count == 0:
                    return RecoveryDecision(
                        strategy="retry_after_wait",
                        should_retry=True,
                        alternative_tool=None,
                        guidance=(
                            "The command timed out. This may be expected for long-running operations "
                            "(npm install, build). Check if the process completed successfully by "
                            "listing the output directory or reading a log file before retrying."
                        ),
                    )

        # ── write_file failures ──────────────────────────────────────────
        if tool_name == "write_file":
            if retry_count < 2:
                return RecoveryDecision(
                    strategy="retry",
                    should_retry=True,
                    alternative_tool=None,
                    guidance="write_file failed. Check that the path is valid and within the workspace, then retry.",
                )

        # ── Generic: too many retries → ask user ─────────────────────────
        if retry_count >= 3:
            return RecoveryDecision(
                strategy="ask_user",
                should_retry=False,
                alternative_tool=None,
                guidance=(
                    f"Tool '{tool_name}' has failed {retry_count + 1} times. "
                    "Report the situation to the user clearly and ask for guidance."
                ),
            )

        # ── Default: retry once ──────────────────────────────────────────
        return RecoveryDecision(
            strategy="retry",
            should_retry=retry_count < 1,
            alternative_tool=None,
            guidance=f"Tool '{tool_name}' failed: {error_output[:300]}. Try a different approach.",
        )

    def to_prompt_injection(self, decision: RecoveryDecision) -> str:
        """Format a recovery decision as a prompt injection for the LLM."""
        return (
            f"\n\n[RECOVERY GUIDANCE — {decision.strategy.upper()}]\n"
            f"{decision.guidance}\n"
            + (f"Consider using: {decision.alternative_tool}\n" if decision.alternative_tool else "")
        )
