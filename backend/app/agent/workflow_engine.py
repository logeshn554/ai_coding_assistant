"""Phase 10 — Workflow Engine.

Maps each intent type to a specialized workflow.
Each workflow defines the expected tool sequence and prompt emphasis.

Workflows are not hard-coded pipelines — they produce prompt context
that guides the LLM toward the right tool sequence for the intent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .intent_router import IntentType
from .task_memory import TaskMemory
from .tool_policy import ToolPolicy

logger = logging.getLogger("devpilot.agent.workflow_engine")


@dataclass
class WorkflowContext:
    """Context produced by the workflow engine for injection into the system prompt."""
    intent: IntentType
    workflow_name: str
    tool_sequence_hint: str    # Natural language description of expected tool order
    emphasis: list[str]        # Key behaviors to emphasise
    success_criteria: str      # What "done" looks like

    def to_prompt_block(self) -> str:
        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"WORKFLOW: {self.workflow_name}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        if self.tool_sequence_hint:
            lines.append(f"Expected tool sequence: {self.tool_sequence_hint}")
        if self.emphasis:
            lines.append("Key behaviors:")
            for e in self.emphasis:
                lines.append(f"  • {e}")
        if self.success_criteria:
            lines.append(f"Done when: {self.success_criteria}")
        return "\n".join(lines)


class WorkflowEngine:
    """Maps intent to specialized workflow context.

    Usage:
        engine = WorkflowEngine()
        ctx = engine.get_workflow(intent, task_memory)
        system_prompt += ctx.to_prompt_block()
    """

    def __init__(self):
        self._policy = ToolPolicy()

    def get_workflow(
        self,
        intent: IntentType,
        task_memory: TaskMemory | None = None,
    ) -> WorkflowContext:
        """Return the workflow context for the given intent."""
        handlers = {
            IntentType.IMPLEMENT_SPEC: self._implement_spec,
            IntentType.BUG_FIX: self._bug_fix,
            IntentType.NEW_PROJECT: self._new_project,
            IntentType.REFACTOR: self._refactor,
            IntentType.EXPLAIN: self._explain,
            IntentType.SEARCH: self._search,
            IntentType.REVIEW: self._review,
            IntentType.CONTINUE: self._continue,
            IntentType.GENERAL: self._general,
        }
        handler = handlers.get(intent, self._general)
        return handler(task_memory)

    # ── Workflow handlers ────────────────────────────────────────────────

    def _implement_spec(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.IMPLEMENT_SPEC,
            workflow_name="Implement Specification",
            tool_sequence_hint=(
                "read_file(spec) → list_directory → write_file(files) → "
                "run_terminal_command(install) → run_terminal_command(test/build)"
            ),
            emphasis=[
                "Read the entire spec file FIRST before writing any code.",
                "List workspace root to understand existing structure before creating files.",
                "Create all required files completely — no placeholder stubs.",
                "Install all dependencies mentioned in the spec.",
                "Re-read the original spec at the end to verify every requirement is met.",
            ],
            success_criteria=(
                "All files described in the spec exist, all dependencies installed, "
                "build/run command succeeds, every spec requirement confirmed satisfied."
            ),
        )

    def _bug_fix(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.BUG_FIX,
            workflow_name="Bug Fix",
            tool_sequence_hint=(
                "search_codebase(error) → read_file(affected) → "
                "edit_file or write_file(fix) → run_terminal_command(test)"
            ),
            emphasis=[
                "Search for the error pattern BEFORE modifying any file.",
                "Read the full file before editing — never guess at content.",
                "Fix only the root cause — avoid unrelated changes.",
                "Run tests after fixing to confirm the bug is resolved.",
                "Check for similar bugs in related files.",
            ],
            success_criteria=(
                "The original error no longer occurs, tests pass, "
                "no new errors introduced."
            ),
        )

    def _new_project(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.NEW_PROJECT,
            workflow_name="New Project Creation",
            tool_sequence_hint=(
                "list_directory(root) → write_file(configs) → "
                "write_file(source_files) → run_terminal_command(install) → "
                "run_terminal_command(dev_server)"
            ),
            emphasis=[
                "Check workspace is empty (or confirm it's safe to add files) FIRST.",
                "Create manifest/config files before source files.",
                "Write complete, runnable files — no TODO stubs.",
                "Install dependencies before trying to run the project.",
                "Confirm the project starts successfully and provide the preview URL.",
            ],
            success_criteria=(
                "Project runs without errors, dev server starts, "
                "preview URL is provided to the user."
            ),
        )

    def _refactor(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.REFACTOR,
            workflow_name="Code Refactoring",
            tool_sequence_hint=(
                "read_file(affected) → [search_codebase(symbol)] → "
                "edit_file or write_file → update_imports → run_terminal_command(test)"
            ),
            emphasis=[
                "Read ALL files involved in the refactor BEFORE making any changes.",
                "Search for all usages of renamed/moved symbols before renaming.",
                "Update import paths in all files that reference changed code.",
                "Run tests after refactoring to verify nothing is broken.",
            ],
            success_criteria=(
                "All affected files updated, imports consistent, tests pass."
            ),
        )

    def _explain(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.EXPLAIN,
            workflow_name="Code Explanation",
            tool_sequence_hint=(
                "read_file(relevant) → search_codebase(symbol) → explain"
            ),
            emphasis=[
                "Read the relevant code BEFORE explaining it.",
                "Quote specific lines to support your explanation.",
                "NEVER modify any files during an explanation.",
            ],
            success_criteria=(
                "Explanation is accurate, well-structured, and references actual code lines."
            ),
        )

    def _search(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.SEARCH,
            workflow_name="Codebase Search",
            tool_sequence_hint=(
                "search_codebase(query) → read_file(results) → report"
            ),
            emphasis=[
                "Use search_codebase with precise patterns.",
                "Show surrounding context for each match.",
                "If no results: try list_directory, check filenames.",
            ],
            success_criteria=(
                "All relevant occurrences reported with file paths and line numbers."
            ),
        )

    def _review(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.REVIEW,
            workflow_name="Code Review",
            tool_sequence_hint=(
                "read_file(files) → search_codebase(patterns) → report"
            ),
            emphasis=[
                "Read all files under review BEFORE writing the report.",
                "Check for: security issues, performance, code quality, correctness.",
                "NEVER modify any files during a review.",
                "Produce a structured report with specific findings and recommendations.",
            ],
            success_criteria=(
                "Structured review report produced with specific findings, "
                "file paths, and actionable recommendations."
            ),
        )

    def _continue(self, tm: TaskMemory | None) -> WorkflowContext:
        next_step = None
        if tm:
            next_step = tm.next_pending()

        return WorkflowContext(
            intent=IntentType.CONTINUE,
            workflow_name="Resume Previous Task",
            tool_sequence_hint=(
                f"[Resume from: {next_step.task if next_step else 'last incomplete step'}]"
            ),
            emphasis=[
                "Check task memory to find the next incomplete step.",
                "Resume from exactly where the previous task stopped.",
                "Do NOT restart from scratch.",
                "Complete all remaining steps in the original plan order.",
            ],
            success_criteria=(
                "All remaining plan steps completed and validated."
            ),
        )

    def _general(self, tm: TaskMemory | None) -> WorkflowContext:
        return WorkflowContext(
            intent=IntentType.GENERAL,
            workflow_name="General Task",
            tool_sequence_hint="read_file or search_codebase → execute → validate",
            emphasis=[
                "Read relevant files BEFORE modifying them.",
                "Verify your changes work after making them.",
                "Complete the task fully without stopping early.",
            ],
            success_criteria=(
                "Task requirement fully satisfied and verified."
            ),
        )
