"""Phase 5 — Intent Router.

Classifies user requests into 8 deterministic intent types.
Each type maps to a specialized workflow and tool policy.

Intent types:
    NEW_PROJECT     — create a new app/project from scratch
    IMPLEMENT_SPEC  — implement a referenced spec/GDD/PRD file
    BUG_FIX         — fix a bug or error
    REFACTOR        — clean up / restructure existing code
    EXPLAIN         — explain code / answer questions
    CONTINUE        — resume a previous task
    SEARCH          — find something in the codebase
    REVIEW          — review / audit / analyse code
    GENERAL         — everything else (fallback)
"""
from __future__ import annotations

import re
import logging
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger("devpilot.agent.intent_router")


class IntentType(str, Enum):
    NEW_PROJECT = "NEW_PROJECT"
    IMPLEMENT_SPEC = "IMPLEMENT_SPEC"
    BUG_FIX = "BUG_FIX"
    REFACTOR = "REFACTOR"
    EXPLAIN = "EXPLAIN"
    CONTINUE = "CONTINUE"
    SEARCH = "SEARCH"
    REVIEW = "REVIEW"
    GENERAL = "GENERAL"


@dataclass
class IntentResult:
    intent: IntentType
    confidence: float          # 0.0 – 1.0
    referenced_files: list[str]   # file names/paths mentioned in the query
    referenced_symbols: list[str] # function/class names mentioned
    spec_file: str | None      # for IMPLEMENT_SPEC: the spec filename
    needs_context: bool        # True → run ContextCollector before LLM
    needs_plan: bool           # True → run PlanningEngine before execution
    explanation: str           # human-readable reason for classification


# ── Pattern tables ──────────────────────────────────────────────────────────

_CONTINUE_PATTERNS = re.compile(
    r"^\s*(continue|resume|keep going|go on|proceed|next|finish it|"
    r"carry on|pick up where|what's next|what is next|still working)\b",
    re.IGNORECASE,
)

_SEARCH_PATTERNS = re.compile(
    r"^\s*(find|search|where is|where are|locate|look for|show me where|"
    r"grep|what files|which file|list all|show all)\b",
    re.IGNORECASE,
)

_REVIEW_PATTERNS = re.compile(
    r"^\s*(review|audit|check|analyse|analyze|inspect|evaluate|"
    r"code review|security review|look at|examine)\b",
    re.IGNORECASE,
)

_EXPLAIN_PATTERNS = re.compile(
    r"^\s*(explain|what is|what are|what does|how does|how do|why does|"
    r"tell me|describe|summarise|summarize|walk me through|"
    r"what's the difference|compare)\b",
    re.IGNORECASE,
)

_NEW_PROJECT_PATTERNS = re.compile(
    r"\b(scaffold|create.{0,30}(new|fresh|blank|starter)\s+(app|project|application|site|template)|"
    r"(from\s+scratch|brand\s+new)\s+(app|project)|"
    r"(initialise|initialize|init|bootstrap)\s+(a\s+)?(new\s+)?(project|app)|"
    r"create\s+a\s+(new\s+)?(react|vue|next|nuxt|svelte|django|fastapi|flask|express|angular|solid|astro|remix)\s+(app|project)|"
    r"(react|vue|next|nuxt|svelte|django|fastapi|flask|express)\s+(app|project).{0,30}(from\s+scratch|brand\s+new))\b",
    re.IGNORECASE,
)

_BUG_FIX_PATTERNS = re.compile(
    r"\b(fix|debug|resolve|patch|repair|the bug|the error|the issue|the problem|"
    r"traceback|exception|stack\s+trace|not working|broken|fails|crash(es|ing)?|"
    r"TypeError|ValueError|AttributeError|ImportError|ModuleNotFoundError|"
    r"SyntaxError|NameError|KeyError|IndexError)\b",
    re.IGNORECASE,
)

_REFACTOR_PATTERNS = re.compile(
    r"\b(refactor|clean\s+up|reorganize|reorganise|restructure|simplify|"
    r"improve\s+the\s+code|make\s+it\s+cleaner|decouple|extract|rename|"
    r"move\s+to|split\s+into|consolidate|optimise|optimize\s+the\s+code)\b",
    re.IGNORECASE,
)

_IMPLEMENT_SPEC_PATTERNS = re.compile(
    r"\b(implement|build|create|develop|code|write)\b.*\.(md|txt|pdf|doc|docx)\b|"
    r"\b(according\s+to|based\s+on|following\s+the|as\s+per)\s+\S+\.(md|txt)\b",
    re.IGNORECASE,
)

# Extensions that signal a "spec" file
_SPEC_EXTENSIONS = {".md", ".txt", ".pdf", ".doc", ".docx", ".rst"}

# Extensions that signal a code file reference
_CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".toml",
}


