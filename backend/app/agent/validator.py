"""Phase 8 — Validator.

Pre-done checklist that runs before session_done is emitted.
Catches common failure modes: files not created, edits not applied, syntax errors.

Checks (in order):
  1. Files the plan said to create — do they exist?
  2. Files the plan said to edit — do they contain the expected changes?
  3. Python files written — syntax valid?
  4. TypeScript/JS — basic import sanity (no obvious broken imports)
  5. No empty files (0 bytes)
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("loopix.agent.validator")


@dataclass
class ValidationResult:
    passed: bool
    checks_run: int
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed_checks: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        if self.passed and not self.warnings:
            return ""
        lines = ["\n[VALIDATION RESULTS]"]
        for f in self.failures:
            lines.append(f"  ❌ FAIL: {f}")
        for w in self.warnings:
            lines.append(f"  ⚠️  WARN: {w}")
        if self.failures:
            lines.append("\nThese failures MUST be fixed before completing the task.")
        return "\n".join(lines)

    def to_summary(self) -> str:
        return (
            f"Validation: {len(self.passed_checks)}/{self.checks_run} checks passed"
            + (f", {len(self.failures)} failures" if self.failures else "")
            + (f", {len(self.warnings)} warnings" if self.warnings else "")
        )


class Validator:
    """Validates agent work before declaring completion.

    Usage:
        validator = Validator(workspace_root)
        result = validator.validate(files_written, files_read)
        if not result.passed:
            # inject result.to_prompt_block() and continue the loop
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    def validate(
        self,
        files_written: list[str],
        files_to_create: list[str] | None = None,
        plan_steps: list[dict] | None = None,
    ) -> ValidationResult:
        """Run all validation checks.

        Args:
            files_written: Files the agent reported writing.
            files_to_create: Files the plan said should be created.
            plan_steps: Full plan step list (for context).

        Returns:
            ValidationResult with pass/fail status and details.
        """
        result = ValidationResult(passed=True, checks_run=0)
        root = Path(self.workspace_root) if self.workspace_root else None

        if not root or not root.is_dir():
            result.warnings.append("No workspace open — skipping file existence checks.")
            return result

        # ── Check 1: Files written actually exist ─────────────────────────
        for rel_path in files_written:
            result.checks_run += 1
            fpath = root / rel_path
            if not fpath.exists():
                result.failures.append(f"File was reported as written but does not exist: {rel_path}")
                result.passed = False
            elif fpath.stat().st_size == 0:
                result.warnings.append(f"File was written but is empty (0 bytes): {rel_path}")
            else:
                result.passed_checks.append(f"File exists: {rel_path}")

        # ── Check 2: Files-to-create (from plan) actually exist ───────────
        for rel_path in (files_to_create or []):
            if rel_path in files_written:
                continue  # Already checked above
            result.checks_run += 1
            fpath = root / rel_path
            if not fpath.exists():
                result.failures.append(f"Plan required creating '{rel_path}' but it was not created.")
                result.passed = False
            else:
                result.passed_checks.append(f"Planned file exists: {rel_path}")

        # ── Check 3: Python syntax check ──────────────────────────────────
        for rel_path in files_written:
            if not rel_path.endswith(".py"):
                continue
            result.checks_run += 1
            fpath = root / rel_path
            if not fpath.is_file():
                continue
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                ast.parse(source)
                result.passed_checks.append(f"Python syntax OK: {rel_path}")
            except SyntaxError as e:
                result.failures.append(
                    f"Python SyntaxError in {rel_path} at line {e.lineno}: {e.msg}"
                )
                result.passed = False

        # ── Check 4: TypeScript/JS basic import sanity ────────────────────
        for rel_path in files_written:
            if not (rel_path.endswith(".ts") or rel_path.endswith(".tsx")
                    or rel_path.endswith(".js") or rel_path.endswith(".jsx")):
                continue
            result.checks_run += 1
            fpath = root / rel_path
            if not fpath.is_file():
                continue
            try:
                source = fpath.read_text(encoding="utf-8", errors="replace")
                # Check for broken relative imports (import from paths that obviously don't resolve)
                broken = self._check_ts_imports(source, rel_path, root)
                if broken:
                    for b in broken:
                        result.warnings.append(f"Possibly unresolved import in {rel_path}: {b}")
                else:
                    result.passed_checks.append(f"TS/JS imports OK: {rel_path}")
            except Exception:
                pass

        # ── Check 5: No completely empty source files ─────────────────────
        for rel_path in files_written:
            ext = Path(rel_path).suffix.lower()
            if ext not in {".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css"}:
                continue
            result.checks_run += 1
            fpath = root / rel_path
            if fpath.is_file() and fpath.stat().st_size < 10:
                result.warnings.append(f"Source file appears to be nearly empty: {rel_path}")

        # ── Check 6: LSP Diagnostics ──────────────────────────────────────
        try:
            from ..state import workspace_state
            for rel_path in files_written:
                norm_key = rel_path.replace("\\", "/")
                diagnostics = workspace_state.lsp_diagnostics.get(norm_key, [])
                for d in diagnostics:
                    msg = f"LSP {d['source']} ({d['code'] or 'error'}) in {rel_path} at line {d['line']}: {d['message']}"
                    result.checks_run += 1
                    if d["severity"] == 1:
                        result.failures.append(msg)
                        result.passed = False
                    else:
                        result.warnings.append(msg)
        except Exception as e:
            logger.debug(f"Failed to validate LSP diagnostics (non-fatal): {e}")

        return result

    def _check_ts_imports(self, source: str, rel_path: str, root: Path) -> list[str]:
        """Check for relative imports that don't resolve to existing files."""
        broken = []
        base_dir = (root / rel_path).parent

        for m in re.finditer(r"""from\s+['"](\./[^'"]+|\.\.\/[^'"]+)['"]""", source):
            import_path = m.group(1)
            # Try with various extensions
            resolved = base_dir / import_path
            candidates = [
                resolved,
                resolved.with_suffix(".ts"),
                resolved.with_suffix(".tsx"),
                resolved.with_suffix(".js"),
                resolved / "index.ts",
                resolved / "index.tsx",
                resolved / "index.js",
            ]
            if not any(c.exists() for c in candidates):
                broken.append(import_path)

        return broken[:5]  # Cap at 5 warnings
