"""Phase 9 — Critic.

Self-review pass that runs after the main execution loop.
Asks: "Did I actually solve the request? Should I continue?"

The critic uses a lightweight rule-based check first (no LLM call).
If the rule-based check is inconclusive, it optionally triggers an LLM call.

Critic rules:
  - Files mentioned in the plan were NOT created → incomplete
  - Validation failures exist → incomplete
  - Response only contains text but no tool calls were made for an action intent → suspicious
  - The agent stopped at turn 1 on a complex request → suspicious
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .intent_router import IntentType
from .task_memory import TaskMemory
from .validator import ValidationResult

logger = logging.getLogger("loopix.agent.critic")


@dataclass
class CriticResult:
    complete: bool
    should_continue: bool    # True → keep the loop going
    reason: str              # Human-readable explanation
    injected_message: str    # Text to inject into LLM context if should_continue

    def to_prompt_block(self) -> str:
        if self.complete:
            return ""
        return (
            f"\n[CRITIC REVIEW]\n"
            f"Status: {'Incomplete' if not self.complete else 'Complete'}\n"
            f"Reason: {self.reason}\n"
            f"{self.injected_message}\n"
        )


class Critic:
    """Rule-based self-review component.

    Usage:
        critic = Critic()
        result = critic.review(
            intent, task_memory, validation_result, total_turns, response_text
        )
        if result.should_continue:
            # inject result.to_prompt_block() and run another LLM turn
    """

    def review(
        self,
        intent: IntentType,
        task_memory: TaskMemory,
        validation_result: ValidationResult | None,
        total_turns: int,
        response_text: str,
        tool_calls_made: int,
    ) -> CriticResult:
        """Run the critic pass.

        Args:
            intent: The classified intent type.
            task_memory: Current task state.
            validation_result: Output from Validator (None if not run yet).
            total_turns: Number of LLM turns used so far.
            response_text: The agent's last text response.
            tool_calls_made: Total tool calls in this session.

        Returns:
            CriticResult indicating whether the task is complete.
        """

        # ── Rule 1: Validation failures → always incomplete ───────────────
        if validation_result and not validation_result.passed:
            failures_summary = "; ".join(validation_result.failures[:3])
            return CriticResult(
                complete=False,
                should_continue=True,
                reason=f"Validation failed: {failures_summary}",
                injected_message=(
                    f"The validator found {len(validation_result.failures)} failure(s):\n"
                    + "\n".join(f"  - {f}" for f in validation_result.failures)
                    + "\n\nFix these issues now and ensure all required files exist."
                ),
            )

        # ── Rule 2: Task memory has incomplete steps ──────────────────────
        if task_memory.steps and not task_memory.all_completed():
            pending = task_memory.pending_count()
            next_step = task_memory.next_pending()
            if next_step:
                return CriticResult(
                    complete=False,
                    should_continue=True,
                    reason=f"{pending} plan step(s) not yet completed.",
                    injected_message=(
                        f"The plan is not complete. {pending} step(s) remaining.\n"
                        f"Next step: {next_step.task}\n\n"
                        f"Continue executing the plan step by step."
                    ),
                )

        # ── Rule 3: Action intent with zero tool calls → suspicious ───────
        action_intents = {
            IntentType.NEW_PROJECT, IntentType.IMPLEMENT_SPEC,
            IntentType.BUG_FIX, IntentType.REFACTOR,
        }
        if intent in action_intents and tool_calls_made == 0 and total_turns <= 2:
            # Check if the response looks like a question rather than action
            response_lower = (response_text or "").lower()
            is_question = (
                response_lower.strip().endswith("?")
                or "which" in response_lower[:100]
                or "what framework" in response_lower[:200]
                or "what engine" in response_lower[:200]
                or "do you want" in response_lower[:200]
                or "would you like" in response_lower[:200]
                or "please clarify" in response_lower[:200]
                or "can you specify" in response_lower[:200]
            )
            if is_question:
                return CriticResult(
                    complete=False,
                    should_continue=True,
                    reason="Agent asked a clarifying question instead of acting on an action intent.",
                    injected_message=(
                        "You asked a clarifying question instead of starting the task. "
                        "Context was already collected for you. "
                        "Stop asking questions — begin executing the task immediately. "
                        "Use read_file, list_directory, or write_file to make progress."
                    ),
                )

        # ── Rule 4: No files written for a CREATE intent ──────────────────
        create_intents = {IntentType.NEW_PROJECT, IntentType.IMPLEMENT_SPEC}
        if intent in create_intents and len(task_memory.files_written) == 0 and total_turns > 3:
            return CriticResult(
                complete=False,
                should_continue=True,
                reason="No files were created for a create/implement intent after multiple turns.",
                injected_message=(
                    "No files have been written yet, but the task requires creating files. "
                    "Use write_file now to create the required files."
                ),
            )

        # ── Rule 5: Recent errors in task memory → may need retry ─────────
        if task_memory.errors and len(task_memory.errors) > 0:
            recent_errors = task_memory.errors[-3:]
            unresolved = [e for e in recent_errors if not self._is_error_acknowledged(e, response_text)]
            if unresolved:
                return CriticResult(
                    complete=False,
                    should_continue=True,
                    reason=f"Unresolved errors in task memory: {unresolved[0][:100]}",
                    injected_message=(
                        "There are unresolved errors from previous steps:\n"
                        + "\n".join(f"  - {e[:200]}" for e in unresolved)
                        + "\n\nAddress these errors before completing the task."
                    ),
                )

        # ── All checks passed → complete ──────────────────────────────────
        return CriticResult(
            complete=True,
            should_continue=False,
            reason="All critic checks passed.",
            injected_message="",
        )

    def _is_error_acknowledged(self, error: str, response_text: str) -> bool:
        """Check if the agent's response addresses an error."""
        if not response_text:
            return False
        error_key = error[:50].lower()
        return error_key[:20] in response_text.lower()