def _extract_file_references(text: str) -> tuple[list[str], list[str]]:
    """Return (file_refs, symbol_refs) mentioned in the text."""
    # File references: word.ext or path/to/file.ext
    file_refs = re.findall(
        r'["\']?[\w./\-]+\.(?:py|ts|tsx|js|jsx|md|txt|json|yaml|yml|toml|html|css|go|rs|java|c|cpp|h|cs|rb|pdf|doc|docx|rst)["\']?',
        text,
        re.IGNORECASE,
    )
    file_refs = [f.strip("'\"") for f in file_refs]

    # Symbol references: CamelCase identifiers or snake_case with context
    symbol_refs = re.findall(
        r'\b([A-Z][a-zA-Z0-9]{2,}(?:[A-Z][a-zA-Z0-9]*)*)\b',  # CamelCase
        text,
    )
    symbol_refs += re.findall(
        r'\b([a-z][a-z0-9_]{3,})\s*(?:function|class|method|variable)\b',
        text,
        re.IGNORECASE,
    )
    return file_refs, list(set(symbol_refs))


def _find_spec_file(file_refs: list[str]) -> str | None:
    """Return the first file reference that looks like a spec document."""
    for f in file_refs:
        suffix = "." + f.rsplit(".", 1)[-1].lower() if "." in f else ""
        if suffix in _SPEC_EXTENSIONS:
            return f
    return None


class IntentRouter:
    """Deterministic intent classifier — no LLM call required.

    Classification priority (first match wins):
      1. CONTINUE
      2. SEARCH
      3. EXPLAIN
      4. REVIEW
      5. BUG_FIX
      6. IMPLEMENT_SPEC  (spec file referenced + action verb)
      7. NEW_PROJECT
      8. REFACTOR
      9. GENERAL
    """

    def classify(self, text: str, last_mode: str = "Ask") -> IntentResult:
        text_stripped = text.strip()
        file_refs, symbol_refs = _extract_file_references(text_stripped)
        spec_file = _find_spec_file(file_refs)

        # ── 1. CONTINUE ──────────────────────────────────────────────────
        if _CONTINUE_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.CONTINUE,
                confidence=0.95,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=False,
                needs_plan=False,
                explanation="User wants to resume a previous task.",
            )

        # ── 2. SEARCH ────────────────────────────────────────────────────
        if _SEARCH_PATTERNS.search(text_stripped) and len(text_stripped) < 200:
            return IntentResult(
                intent=IntentType.SEARCH,
                confidence=0.90,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=True,
                needs_plan=False,
                explanation="User wants to find something in the codebase.",
            )

        # ── 3. EXPLAIN ───────────────────────────────────────────────────
        if _EXPLAIN_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.EXPLAIN,
                confidence=0.92,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=bool(file_refs or symbol_refs),
                needs_plan=False,
                explanation="User wants an explanation or answer.",
            )

        # ── 4. REVIEW ────────────────────────────────────────────────────
        if _REVIEW_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.REVIEW,
                confidence=0.88,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=True,
                needs_plan=False,
                explanation="User wants a code review or audit.",
            )

        # ── 5. BUG FIX ───────────────────────────────────────────────────
        if _BUG_FIX_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.BUG_FIX,
                confidence=0.90,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=True,
                needs_plan=True,
                explanation="User wants to fix a bug or error.",
            )

        # ── 6. IMPLEMENT SPEC ────────────────────────────────────────────
        if spec_file and _IMPLEMENT_SPEC_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.IMPLEMENT_SPEC,
                confidence=0.95,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=spec_file,
                needs_context=True,
                needs_plan=True,
                explanation=f"User wants to implement the spec file '{spec_file}'.",
            )

        # ── 7. NEW PROJECT ───────────────────────────────────────────────
        if _NEW_PROJECT_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.NEW_PROJECT,
                confidence=0.88,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=True,  # Check if workspace is empty first
                needs_plan=True,
                explanation="User wants to create a new project from scratch.",
            )

        # ── 8. REFACTOR ──────────────────────────────────────────────────
        if _REFACTOR_PATTERNS.search(text_stripped):
            return IntentResult(
                intent=IntentType.REFACTOR,
                confidence=0.85,
                referenced_files=file_refs,
                referenced_symbols=symbol_refs,
                spec_file=None,
                needs_context=True,
                needs_plan=True,
                explanation="User wants to refactor or restructure code.",
            )

        # ── 9. GENERAL (fallback) ────────────────────────────────────────
        confidence = 0.70
        needs_context = bool(file_refs or symbol_refs)
        needs_plan = len(text_stripped) > 100  # Long requests likely need planning

        return IntentResult(
            intent=IntentType.GENERAL,
            confidence=confidence,
            referenced_files=file_refs,
            referenced_symbols=symbol_refs,
            spec_file=None,
            needs_context=needs_context,
            needs_plan=needs_plan,
            explanation="General request; using default agent workflow.",
        )
