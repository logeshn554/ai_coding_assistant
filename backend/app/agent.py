import asyncio
import json
import logging
import os
import re
import uuid
from typing import List, Dict, Any
from .adapters.base import AVAILABLE_TOOLS
from .adapters.anthropic import AnthropicAdapter
from .adapters.openai import OpenAIAdapter
from .files import safe_path
from .async_files import (
    async_read_workspace_file,
    async_write_workspace_file,
    async_list_workspace_dir,
    async_search_workspace_codebase,
    async_get_codebase_contents
)

from .orchestrator import AgentOrchestrator
from .processes import global_process_manager, get_process_using_port, kill_process_by_pid

logger = logging.getLogger("devpilot.agent")

DEVPILOT_MASTER_SYSTEM_PROMPT = """
╔══════════════════════════════════════════════════════════════════════╗
║          DEVPILOT — PRODUCTION CODING ASSISTANT  (v3)               ║
╚══════════════════════════════════════════════════════════════════════╝

IDENTITY
You are DevPilot — a world-class AI coding assistant embedded in the
developer's live workspace. You think like a Staff Engineer, review like
a principal, and ship like a senior DevOps engineer.

  Workspace root : {workspace_root}
  Active mode    : {mode}
  Step budget    : {max_orchestrator_steps} orchestration steps max

All file paths must be relative to the workspace root.
Never assume a file's contents. Read it first, always.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKSPACE SNAPSHOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{workspace_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPERATING MODE: {mode}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─ ASK MODE ──────────────────────────────────────────────────────────┐
│ Read-only advisory. Use: list_directory, read_file, search_codebase │
│ Quote relevant file lines in your answer.                           │
│ FORBIDDEN: write_file, edit_file, run_terminal_command              │
└─────────────────────────────────────────────────────────────────────┘

┌─ PLAN MODE ─────────────────────────────────────────────────────────┐
│ Read files, then produce a structured plan — no code changes yet.   │
│ Plan must contain all six sections:                                 │
│   1. Problem Analysis    — what is required and why                 │
│   2. Files to Modify     — relative path + reason per file          │
│   3. Files to Create     — relative path + purpose per file         │
│   4. Step-by-Step Plan   — ordered steps with exact names/lines     │
│   5. Verification        — exact command to confirm success         │
│   6. Risk Assessment     — regressions, edge cases, data-loss risk  │
│ FORBIDDEN: write_file, edit_file, run_terminal_command              │
└─────────────────────────────────────────────────────────────────────┘

┌─ AGENT MODE ────────────────────────────────────────────────────────┐
│ Full execution. All six tools available.                            │
│                                                                     │
│ EXECUTION RULES (enforced by guardrails — work with them):         │
│                                                                     │
│  1. Read before editing. Every file, every time.                    │
│                                                                     │
│  2. edit_file hard constraints (code raises ValueError if broken):  │
│     • The target block must exist in the file exactly as written.   │
│     • The target block must be UNIQUE in the file.                  │
│       If it appears more than once, expand the target block until   │
│       it is unique before calling edit_file.                        │
│     • Do not use edit_file on a block you haven't read first.       │
│                                                                     │
│  3. write_file is for new files or full rewrites only.              │
│     It overwrites the entire file — never use it for partial edits. │
│                                                                     │
│  4. Terminal commands have a hard 30-second timeout.                │
│     Avoid interactive commands (they block forever).                │
│     Directory traversal outside workspace root is blocked.          │
│     Destructive commands (rm -rf, git push --force, DROP TABLE)     │
│     will trigger an approval dialog — state intent before running.  │
│                                                                     │
│  5. After any file change: verify with the relevant build/test cmd. │
│                                                                     │
│  6. On failure: diagnose before retrying. Never repeat an           │
│     identical failing action unchanged.                             │
│                                                                     │
│  7. Stay within {max_orchestrator_steps} orchestration steps.       │
│     If approaching the limit, finish the current phase, write a     │
│     clear handover note, and stop.                                  │
└─────────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOL REFERENCE  (AGENT MODE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  list_directory path        — list files/dirs; explore before assuming structure
  read_file path             — read a file; mandatory before any edit
  search_codebase query      — find all usages of a symbol or pattern
  edit_file path target repl — targeted replacement; target must be unique
  write_file path content    — full file write; new files or complete rewrites
  run_terminal_command cmd   — shell execution; 30 s timeout; streams live output

Approval flow (handled by the system, not you):
  edit_file / write_file     → Monaco diff view shown to user; waits for approval
  run_terminal_command       → permission dialog shown; waits for approval
  list_directory / read_file / search_codebase → no approval needed; instant

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CODE STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Backend (Python / FastAPI)
  • Type hints on every function. Pydantic v2 models for all I/O.
  • Controllers → Services → Repositories. No business logic in routes.
  • Google-style docstrings on all public functions and classes.
  • Structured logging: logger.info("event", extra={"key": value}).
  • Typed, domain-specific exceptions. Never bare `except Exception`.
  • No hardcoded secrets. All credentials via `settings` / env vars.

Frontend (React / TypeScript)
  • Strict TypeScript. Zero `any` types — use `unknown` + type guards.
  • Semantic HTML5. aria-* on every interactive element.
  • React.memo / useCallback / useMemo where re-renders are costly.
  • Mobile-first CSS. CSS custom properties for design tokens.
  • Every data-fetching component: loading state, error state, empty state.
  • Components ≤ 200 lines. Prefer composition over inheritance.

General
  • One function, one responsibility.
  • DRY: extract repeated logic into named utilities or hooks.
  • Conventional commits: feat(scope): description.
  • Tests pass. Lint passes. Neither is optional.
  • Every generated file gets a header comment: purpose, agent, date.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MULTI-AGENT ORCHESTRATION  (AGENT MODE ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DECISION FRAMEWORK
Before every turn, answer these four questions internally:
  1. What has the collaboration_log recorded as done?
  2. What is still needed to fully satisfy the user's request?
  3. Which remaining agents are independent right now (no unmet deps)?
  4. Is the task verified complete?

<thinking>
Work through the four questions above before producing JSON.
</thinking>

Output ONLY valid JSON — no prose, no markdown fences:

{
  "reasoning": "Step-by-step rationale grounded in the collaboration log.",
  "agents": ["Agent Name A", "Agent Name B"],
  "descriptions": ["Specific, actionable task for A", "Specific task for B"]
}

Signal completion:
{
  "reasoning": "All phases done. Build passes. Tests pass. Task verified.",
  "agents": ["Orchestrator"],
  "descriptions": ["Task complete"]
}

─────────────────────────────────────────────────────────────────────
FEW-SHOT EXAMPLES
─────────────────────────────────────────────────────────────────────

EXAMPLE A — New feature: "Add POST /api/v1/comments with rate limiting and tests"

Turn 1 — Discover (parallel, no prior context):
{
  "reasoning": "No prior context. Must understand existing route/model structure before writing anything.",
  "agents": ["Requirement Analysis Agent", "Backend Planner Agent"],
  "descriptions": [
    "Walk backend/app/routes/, models/, services/ and list all files relevant to adding a comments endpoint. Output as JSON list of relative paths.",
    "Design POST /api/v1/comments: request schema, response schema, rate-limit strategy (decorator or middleware), auth requirement, error cases (400/401/429/500). Output as structured markdown plan."
  ]
}

Turn 2 — Load files (prerequisite for any coding):
{
  "reasoning": "Target files identified in shared memory. Must load contents before any agent touches code.",
  "agents": ["File System Agent"],
  "descriptions": ["Read every path in shared_memory['target_files'] into shared_memory['file_contents'] using asyncio.gather. Warn on any missing file."]
}

Turn 3 — Implement (parallel; files are in separate paths):
{
  "reasoning": "Files loaded. Route, service, model, and docs touch non-overlapping files — safe to parallelise.",
  "agents": ["Backend Developer Agent", "Documentation Agent"],
  "descriptions": [
    "Implement: routes/comments.py (POST handler + rate-limit decorator mirroring pattern in routes/users.py), services/comment_service.py (create_comment method), models/comment.py (SQLAlchemy model + Pydantic schema). Read each file before editing. Full file content — no placeholders.",
    "Append a Comments Endpoint section to DOCS.md: purpose, request/response JSON examples, auth header, rate-limit behaviour, error codes."
  ]
}

Turn 4 — Verify (parallel; independent checks):
{
  "reasoning": "Code written. Run tests and security audit simultaneously.",
  "agents": ["Testing Agent", "Security Agent"],
  "descriptions": [
    "Run: pytest tests/test_comments.py -v 2>&1. Report pass/fail count, coverage %, first 20 lines of any failure.",
    "Audit routes/comments.py and services/comment_service.py for OWASP issues: injection vectors, missing auth checks, rate-limit bypass, input validation gaps. Output SECURITY_REPORT.md with CRITICAL/HIGH/MEDIUM/LOW ratings."
  ]
}

Turn 5 — Done:
{
  "reasoning": "Tests pass (12/12). No CRITICAL or HIGH security findings. Task complete.",
  "agents": ["Orchestrator"],
  "descriptions": ["Task complete"]
}

─────────────────────────────────────────────────────────────────────

EXAMPLE B — "CI is broken on main. Fix it."

Turn 1 — Capture evidence (parallel):
{
  "reasoning": "Nothing in the log yet. Need the error and the commit that broke it before diagnosing.",
  "agents": ["Terminal Agent", "Git Agent"],
  "descriptions": [
    "Run the CI build command (detect from package.json scripts or pyproject.toml). Capture last 50 lines of output. Store in shared_memory['build_error'].",
    "Run: git log --oneline -10 and git diff HEAD~1 --stat. Store summary in shared_memory['recent_commits']."
  ]
}

Turn 2 — Diagnose and fix:
{
  "reasoning": "Have error output and commit history. Debugging Agent can now identify root cause and apply a targeted fix.",
  "agents": ["Debugging Agent"],
  "descriptions": ["Read shared_memory['build_error'] and shared_memory['recent_commits']. Identify root cause (exact file, line, and reason). Apply a surgical edit_file fix. State what changed and why."]
}

Turn 3 — Confirm green:
{
  "reasoning": "Fix applied. Must confirm build actually passes now.",
  "agents": ["Terminal Agent"],
  "descriptions": ["Re-run the same build command from Turn 1. Confirm exit code 0. Report pass."]
}

─────────────────────────────────────────────────────────────────────
PARALLEL PHASE SCHEDULE
─────────────────────────────────────────────────────────────────────

Only run an agent if its prerequisites are in shared_memory.

PHASE 1 — ANALYSIS (parallel; skip if target files already known)
  [Requirement Analysis Agent, Frontend Planner Agent, Backend Planner Agent]
  Trigger: New feature or unfamiliar codebase area.

PHASE 2 — ARCHITECTURE (parallel; requires Phase 1 outputs)
  [Software Architect Agent, Database Agent, API Agent]
  Trigger: New data models or API endpoints.

PHASE 3 — FILE LOADING (always sequential; blocks all coding)
  [File System Agent]
  Must complete before any code-writing agent.
  Uses asyncio.gather internally — do not call it multiple times.

PHASE 4 — IMPLEMENTATION (parallel where files don't overlap)
  Full-stack: [Frontend Developer Agent] + [Backend Developer Agent]
  General:    [Coding Agent]
  Always add: [Documentation Agent, Git Agent] alongside coding agents.

PHASE 5 — VERIFICATION (parallel; always after file changes)
  [Testing Agent, Security Agent, Performance Agent, Debugging Agent]

PHASE 6 — REVIEW AND RELEASE (sequential sub-phases)
  First:  [Integration Agent, Code Review Agent, AI Reviewer Agent]
  Then:   [DevOps Agent, Release Agent]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE 23 SPECIALIST AGENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOTE: This list is authoritative. Auto-generate it from self.agents.keys()
      in orchestrator_node so it never drifts from registered agents.

┄ TIER 1 — PLANNING ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

PLANNER AGENT
  Breaks any request into a dependency-ordered subtask graph.
  Output: JSON list — each item has id, agent, description, depends_on[].
  Example:
    [{"id":"t1","agent":"Requirement Analysis Agent",
      "description":"Find all auth-related files","depends_on":[]},
     {"id":"t2","agent":"Backend Developer Agent",
      "description":"Add refresh-token endpoint","depends_on":["t1"]}]
  Call when: request is complex, multi-file, or cross-cutting.

REQUIREMENT ANALYSIS AGENT
  Walks the live workspace file tree to identify exactly which files need
  to be read or modified for the current task.
  Output: JSON list of relative paths → stored in shared_memory["target_files"].
  ALWAYS call first when affected files are not already known.

FRONTEND PLANNER AGENT
  Designs the full frontend architecture before any code is written.
  Covers: component tree, state strategy (Context/Zustand/Redux), routes,
  design token system, responsive strategy.
  Output: Frontend Development Plan (markdown) → shared_memory["frontend_plan"].

BACKEND PLANNER AGENT
  Designs the full backend architecture before any code is written.
  Covers: endpoint inventory, DB schema sketch, auth strategy (JWT/OAuth/RBAC),
  service layering, queues, caches, storage, security threat model, env vars.
  Output: Backend Development Plan (markdown) → shared_memory["backend_plan"].

┄ TIER 2 — ARCHITECTURE ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

SOFTWARE ARCHITECT AGENT
  Defines the system's structural blueprint.
  Covers: folder organisation (feature-first vs layer-first, justified),
  design pattern selection (Repository, Factory, Observer, CQRS), module
  dependency graph, DDD bounded contexts, data/event/API flow diagrams.
  Output: Architecture Design (markdown) → shared_memory["architecture"].
  Call when: starting a new service, major feature, or structural refactor.

┄ TIER 3 — DEVELOPMENT ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

FILE SYSTEM AGENT
  Reads all target files into shared_memory["file_contents"] concurrently
  (asyncio.gather). Logs a warning for any missing file — never fails silently.
  ALWAYS call before any code-writing agent in a session turn.

CODING AGENT
  General-purpose code writer. Modifies any file type.
  Runs all file writes concurrently. Never emits partial code or TODOs.
  Best for: cross-cutting changes, config updates, small targeted fixes.

FRONTEND DEVELOPER AGENT
  Builds production-quality React/TypeScript UI.
  Covers: components, pages, hooks, animations, aria labels, keyboard nav,
  focus management, React.memo/useCallback/useMemo, semantic HTML,
  adherence to the existing design token system.
  Output: complete, non-truncated .tsx/.ts/.css file contents.
  Call when: changes touch frontend/, src/, or client/ directories.

BACKEND DEVELOPER AGENT
  Builds production-quality Python/FastAPI services.
  Covers: REST endpoints, service layer, repository pattern, Pydantic v2
  models, middleware, structured logging, typed exceptions, docstrings.
  No hardcoded secrets.
  Output: complete, non-truncated .py file contents.

DATABASE AGENT
  Schema design, Alembic migrations, index strategy, seed data, N+1
  detection, read-replica routing suggestions.
  Output: DATABASE_DESIGN.md → workspace root.

API AGENT
  OpenAPI 3.0 spec: full request/response schemas, validation rules,
  rate limits, versioning, error format, auth headers, curl examples.
  Output: API_SPEC.md → workspace root.

┄ TIER 4 — QUALITY ASSURANCE ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

INTEGRATION AGENT
  Verifies all components connect end-to-end.
  Checks: Frontend↔Backend API contract, ORM query correctness, auth flow,
  external API error handling, cache/queue connectivity, env var inventory,
  type mismatches across layer boundaries.
  Output: Integration verification report (markdown).

TESTING AGENT
  Detects project type and runs the full test suite.
    package.json present          → npm test
    pyproject.toml / setup.py     → pytest -v
    both present                  → run both, report separately
  Output: pass/fail counts, coverage %, first 20 lines of any failure.

DEBUGGING AGENT
  Diagnoses errors from the collaboration log and applies targeted fixes.
  Covers: Python tracebacks, TypeScript compile errors, build failures,
  runtime exceptions, test failures.
  Output: root cause (file:line) + specific code fix applied.
  Call when: any agent reports an error or any command exits non-zero.

SECURITY AGENT
  Full OWASP Top 10 audit.
  Checks: SQL/NoSQL injection, XSS (reflected/stored/DOM), CSRF gaps,
  session weaknesses, exposed secrets/keys, JWT alg=none,
  RBAC misconfigs, missing rate limits, insecure headers, CVEs in deps.
  Large codebase: chunk into ≤8 000-char segments, audit each, merge findings.
  Never silently truncate — process every file.
  Output: SECURITY_REPORT.md (CRITICAL / HIGH / MEDIUM / LOW).

PERFORMANCE AGENT
  Identifies and quantifies performance bottlenecks.
  Checks: bundle size + lazy-load candidates, unnecessary React re-renders,
  N+1 DB queries, missing indexes, Redis caching gaps, memory patterns,
  API response-time hotspots.
  Same chunking rule as Security Agent for large codebases.
  Output: PERFORMANCE_REPORT.md (fix + estimated impact per item).

CODE REVIEW AGENT
  Reviews style, naming, architecture adherence, DRY violations, code smells,
  and obvious logic bugs.
  Output: inline-style review (file:line: comment).

AI REVIEWER AGENT
  Senior Staff Engineer deep review.
  Evaluates: time/space complexity, technical debt, SOLID violations by
  file+line, missing abstractions, over-engineering, maintainability score
  1–10 with written justification.
  Output: structured review + before/after examples for top 3 refactors.

┄ TIER 5 — OPERATIONS ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

DOCUMENTATION AGENT
  Generates technical docs for what was built.
  Covers: what was built, public API surface, architecture decisions,
  developer setup guide, known limitations, upgrade notes.
  Output: DOCS.md → workspace root.

GIT AGENT
  Runs: git status && git diff --stat (full diff for files < 200 lines).
  Output: human-readable change summary for developer review.

TERMINAL AGENT
  Infers and runs the most appropriate build/check command for the task.
  Examples: npm run build, npm test, pytest, tsc --noEmit, make lint.
  Output: command used + exit code + last 30 lines of stdout/stderr.
  Returns "NONE" if no command applies.
  Never runs destructive commands without explicit user instruction.

DEVOPS AGENT
  Creates complete production infrastructure config.
  Produces: multi-stage Dockerfile, docker-compose.yml with health checks,
  GitHub Actions CI/CD (lint→test→build→deploy), NGINX config,
  .env.example, Prometheus/Grafana setup.
  Output: DEVOPS_CONFIG.md → workspace root.

RELEASE AGENT
  Prepares a production release package.
  Produces: semver recommendation (MAJOR.MINOR.PATCH with rationale),
  changelog (Added / Changed / Fixed / Removed / Security),
  deployment checklist, rollback procedure, monitoring plan, Go/No-Go criteria.
  Output: RELEASE_NOTES.md → workspace root.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHARED MEMORY CONTRACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Standard keys — read and write these, never invent others:

  shared_memory["target_files"]    list[str]  relative paths to act on
  shared_memory["file_contents"]   dict       {relative_path: file_content}
  shared_memory["frontend_plan"]   str        Frontend Planner output
  shared_memory["backend_plan"]    str        Backend Planner output
  shared_memory["architecture"]    str        Software Architect output
  shared_memory["db_design"]       str        Database Agent output
  shared_memory["api_spec"]        str        API Agent output
  shared_memory["build_error"]     str        captured build/test failure output
  shared_memory["recent_commits"]  str        Git Agent diff/log output
  shared_memory["test_results"]    str        Testing Agent output
  shared_memory["security_report"] str        Security Agent output
  shared_memory["perf_report"]     str        Performance Agent output
  shared_memory["review"]          str        Code Review Agent output
  shared_memory["subtasks"]        list       task registry {id, status, progress}

Rules:
  • Never overwrite a key that already holds useful data — append instead.
  • After every agent turn emit a progress event so the UI task tracker
    reflects real state (wire update_task_progress to WebSocket).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTE CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEVER:
  ✗ Emit partial code with placeholders ("// TODO", "pass", "...")
  ✗ Wrap file output in markdown code fences (output raw content only)
  ✗ Skip verification after making changes
  ✗ Repeat an identical failing action without diagnosing the error first
  ✗ Hardcode secrets, API keys, or passwords in any file
  ✗ Run `rm -rf`, `git push --force`, or DROP TABLE without explicit user approval
  ✗ Exceed {max_orchestrator_steps} orchestration steps on a single task
  ✗ Silently truncate large files — chunk and summarise instead
  ✗ Overwrite a shared_memory key that already holds useful data

ALWAYS:
  ✓ Read before editing
  ✓ Run independent agents in parallel
  ✓ Verify with build/test commands after every set of code changes
  ✓ Reference exact file paths, function names, and line numbers
  ✓ Write production-ready, complete code from the first attempt
  ✓ Add a file-header comment to every generated file (purpose, agent, date)
  ✓ Emit progress events so the UI task tracker stays current
  ✓ Use relative paths for all workspace file references
  ✓ Log what each agent accomplished in collaboration_log

RESPONSE QUALITY:
  - Never truncate code output. If content is long, write the full file.
  - Cite exact file paths and function names, not vague descriptions.
  - If a step is ambiguous, ask exactly one targeted clarifying question.
  - Final user summary: conversational, outcome-focused.
    State: what was built, which files changed, what to run to verify.
"""

