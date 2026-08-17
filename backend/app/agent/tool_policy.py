"""Phase 11 — Tool Policy.

Deterministic rules for which tools to use in which situation.
Reduces inconsistent tool selection by encoding best practices as code.

Rules (in priority order):
  1. File referenced in query → read_file before any edit
  2. Bug fix → search_codebase → read_file → edit_file/write_file
  3. Spec implement → read_file(spec) → plan → write_file
  4. New file → write_file (no prior read needed)
  5. Edit request → read_file → edit_file → fallback write_file
  6. Refactor → read_file → edit_file (multiple)
  7. Search intent → search_codebase
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .intent_router import IntentType

logger = logging.getLogger("loopix.agent.tool_policy")


@dataclass
class ToolRule:
    """A single tool usage rule."""
    name: str
    description: str
    required_before: list[str] = None   # These tools must run before this tool
    forbidden_without: list[str] = None  # Must not use this tool without these having run

    def __post_init__(self):
        self.required_before = self.required_before or []
        self.forbidden_without = self.forbidden_without or []


# ── Tool sequence policies per intent ───────────────────────────────────────

_POLICIES: dict[str, list[str]] = {
    IntentType.BUG_FIX: [
        "ALWAYS search_codebase or read_file BEFORE editing any file.",
        "NEVER apply a fix without reading the file first in the same turn sequence.",
        "After fixing: run the relevant test or build command to confirm the fix.",
        "If search_codebase returns no results, check filename spellings with list_directory.",
    ],
    IntentType.IMPLEMENT_SPEC: [
        "ALWAYS read the spec file FIRST before writing any code.",
        "After reading spec: list_directory to check what already exists.",
        "Use write_file for new files — no prior read needed for new files.",
        "Use read_file → edit_file for files that already exist.",
        "Install dependencies before writing files that import them.",
    ],
    IntentType.NEW_PROJECT: [
        "ALWAYS list_directory root FIRST to check if workspace is empty.",
        "If workspace is non-empty: do NOT scaffold over it without asking.",
        "Use write_file to create all project files — no scaffolding tools unless workspace is empty.",
        "Create config/manifest files before source files that depend on them.",
    ],
    IntentType.REFACTOR: [
        "ALWAYS read_file on every file being refactored BEFORE making changes.",
        "Prefer edit_file for targeted changes; use write_file only for complete rewrites.",
        "After refactoring: search_codebase to find other files that import changed symbols.",
        "Update all import paths after renaming files or moving code.",
    ],
    IntentType.EXPLAIN: [
        "Use read_file to gather the code before explaining.",
        "Use search_codebase to find usages before explaining a symbol.",
        "NEVER use write_file, edit_file, or run_terminal_command in EXPLAIN mode.",
    ],
    IntentType.SEARCH: [
        "Always use search_codebase as the primary search tool.",
        "Follow up with read_file to show surrounding context for matches.",
        "Use list_directory to browse folder structure when search returns no results.",
    ],
    IntentType.REVIEW: [
        "Read all files under review with read_file BEFORE writing the review.",
        "Use search_codebase to find security-sensitive patterns.",
        "NEVER modify files during a review — output review text only.",
    ],
    IntentType.CONTINUE: [
        "Check task memory to determine the next pending step.",
        "Resume from the last incomplete step — do not restart from scratch.",
        "Use the same tool sequence that the original intent required.",
    ],
    IntentType.GENERAL: [
        "For any file edit: read_file FIRST, then edit_file or write_file.",
        "For new files: write_file directly without reading.",
        "For questions about existing code: read_file or search_codebase first.",
    ],
}

# ── Edit safety policy (applies to ALL intents) ──────────────────────────────

_UNIVERSAL_RULES = [
    "BEFORE edit_file: read_file immediately before in the same turn to get current content.",
    "If edit_file fails twice: fall back to write_file with full corrected content.",
    "NEVER repeat an identical failing tool call — change the approach first.",
    "NEVER use run_terminal_command to read files — use read_file instead.",
    "NEVER install packages without checking the manifest first (list_directory → read package.json/requirements.txt).",
]


class ToolPolicy:
    """Returns applicable tool rules for a given intent and situation.

    Usage:
        policy = ToolPolicy()
        rules = policy.get_rules(IntentType.BUG_FIX)
        # Inject rules into system prompt
        prompt += policy.to_prompt_block(IntentType.BUG_FIX)
    """

    def get_rules(self, intent: IntentType) -> list[str]:
        """Return all applicable tool rules for this intent."""
        specific = _POLICIES.get(intent, _POLICIES[IntentType.GENERAL])
        return _UNIVERSAL_RULES + specific

    def to_prompt_block(self, intent: IntentType) -> str:
        """Format tool rules as a prompt section."""
        rules = self.get_rules(intent)
        if not rules:
            return ""

        lines = [
            "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"TOOL POLICY FOR THIS TASK ({intent.value})",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        for rule in rules:
            lines.append(f"  • {rule}")
        return "\n".join(lines)

    def should_read_before_edit(self, file_path: str, files_already_read: list[str]) -> bool:
        """Return True if the agent should read this file before editing it."""
        return file_path not in files_already_read

    def should_fallback_to_write(self, edit_fail_count: int) -> bool:
        """Return True if edit_file has failed enough times to warrant write_file fallback."""
        return edit_fail_count >= 2