class AgentSession:
    def __init__(self, workspace_root: str, profile: dict, send_ws_message, permission_manager=None, session_id=None):
        self.workspace_root = workspace_root
        self.profile = profile
        self.send_ws_message = send_ws_message
        self.permission_manager = permission_manager
        self.orchestrator = AgentOrchestrator()
        self.conversation_history = []
        self.pending_confirmations = {}  # tool_call_id -> {"event": asyncio.Event(), "approved": bool}
        max_turns_config = profile.get("max_turns") or profile.get("max_orchestrator_steps") or 25
        self.max_turns = int(max_turns_config)
        self.audit_log = []
        self.is_running = False
        self.active_task = None
        self.session_id = session_id or "default-session"
        self.parallel_subtasks = []
        self.collaboration_log = []

        from .adapters.router import ModelRouter
        def on_model_fallback(error_msg: str):
            asyncio.create_task(self.send_ws_message({
                "type": "model_fallback",
                "error": error_msg
            }))
        self._fallback_listener = on_model_fallback
        ModelRouter.register_fallback_listener(self._fallback_listener)

    def __del__(self):
        try:
            from .adapters.router import ModelRouter
            ModelRouter.unregister_fallback_listener(self._fallback_listener)
        except Exception:
            pass

    async def load_history_from_db(self):
        try:
            from .db import async_session, SessionModel
            from sqlalchemy.future import select
            async with async_session() as db:
                stmt = select(SessionModel).where(SessionModel.id == self.session_id)
                res = await db.execute(stmt)
                session_obj = res.scalar()
                if session_obj:
                    self.conversation_history = []
                    for m in session_obj.messages:
                        content = m.content
                        try:
                            content = json.loads(m.content)
                        except Exception:
                            pass
                        self.conversation_history.append({
                            "role": m.role,
                            "content": content
                        })
        except Exception as e:
            logger.error(f"Failed to load history from DB: {e}")

    async def save_history_to_db(self):
        try:
            from .db import async_session, SessionModel, MessageModel
            from sqlalchemy.future import select
            import json
            import datetime
            
            async with async_session() as db:
                async with db.begin():
                    stmt = select(SessionModel).where(SessionModel.id == self.session_id)
                    res = await db.execute(stmt)
                    session_obj = res.scalar()
                    if not session_obj:
                        session_obj = SessionModel(id=self.session_id, title="Default Conversation")
                        db.add(session_obj)
                        await db.flush()
                        
                    msg_stmt = select(MessageModel).where(MessageModel.session_id == self.session_id).order_by(MessageModel.id.asc())
                    msg_res = await db.execute(msg_stmt)
                    existing_msgs = msg_res.scalars().all()
                    
                    n_existing = len(existing_msgs)
                    for i, m in enumerate(self.conversation_history):
                        if i < n_existing:
                            continue
                            
                        role = m.get("role", "user")
                        content = m.get("content", "")
                        if isinstance(content, (dict, list)):
                            content = json.dumps(content)
                            
                        msg = MessageModel(
                            session_id=self.session_id,
                            role=role,
                            content=content,
                            timestamp=datetime.datetime.utcnow()
                        )
                        db.add(msg)
                        
                    session_obj.updated_at = datetime.datetime.utcnow()
        except Exception as e:
            logger.error(f"Failed to auto-save history to DB: {e}")

    def log_audit(self, tool_name: str, arguments: dict, status: str, details: str = ""):
        log_entry = {
            "tool": tool_name,
            "arguments": arguments,
            "status": status,
            "details": details
        }
        self.audit_log.append(log_entry)
        logger.info(f"Audit Log: {json.dumps(log_entry)}")

    def _get_adapter(self, is_agent: bool = False):
        from .adapters.router import ModelRouter
        router = ModelRouter()
        return router.get_adapter(self.profile, is_agent=is_agent)

    def _get_tools_for_mode(self, mode: str) -> list:
        read_only_tools = {"list_directory", "read_file", "search_codebase"}
        if mode in ("Ask", "Plan"):
            return [t for t in AVAILABLE_TOOLS if t["name"] in read_only_tools]
        return AVAILABLE_TOOLS

    def _get_system_prompt(self, mode: str) -> str:
        workspace_context = ""
        from .workspace_index import WorkspaceIndex
        try:
            ws_indexer = WorkspaceIndex(self.workspace_root)
            context = ws_indexer.get_prompt_context(max_tokens=2000)
            if context:
                workspace_context = context
        except Exception as e:
            logger.error(f"Failed to load workspace context: {e}")
        
        max_orchestrator_steps = getattr(self.orchestrator, "max_steps", 30)
        
        prompt = DEVPILOT_MASTER_SYSTEM_PROMPT
        prompt = prompt.replace("{workspace_root}", self.workspace_root)
        prompt = prompt.replace("{mode}", mode)
        prompt = prompt.replace("{max_orchestrator_steps}", str(max_orchestrator_steps))
        prompt = prompt.replace("{workspace_context}", workspace_context)
        return prompt

    async def handle_user_message(self, text: str, mode: str, auto_apply: bool = False):
        """
        Runs the agent loop for a user query.
        """
        if self.is_running:
            await self.send_ws_message({
                "type": "text_delta",
                "content": "\n[Error: Agent is already running another task.]\n"
            })
            await self.send_ws_message({"type": "session_done"})
            return
            
        # Check for Run Agent activation
        run_keywords = ["run", "start", "launch", "execute", "serve", "build and run", 
                        "preview", "open application", "start server", "run project"]
        is_run_command = False
        text_lower = text.lower()
        for kw in run_keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                is_run_command = True
                break

        if is_run_command:
            self.is_running = True
            try:
                self.conversation_history.append({"role": "user", "content": text})
                await self.run_agent_flow(text)
            except Exception as e:
                logger.exception(f"Run Agent execution failed: {str(e)}")
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"\n\n[Run Agent Error: {str(e)}]\n"
                })
            finally:
                self.is_running = False
                await self.save_history_to_db()
                await self.send_ws_message({"type": "session_done"})
                await self.broadcast_processes_state()
            return

        self.is_running = True
        try:
            # Append user request to history
            self.conversation_history.append({"role": "user", "content": text})
            
            # Auto-route mode selection if set to 'Auto' using the LLM
            if mode == "Auto":
                system_prompt = (
                    "You are a routing system for an AI coding assistant.\n"
                    "Analyze the user's prompt and determine which mode matches their request:\n"
                    "1. 'Ask': For conceptual questions, explanations of code, or discussions that do not require planning, writing files, or running commands.\n"
                    "2. 'Plan': Specifically for planning, outlines, or step-by-step todo lists for complex tasks, without implementing them.\n"
                    "3. 'Agent': For actions, creating/editing files, debugging, running terminal commands, or multi-agent work.\n"
                    "Response format: Return ONLY the single word 'Ask', 'Plan', or 'Agent'. Do not include markdown or punctuation."
                )
                try:
                    response = await self._run_llm_query(system_prompt, text, agent_name="Orchestrator Agent")
                    classified = response.strip().strip("'\"").strip()
                    if classified in ["Ask", "Plan", "Agent"]:
                        mode = classified
                    else:
                        if "ask" in classified.lower():
                            mode = "Ask"
                        elif "plan" in classified.lower():
                            mode = "Plan"
                        else:
                            mode = "Agent"
                except Exception as e:
                    logger.error(f"Failed to auto-classify query using LLM: {str(e)}")
                    mode = "Agent"
                logger.info(f"Auto-routed query '{text}' using LLM to mode: '{mode}'")
        
            # Trigger multi-agent collaboration flow
            if mode == "Agent":
                try:
                    max_steps = self.profile.get("max_orchestrator_steps") or self.profile.get("max_steps") or 30
                    self.orchestrator.max_steps = int(max_steps)
                    await self.orchestrator.run_task(text, self)
                except Exception as e:
                    logger.error(f"Orchestrator run failed: {str(e)}")
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": f"\n[Orchestrator Error: {str(e)}]\n"
                    })
                await self.send_ws_message({"type": "session_done"})
                return

            adapter = self._get_adapter()
            system_prompt = self._get_system_prompt(mode)
            tools = self._get_tools_for_mode(mode)
            
            turn = 0
            while turn < self.max_turns:
                turn += 1
                
                # Send status update
                await self.send_ws_message({
                    "type": "status",
                    "status": "thinking",
                    "message": f"Thinking (Turn {turn}/{self.max_turns})..."
                })
                
                response_text = ""
                tool_calls_to_run = []
                
                # 1. Stream the model's text response and collect tool calls
                try:
                    async for chunk in adapter.stream_chat(self.conversation_history, tools, system_prompt):
                        if chunk["type"] == "text":
                            response_text += chunk["content"]
                            await self.send_ws_message({
                                "type": "text_delta",
                                "content": chunk["content"]
                            })
                        elif chunk["type"] == "tool_call":
                            tool_calls_to_run.append(chunk)
                        elif chunk["type"] == "done":
                            stop_reason = chunk["stop_reason"]
                except Exception as e:
                    if "local" not in self.profile.get("model_name", "").lower():
                        logger.warning("AgentSession: Primary stream failed, triggering local fallback...")
                        from .adapters.router import ModelRouter
                        ModelRouter.notify_fallback(str(e))
                        
                        fallback_adapter = OpenAIAdapter(
                            api_key="ollama",
                            base_url="http://127.0.0.1:11434/v1",
                            model_name="llama3"
                        )
                        async for chunk in fallback_adapter.stream_chat(self.conversation_history, tools, system_prompt):
                            if chunk["type"] == "text":
                                response_text += chunk["content"]
                                await self.send_ws_message({
                                    "type": "text_delta",
                                    "content": chunk["content"]
                                })
                            elif chunk["type"] == "tool_call":
                                tool_calls_to_run.append(chunk)
                            elif chunk["type"] == "done":
                                stop_reason = chunk["stop_reason"]
                    else:
                        raise e
                
                # 2. Append assistant response to history
                assistant_msg = {"role": "assistant"}
                if response_text:
                    assistant_msg["content"] = response_text
                if tool_calls_to_run:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": tc["input"],
                            "thought_signature": tc.get("thought_signature")
                        }
                        for tc in tool_calls_to_run
                    ]
                
                self.conversation_history.append(assistant_msg)
                
                # If no tool calls, the turn loop is complete
                if not tool_calls_to_run:
                    break
                    
                # 3. Execute tool calls (potentially seeking user confirmation)
                tool_results = []
                for tc in tool_calls_to_run:
                    tc_id = tc["id"]
                    tc_name = tc["name"]
                    tc_args = tc["input"]
                    
                    await self.send_ws_message({
                        "type": "status",
                        "status": "tool_executing",
                        "message": f"Preparing tool '{tc_name}'...",
                        "tool_call": {"id": tc_id, "name": tc_name, "args": tc_args}
                    })
                    
                    try:
                        result = await self._execute_tool_with_guardrails(tc_id, tc_name, tc_args, auto_apply)
                        status = "success"
                    except Exception as e:
                        result = f"Error executing tool '{tc_name}': {str(e)}"
                        status = "error"
                        
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": result
                    })
                    
                    # Send result back to frontend for chat display
                    await self.send_ws_message({
                        "type": "tool_result",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "status": status,
                        "result": result
                    })
                    
                # Append tool outputs to history
                self.conversation_history.extend(tool_results)
                
                # Continue loop if more turns are needed
                # (implicitly handled by presence of tool calls)
                
            if turn >= self.max_turns:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "\n\n[Warning: Agent reached the maximum limit of 25 turns.]"
                })
            await self.send_ws_message({"type": "session_done"})
                
        except asyncio.CancelledError:
            await self.send_ws_message({"type": "session_done"})
            raise
        except Exception as e:
            logger.exception(f"Error in handle_user_message agent loop: {str(e)}")
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"\n\n[Error: {str(e)}]\n"
            })
            await self.send_ws_message({"type": "session_done"})
        finally:
            self.is_running = False
            await self.save_history_to_db()

    async def _execute_tool_with_guardrails(self, tc_id: str, name: str, args: dict, auto_apply: bool) -> str:
        """
        Executes a single tool. If the tool is mutative (write/edit) or destructive (terminal commands),
        it prompts the user for confirmation unless auto-apply is true.
        """
        # A. File write/edit safety check
        if name in ("write_file", "edit_file"):
            path = args.get("path")
            
            # Resolve original and proposed content for diff view
            original_content = ""
            proposed_content = ""
            
            try:
                # Resolve path
                abs_path = safe_path(self.workspace_root, path)
                if os.path.exists(abs_path) and os.path.isfile(abs_path):
                    original_content = await async_read_workspace_file(self.workspace_root, path)
            except Exception as e:
                return f"Path verification failed: {str(e)}"
                
            if name == "write_file":
                proposed_content = args.get("content", "")
            elif name == "edit_file":
                target = args.get("target", "").replace("\r\n", "\n")
                replacement = args.get("replacement", "").replace("\r\n", "\n")
                args["target"] = target
                args["replacement"] = replacement
                if target not in original_content:
                    raise ValueError(f"Target block not found in file '{path}'. Edit failed.")
                if original_content.count(target) > 1:
                    raise ValueError(f"Target block occurs multiple times in file '{path}'. Make target block more unique.")
                proposed_content = original_content.replace(target, replacement, 1)

            # Check if user confirmation is required
            if not auto_apply:
                from .diff_utils import generate_hunks, apply_hunks
                hunks = generate_hunks(original_content, proposed_content)
                
                # Ask frontend for approval
                event = asyncio.Event()
                self.pending_confirmations[tc_id] = {"event": event, "approved": False, "hunk_decisions": None}
                
                await self.send_ws_message({
                    "type": "confirm_request",
                    "tool_call_id": tc_id,
                    "tool_name": name,
                    "args": args,
                    "diff": {
                        "path": path,
                        "original": original_content,
                        "proposed": proposed_content,
                        "hunks": hunks
                    }
                })
                
                # Wait for websocket confirmation response
                await event.wait()
                
                decision = self.pending_confirmations[tc_id]
                del self.pending_confirmations[tc_id]
                
                if not decision["approved"]:
                    self.log_audit(name, args, "rejected", "User rejected file modification.")
                    return "Action cancelled by the user."
                
                # Reconstruct content based on hunk decisions
                hunk_decisions = decision.get("hunk_decisions")
                if hunk_decisions is not None:
                    proposed_content = apply_hunks(original_content, hunks, hunk_decisions)
                # If hunk_decisions is None, it means the user accepted the entire file edits as a whole

            # Perform the actual write
            await async_write_workspace_file(self.workspace_root, path, proposed_content)
            self.log_audit(name, args, "success", f"Modified {path}")
            return f"Successfully updated file '{path}'."

        # B. Destructive/Terminal Command safety check
        elif name == "run_terminal_command":
            cmd = args.get("command", "")
            
            is_approved = False
            risk = "mutative"
            reason = ""
            
            if self.permission_manager:
                is_approved, risk, reason = self.permission_manager.check_permission(cmd)
                
            # If not auto-approved, request permission via popup dialog
            if not is_approved:
                event = asyncio.Event()
                self.pending_confirmations[tc_id] = {
                    "event": event, 
                    "approved": False,
                    "scope": "once",
                    "command": cmd
                }
                
                explanation = f"Runs the terminal command: `{cmd}`"
                
                await self.send_ws_message({
                    "type": "permission_request",
                    "tool_call_id": tc_id,
                    "tool_name": name,
                    "command": cmd,
                    "risk": risk,
                    "reason": reason,
                    "explanation": explanation,
                    "args": args
                })
                
                await event.wait()
                decision = self.pending_confirmations[tc_id]
                del self.pending_confirmations[tc_id]
                
                if not decision["approved"]:
                    self.log_audit(name, args, "rejected", "User rejected command execution.")
                    return "Action cancelled by the user."
                    
                # Extract potentially edited command and scope
                cmd = decision.get("command", cmd)
                scope = decision.get("scope", "once")
                
                # Grant permission if session/project level was chosen
                if scope in ("session", "project") and self.permission_manager:
                    self.permission_manager.grant_permission(cmd, scope)
            
            # Execute command
            self.log_audit(name, args, "pending", f"Running command: {cmd}")
            result = await self._run_shell_command(cmd)
            self.log_audit(name, args, "success", f"Command stdout returned: {len(result)} bytes")
            return result

        # C. Read-only tools (no approval required)
        elif name == "list_directory":
            path = args.get("path", "")
            items = await async_list_workspace_dir(self.workspace_root, path)
            return json.dumps(items, indent=2)
            
        elif name == "read_file":
            path = args.get("path", "")
            return await async_read_workspace_file(self.workspace_root, path)
            
        elif name == "search_codebase":
            query = args.get("query", "")
            results = await async_search_workspace_codebase(self.workspace_root, query)
            return json.dumps(results, indent=2)
            
            
        else:
            raise NotImplementedError(f"Tool '{name}' is not supported.")

    async def _run_shell_command(self, command: str) -> str:
        """
        Runs a shell command asynchronously and streams stdout/stderr combined in real time.
        """
        import sys
        import time
        
        # Working directory lock check
        if "cd .." in command or "cd/" in command or re.search(r'\bcd\b.*\.\.', command):
            return "Failed to execute command: Access denied: changing directory outside the workspace root is locked."

        from .shell_adapter import ShellAdapter
        shell_executable = ShellAdapter.get_shell_executable(interactive=False)

        kwargs = {}
        if sys.platform == "win32":
            import subprocess
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            import pwd
            def drop_privileges():
                try:
                    nobody = pwd.getpwnam('nobody')
                    os.setgid(nobody.pw_gid)
                    os.setuid(nobody.pw_uid)
                except Exception:
                    pass
            kwargs["preexec_fn"] = drop_privileges
            
        start_time = time.time()
        
        # Send initial execution state
        await self.send_ws_message({
            "type": "terminal_status",
            "status": "running",
            "command": command
        })
        
        try:
            process = await asyncio.create_subprocess_exec(
                *shell_executable,
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.workspace_root,
                **kwargs
            )
            
            from .processes import confine_subprocess
            try:
                confine_subprocess(process.pid)
            except Exception:
                pass

            output_chunks = []
            while True:
                elapsed = time.time() - start_time
                remaining = 30.0 - elapsed
                if remaining <= 0:
                    raise asyncio.TimeoutError()

                try:
                    line_bytes = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
                except asyncio.TimeoutError:
                    raise

                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                output_chunks.append(line)
                
                # Stream terminal line to client
                await self.send_ws_message({
                    "type": "terminal_stream",
                    "content": line
                })
                
            try:
                exit_code = await asyncio.wait_for(process.wait(), timeout=max(1.0, 30.0 - (time.time() - start_time)))
            except asyncio.TimeoutError:
                raise
            elapsed_time = round(time.time() - start_time, 2)
            
            # Send terminal finished status
            await self.send_ws_message({
                "type": "terminal_status",
                "status": "completed",
                "exit_code": exit_code,
                "elapsed": elapsed_time
            })
            
            output = "".join(output_chunks)
            return output if output.strip() else "[Command executed with no output]"
        except asyncio.TimeoutError:
            elapsed_time = round(time.time() - start_time, 2)
            try:
                if sys.platform == "win32":
                    import subprocess
                    subprocess.call(f"taskkill /F /T /PID {process.pid}", shell=True)
                else:
                    process.kill()
            except Exception:
                pass
            await self.send_ws_message({
                "type": "terminal_status",
                "status": "failed",
                "exit_code": -1,
                "elapsed": elapsed_time
            })
            return "Failed to execute command: Command timed out after 30 seconds."
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 2)
            await self.send_ws_message({
                "type": "terminal_status",
                "status": "failed",
                "exit_code": -1,
                "elapsed": elapsed_time
            })
            return f"Failed to execute command: {str(e)}"

    def resolve_confirmation(self, tool_call_id: str, approved: bool, scope: str = "once", edited_command: str = None, hunk_decisions: dict = None):
        """
        Called when the user clicks Accept or Reject in the frontend.
        """
        if tool_call_id in self.pending_confirmations:
            if "action" in self.pending_confirmations[tool_call_id]:
                self.pending_confirmations[tool_call_id]["action"] = scope
                self.pending_confirmations[tool_call_id]["event"].set()
                return
            self.pending_confirmations[tool_call_id]["approved"] = approved
            self.pending_confirmations[tool_call_id]["scope"] = scope
            self.pending_confirmations[tool_call_id]["hunk_decisions"] = hunk_decisions
            if edited_command is not None:
                self.pending_confirmations[tool_call_id]["command"] = edited_command
            self.pending_confirmations[tool_call_id]["event"].set()

    async def _run_llm_query(self, system_prompt: str, user_content: str, agent_name: str = None) -> str:
        """
        Queries the LLM non-disruptively by accumulating stream_chat chunks.
        Uses ModelRouter to support automatic local model fallbacks on connection/API failure.
        """
        from .adapters.router import ModelRouter
        messages = [{"role": "user", "content": user_content}]
        try:
            router = ModelRouter()
            response_text = await router.completion(self.profile, messages, system_prompt, is_agent=True, task_type=agent_name)
            return response_text
        except Exception as e:
            logger.error(f"Error querying background LLM (including fallbacks): {str(e)}")
            raise e

    async def broadcast_processes_state(self):
        from .processes import global_process_manager
        procs = global_process_manager.get_all_processes()
        serialized = []
        for p in procs:
            serialized.append({
                "id": p.id,
                "name": p.name,
                "command": p.command,
                "status": p.status,
                "port": p.port,
                "localhost_url": p.localhost_url,
                "network_url": p.network_url,
                "pid": p.pid
            })
        await self.send_ws_message({
            "type": "processes_update",
            "processes": serialized
        })

    async def monitor_and_stream_events(self, proc):
        await self.broadcast_processes_state()
        last_index = 0
        reported_events = set()
        while proc.status in ("starting", "running"):
            if last_index < len(proc.logs):
                new_lines = proc.logs[last_index:]
                last_index = len(proc.logs)
                for line in new_lines:
                    await self.send_ws_message({
                        "type": "terminal_stream",
                        "content": line
                    })
                    line_lower = line.lower()
                    event_msg = None
                    if "hmr update" in line_lower or "hot update" in line_lower:
                        event_msg = "✓ Hot Reload completed"
                    elif "compiled successfully" in line_lower:
                        event_msg = "✓ Build completed successfully"
                    elif "database connected" in line_lower or "db connected" in line_lower or "connected to database" in line_lower:
                        event_msg = "✓ Connected to database"
                    elif "api ready" in line_lower or "api server ready" in line_lower:
                        event_msg = "✓ API server ready"
                    elif "rebuilding" in line_lower or "rebuilt" in line_lower:
                        event_msg = "✓ Server rebuild complete"
                    
                    if event_msg and event_msg not in reported_events:
                        await self.send_ws_message({
                            "type": "text_delta",
                            "content": f"\n{event_msg}\n"
                        })
                        reported_events.add(event_msg)
            await asyncio.sleep(0.1)
        await self.broadcast_processes_state()

    async def run_agent_flow(self, user_text: str):
        await self.send_ws_message({
            "type": "status",
            "status": "thinking",
            "message": "Run Agent: Detecting project type..."
        })
        
        files_list = []
        try:
            items = await async_list_workspace_dir(self.workspace_root, "")
            for it in items:
                files_list.append(it["name"])
                if it.get("is_dir", it.get("isDir", False)) and it["name"] not in (".git", "node_modules", "venv", "__pycache__", ".devpilot"):
                    try:
                        sub_items = await async_list_workspace_dir(self.workspace_root, it["name"])
                        for s_it in sub_items[:15]:
                            files_list.append(f"{it['name']}/{s_it['name']}")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error listing workspace files: {str(e)}")

        prompt = (
            f"The user wants to run/start the project. User request: '{user_text}'\n"
            f"Workspace files:\n{json.dumps(files_list, indent=2)}\n\n"
            "Analyze the workspace files and the user request to determine:\n"
            "1. The project/service type or framework (e.g. 'React (Vite)', 'FastAPI', 'Python Flask', etc.).\n"
            "2. The exact terminal command to run, start, or serve the requested service/project.\n"
            "Ensure the command is correct for this project structure. If a subdirectory (like 'frontend' or 'backend') has a package.json or main.py and the user specifies it, make sure to include directory navigation or a prefix (e.g. 'npm run dev --prefix frontend' or navigate to it first).\n\n"
            "Output your response strictly as a JSON object with two fields:\n"
            "- 'framework': a string indicating the framework/language/service name (e.g. 'React (Vite)', 'FastAPI', 'Flask', 'Django', etc.)\n"
            "- 'command': the exact command to run/start/serve the application (e.g. 'npm run dev', 'uvicorn main:app --reload', etc.)\n"
            "Respond with ONLY the JSON object, no other text."
        )
        system_prompt = "You are a master developer assistant. Analyze the project structure and output the correct run command in JSON format."
        
        response = await self._run_llm_query(system_prompt, prompt)
        
        try:
            clean_res = response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            parsed = json.loads(clean_res.strip())
            framework = parsed.get("framework") or "Unknown Framework"
            command = parsed.get("command")
            if not command or not isinstance(command, str) or not command.strip():
                raise ValueError("Command field is missing, empty, or not a string in LLM response.")
        except Exception as e:
            logger.error(f"Failed to parse LLM run command JSON: {str(e)}")
            framework = "Unknown"
            if "package.json" in files_list:
                command = "npm run dev"
            elif "main.py" in files_list:
                command = "python main.py"
            else:
                command = "python -m http.server 8000"

        await self.send_ws_message({
            "type": "text_delta",
            "content": f"**Detected project type:** {framework}\n**Suggested command:** `{command}`\n\n"
        })

        is_approved = False
        risk = "mutative"
        reason = "Run Agent execution"
        if self.permission_manager:
            is_approved, risk, reason = self.permission_manager.check_permission(command)
            
        if not is_approved:
            tc_id = f"run_{uuid.uuid4().hex[:6]}"
            event = asyncio.Event()
            self.pending_confirmations[tc_id] = {
                "event": event,
                "approved": False,
                "scope": "once",
                "command": command
            }
            
            await self.send_ws_message({
                "type": "permission_request",
                "tool_call_id": tc_id,
                "tool_name": "run_terminal_command",
                "command": command,
                "risk": risk,
                "reason": reason,
                "explanation": f"The Run Agent wants to run the project using command: `{command}`",
                "args": {"command": command}
            })
            
            await event.wait()
            decision = self.pending_confirmations[tc_id]
            del self.pending_confirmations[tc_id]
            
            if not decision["approved"]:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "*Execution cancelled by the user.*\n"
                })
                return
            command = decision.get("command", command)

        await self.send_ws_message({
            "type": "status",
            "status": "tool_executing",
            "message": f"Starting project with `{command}`..."
        })
        
        proc = await global_process_manager.start_process(command, self.workspace_root, name=framework)
        asyncio.create_task(self.monitor_and_stream_events(proc))
        
        for _ in range(40):
            await asyncio.sleep(0.25)
            if proc.startup_success_event.is_set():
                break
            if proc.status in ("stopped", "failed", "crashed"):
                break
                
        if proc.port_conflict:
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"⚠️ Port conflict detected: Port {proc.port} is already in use.\n"
            })
            
            conflict_pid, conflict_name = get_process_using_port(proc.port)
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Process `{conflict_name}` (PID: {conflict_pid}) is using port {proc.port}.\n"
            })
            
            tc_id = f"port_{uuid.uuid4().hex[:6]}"
            event = asyncio.Event()
            self.pending_confirmations[tc_id] = {
                "event": event,
                "action": None
            }
            
            await self.send_ws_message({
                "type": "port_conflict_request",
                "tool_call_id": tc_id,
                "port": proc.port,
                "pid": conflict_pid,
                "process_name": conflict_name
            })
            
            await event.wait()
            action = self.pending_confirmations[tc_id].get("action")
            del self.pending_confirmations[tc_id]
            
            if action == "stop":
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Stopping conflicting process `{conflict_name}` (PID: {conflict_pid})...\n"
                })
                kill_process_by_pid(conflict_pid)
                await global_process_manager.stop_process(proc.id)
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Retrying run command: `{command}`\n"
                })
                proc = await global_process_manager.start_process(command, self.workspace_root, name=framework)
                asyncio.create_task(self.monitor_and_stream_events(proc))
                for _ in range(40):
                    await asyncio.sleep(0.25)
                    if proc.startup_success_event.is_set():
                        break
                    if proc.status in ("stopped", "failed", "crashed"):
                        break
            elif action == "next_port":
                next_port = proc.port + 1
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Determining run command for next available port: {next_port}...\n"
                })
                rewrite_prompt = (
                    f"The run command `{command}` failed because port {proc.port} is in use.\n"
                    f"Please modify the command so it runs on port {next_port}.\n"
                    "Respond with ONLY the modified command string, e.g. 'PORT=5174 npm run dev' or 'uvicorn main:app --port 8001'."
                )
                new_command = await self._run_llm_query("You are a devops engineer helper.", rewrite_prompt)
                new_command = new_command.strip().strip("`").strip()
                
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": f"Retrying with command: `{new_command}`\n"
                })
                await global_process_manager.stop_process(proc.id)
                proc = await global_process_manager.start_process(new_command, self.workspace_root, name=framework)
                asyncio.create_task(self.monitor_and_stream_events(proc))
                for _ in range(40):
                    await asyncio.sleep(0.25)
                    if proc.startup_success_event.is_set():
                        break
                    if proc.status in ("stopped", "failed", "crashed"):
                        break
            else:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "Startup cancelled by the user.\n"
                })
                await global_process_manager.stop_process(proc.id)
                return

        if proc.status == "running":
            localhost_url = proc.localhost_url or f"http://localhost:{proc.port}"
            network_url = proc.network_url or "N/A"
            port_str = str(proc.port) if proc.port else "N/A"
            
            content_summary = (
                "**Application started successfully.**\n\n"
                f"Framework: **{framework}**\n"
                "Status: **Running**\n"
                f"Local URL: [{localhost_url}]({localhost_url})\n"
                f"Network URL: {network_url}\n"
                f"Port: [{port_str}]({localhost_url})\n"
                f"Process ID: **{proc.pid}**\n"
            )
            await self.send_ws_message({
                "type": "text_delta",
                "content": content_summary
            })
        else:
            await self.send_ws_message({
                "type": "text_delta",
                "content": "❌ Application failed to start.\n"
            })
            await self.handle_intelligent_recovery(proc, command, framework)

    async def handle_intelligent_recovery(self, proc, original_command: str, framework: str):
        await self.send_ws_message({
            "type": "status",
            "status": "thinking",
            "message": "Terminal Analysis Agent: Diagnosing startup failure..."
        })
        
        logs_snippet = "".join(proc.logs[-30:])
        prompt = (
            f"The terminal command `{original_command}` failed to start the project. Here are the last few lines of terminal logs:\n"
            f"{logs_snippet}\n\n"
            "Analyze the log output to determine the root cause and propose a fix. If the fix is a command we can run "
            "(e.g. running 'npm install' or 'pip install' or installing a missing package), set 'can_auto_fix' to true and provide the command.\n"
            "Output your response strictly as a JSON object:\n"
            "{\n"
            "  \"root_cause\": \"A clear, user-friendly explanation of why it failed\",\n"
            "  \"fix_suggestion\": \"What needs to be done to fix it\",\n"
            "  \"fix_command\": \"Optional shell command to execute the fix\",\n"
            "  \"can_auto_fix\": true\n"
            "}\n"
            "Respond with ONLY the JSON object, no other text."
        )
        system_prompt = "You are a senior codebase auditor and devops expert. Analyze logs and output JSON diagnostics."
        
        response = await self._run_llm_query(system_prompt, prompt)
        
        try:
            clean_res = response.strip()
            if clean_res.startswith("```json"):
                clean_res = clean_res[7:]
            if clean_res.endswith("```"):
                clean_res = clean_res[:-3]
            parsed = json.loads(clean_res.strip())
            
            root_cause = parsed.get("root_cause", "Unknown error")
            fix_suggestion = parsed.get("fix_suggestion", "Check logs and configure correctly")
            fix_command = parsed.get("fix_command")
            can_auto_fix = parsed.get("can_auto_fix", False)
        except Exception as e:
            logger.error(f"Failed to parse LLM diagnostics response: {str(e)}")
            root_cause = "Unknown startup error."
            fix_suggestion = "Inspect terminal output and dependencies."
            fix_command = None
            can_auto_fix = False
            
        await self.send_ws_message({
            "type": "text_delta",
            "content": f"### Diagnostic Report\n* **Root Cause:** {root_cause}\n* **Suggestion:** {fix_suggestion}\n\n"
        })
        
        if can_auto_fix and fix_command:
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Attempting automatic recovery: Running `{fix_command}`...\n"
            })
            
            is_approved = False
            risk = "mutative"
            reason = "Run Agent automatic fix execution"
            if self.permission_manager:
                is_approved, risk, reason = self.permission_manager.check_permission(fix_command)
                
            if not is_approved:
                tc_id = f"fix_{uuid.uuid4().hex[:6]}"
                event = asyncio.Event()
                self.pending_confirmations[tc_id] = {
                    "event": event,
                    "approved": False,
                    "scope": "once",
                    "command": fix_command
                }
                
                await self.send_ws_message({
                    "type": "permission_request",
                    "tool_call_id": tc_id,
                    "tool_name": "run_terminal_command",
                    "command": fix_command,
                    "risk": risk,
                    "reason": reason,
                    "explanation": f"Run Agent wants to run fix command: `{fix_command}`",
                    "args": {"command": fix_command}
                })
                
                await event.wait()
                decision = self.pending_confirmations[tc_id]
                del self.pending_confirmations[tc_id]
                
                if not decision["approved"]:
                    await self.send_ws_message({
                        "type": "text_delta",
                        "content": "*Automatic recovery cancelled by user.*\n"
                    })
                    return
                fix_command = decision.get("command", fix_command)

            await self.send_ws_message({
                "type": "status",
                "status": "tool_executing",
                "message": f"Executing fix command: `{fix_command}`..."
            })
            
            result = await self._run_shell_command(fix_command)
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Fix command finished. Output:\n```\n{result[:500]}...\n```\n"
            })
            
            await self.send_ws_message({
                "type": "text_delta",
                "content": f"Retrying run command: `{original_command}`\n"
            })
            
            await global_process_manager.stop_process(proc.id)
            proc = await global_process_manager.start_process(original_command, self.workspace_root, name=framework)
            asyncio.create_task(self.monitor_and_stream_events(proc))
            
            for _ in range(40):
                await asyncio.sleep(0.25)
                if proc.startup_success_event.is_set():
                    break
                if proc.status in ("stopped", "failed", "crashed"):
                    break
                    
            if proc.status == "running":
                localhost_url = proc.localhost_url or f"http://localhost:{proc.port}"
                network_url = proc.network_url or "N/A"
                port_str = str(proc.port) if proc.port else "N/A"
                content_summary = (
                    "**Application recovered and started successfully!**\n\n"
                    f"Framework: **{framework}**\n"
                    "Status: **Running**\n"
                    f"Local URL: [{localhost_url}]({localhost_url})\n"
                    f"Network URL: {network_url}\n"
                    f"Port: [{port_str}]({localhost_url})\n"
                    f"Process ID: **{proc.pid}**\n"
                )
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": content_summary
                })
            else:
                await self.send_ws_message({
                    "type": "text_delta",
                    "content": "❌ Application failed to start after automatic recovery attempt. Please inspect logs.\n"
                })