"""Phase 1 — Context Collector.

Before the LLM is called, automatically collect all information
the agent already has access to. This prevents the "which engine?"
problem where the agent asks questions that a file in the workspace
already answers.

Collection steps (in order):
  1. Parse query for file references → read them
  2. Parse query for symbol references → locate in workspace index
  3. Read README.md / PRD.md / GDD.md / SPEC.md if they exist
  4. Read manifest files (package.json, pyproject.toml, requirements.txt, go.mod, Cargo.toml)
  5. Read configuration files (.env.example, tsconfig.json, vite.config.*)
  6. List referenced directories
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("devpilot.agent.context_collector")

# Known spec/doc filenames to always try to read
_SPEC_FILENAMES = {
    "readme.md", "readme.txt", "prd.md", "gdd.md", "spec.md",
    "requirements.md", "design.md", "architecture.md", "overview.md",
    "changelog.md", "contributing.md", "docs/readme.md",
}

# Manifest files (project definition)
_MANIFEST_FILENAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "go.mod",
    "cargo.toml", "composer.json", "gemfile", "build.gradle",
    "pom.xml", "setup.py", "setup.cfg",
}

# Config files (tech stack context)
_CONFIG_FILENAMES = {
    ".env.example", ".env.sample", "tsconfig.json", "vite.config.ts",
    "vite.config.js", "webpack.config.js", "next.config.js", "next.config.ts",
    "tailwind.config.js", "tailwind.config.ts", "jest.config.js",
    "jest.config.ts", "pytest.ini", "pyproject.toml", "docker-compose.yml",
    "docker-compose.yaml", ".dockerignore", "makefile",
}

# Max characters to read per file (to avoid context bloat)
_MAX_FILE_CHARS = 8000
_MAX_FILES_TO_AUTO_READ = 6


@dataclass
class CollectedContext:
    """All context automatically gathered before the LLM is invoked."""
    files_read: dict[str, str] = field(default_factory=dict)    # path → content
    symbols_found: dict[str, str] = field(default_factory=dict) # symbol → file:line
    manifest_content: str = ""
    spec_content: str = ""
    config_hints: list[str] = field(default_factory=list)
    workspace_structure: str = ""
    collection_notes: list[str] = field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Format collected context into a prompt injection block."""
        parts = []

        if self.spec_content:
            parts.append(f"## Specification / Documentation\n{self.spec_content}")

        if self.manifest_content:
            parts.append(f"## Project Manifest\n{self.manifest_content}")

        if self.files_read:
            file_blocks = []
            for path, content in self.files_read.items():
                file_blocks.append(f"### {path}\n```\n{content}\n```")
            parts.append("## Referenced Files\n" + "\n\n".join(file_blocks))

        if self.symbols_found:
            sym_lines = [f"- `{sym}` found in `{loc}`" for sym, loc in self.symbols_found.items()]
            parts.append("## Symbol Locations\n" + "\n".join(sym_lines))

        if self.config_hints:
            parts.append("## Tech Stack Hints\n" + "\n".join(f"- {h}" for h in self.config_hints))

        if self.workspace_structure:
            parts.append(f"## Workspace Structure\n{self.workspace_structure}")

        if self.collection_notes:
            parts.append("## Collection Notes\n" + "\n".join(f"- {n}" for n in self.collection_notes))

        if not parts:
            return ""

        return (
            "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "AUTO-COLLECTED CONTEXT (gathered before LLM reasoning)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            + "\n\n".join(parts)
        )


class ContextCollector:
    """Automatically reads workspace files before the LLM is called.

    Usage:
        collector = ContextCollector(workspace_root)
        ctx = await collector.collect(user_query, intent_result)
        system_prompt += ctx.to_prompt_block()
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    async def collect(
        self,
        user_query: str,
        referenced_files: list[str],
        referenced_symbols: list[str],
        spec_file: str | None = None,
    ) -> CollectedContext:
        """Collect all relevant context for a given user query.

        Args:
            user_query: The raw user message.
            referenced_files: File paths mentioned in the query (from IntentRouter).
            referenced_symbols: Symbol names mentioned in the query.
            spec_file: Spec document to read first (for IMPLEMENT_SPEC intent).

        Returns:
            CollectedContext with all pre-gathered information.
        """
        ctx = CollectedContext()

        if not self.workspace_root or not os.path.isdir(self.workspace_root):
            ctx.collection_notes.append("No workspace open — skipping context collection.")
            return ctx

        root = Path(self.workspace_root)
        files_read_count = 0

        # ── Step 1: Read spec file (highest priority) ───────────────────
        if spec_file:
            content = self._try_read(root, spec_file)
            if content:
                ctx.spec_content = f"**{spec_file}**\n\n{content}"
                ctx.collection_notes.append(f"Read spec file: {spec_file}")
                files_read_count += 1
            else:
                ctx.collection_notes.append(f"Spec file '{spec_file}' not found — searched workspace.")

        # ── Step 2: Read any other explicitly referenced files ───────────
        for ref_file in referenced_files:
            if ref_file == spec_file:
                continue
            if files_read_count >= _MAX_FILES_TO_AUTO_READ:
                ctx.collection_notes.append(f"Auto-read limit ({_MAX_FILES_TO_AUTO_READ}) reached — skipped remaining file refs.")
                break
            content = self._try_read(root, ref_file)
            if content:
                ctx.files_read[ref_file] = content
                ctx.collection_notes.append(f"Auto-read referenced file: {ref_file}")
                files_read_count += 1

        # ── Step 3: Locate referenced symbols ───────────────────────────
        if referenced_symbols:
            self._find_symbols(root, referenced_symbols, ctx)

        # ── Step 4: Read README / GDD / PRD if not already read ─────────
        if not ctx.spec_content:
            for spec_name in _SPEC_FILENAMES:
                content = self._try_read(root, spec_name)
                if content:
                    ctx.spec_content = f"**{spec_name}**\n\n{content}"
                    ctx.collection_notes.append(f"Auto-read spec document: {spec_name}")
                    break

        # ── Step 5: Read manifest files ──────────────────────────────────
        manifest_parts = []
        for manifest_name in _MANIFEST_FILENAMES:
            content = self._try_read(root, manifest_name, max_chars=4000)
            if content:
                manifest_parts.append(f"**{manifest_name}**\n```\n{content}\n```")
                ctx.collection_notes.append(f"Read manifest: {manifest_name}")
                break  # One manifest is enough

        if manifest_parts:
            ctx.manifest_content = "\n\n".join(manifest_parts)

        # ── Step 6: Extract tech stack hints from config files ───────────
        ctx.config_hints = self._detect_tech_stack(root)

        # ── Step 7: Get workspace structure ─────────────────────────────
        ctx.workspace_structure = self._get_workspace_structure(root)

        return ctx

    def _try_read(self, root: Path, rel_path: str, max_chars: int = _MAX_FILE_CHARS) -> str | None:
        """Try to read a file relative to workspace root. Returns None if not found."""
        # Try exact path
        candidates = [
            root / rel_path,
            root / rel_path.lower(),
        ]
        # Also search recursively for the filename (not path)
        filename = Path(rel_path).name.lower()
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower() == filename:
                    candidates.append(Path(dirpath) / f)
            if len(candidates) > 10:
                break

        for candidate in candidates:
            try:
                if candidate.is_file():
                    content = candidate.read_text(encoding="utf-8", errors="replace")
                    if len(content) > max_chars:
                        content = content[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
                    return content
            except Exception:
                continue
        return None

    def _find_symbols(self, root: Path, symbols: list[str], ctx: CollectedContext) -> None:
        """Search for symbol definitions in Python and TypeScript files."""
        import re
        found = {}
        search_exts = {".py", ".ts", ".tsx", ".js", ".jsx"}
        skip_dirs = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", ".next"}

        target_symbols = set(s.lower() for s in symbols[:10])  # cap to 10

        try:
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for fname in files:
                    if not any(fname.endswith(ext) for ext in search_exts):
                        continue
                    fpath = Path(dirpath) / fname
                    try:
                        lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
                        for lineno, line in enumerate(lines, 1):
                            for sym in target_symbols:
                                if sym in line.lower() and re.search(
                                    r'\b(class|def|function|const|let|var|interface|type)\s+', line
                                ):
                                    rel = str(fpath.relative_to(root))
                                    found[sym] = f"{rel}:{lineno}"
                                    target_symbols.discard(sym)
                                    break
                    except Exception:
                        continue
                    if not target_symbols:
                        break
        except Exception as e:
            ctx.collection_notes.append(f"Symbol search error: {e}")

        ctx.symbols_found = found

    def _detect_tech_stack(self, root: Path) -> list[str]:
        """Detect technology stack from config files."""
        hints = []

        def exists(name: str) -> bool:
            return (root / name).exists()

        def read_json(name: str) -> dict:
            try:
                import json
                return json.loads((root / name).read_text(encoding="utf-8"))
            except Exception:
                return {}

        if exists("package.json"):
            pkg = read_json("package.json")
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "react" in deps:
                hints.append("Frontend: React")
            if "vue" in deps:
                hints.append("Frontend: Vue")
            if "svelte" in deps:
                hints.append("Frontend: Svelte")
            if "next" in deps:
                hints.append("Framework: Next.js")
            if "vite" in deps:
                hints.append("Bundler: Vite")
            if "typescript" in deps:
                hints.append("Language: TypeScript")
            if pkg.get("scripts"):
                dev_cmd = pkg["scripts"].get("dev") or pkg["scripts"].get("start")
                if dev_cmd:
                    hints.append(f"Dev command: {dev_cmd}")

        if exists("requirements.txt") or exists("pyproject.toml"):
            hints.append("Language: Python")
            try:
                content = ""
                if exists("requirements.txt"):
                    content = (root / "requirements.txt").read_text(encoding="utf-8")
                elif exists("pyproject.toml"):
                    content = (root / "pyproject.toml").read_text(encoding="utf-8")
                if "fastapi" in content.lower():
                    hints.append("Framework: FastAPI")
                elif "django" in content.lower():
                    hints.append("Framework: Django")
                elif "flask" in content.lower():
                    hints.append("Framework: Flask")
            except Exception:
                pass

        if exists("go.mod"):
            hints.append("Language: Go")
        if exists("Cargo.toml"):
            hints.append("Language: Rust")
        if exists("pom.xml"):
            hints.append("Language: Java (Maven)")
        if exists("Dockerfile"):
            hints.append("Containerised: Docker")
        if exists("docker-compose.yml") or exists("docker-compose.yaml"):
            hints.append("Orchestration: Docker Compose")

        return hints

    def _get_workspace_structure(self, root: Path) -> str:
        """Return a compact top-level file/folder listing."""
        skip = {"node_modules", "__pycache__", ".git", "venv", ".venv", "dist", ".next", ".mypy_cache"}
        try:
            lines = []
            for item in sorted(root.iterdir()):
                if item.name.startswith(".") and item.name not in {".env.example", ".gitignore"}:
                    continue
                if item.name in skip:
                    continue
                if item.is_dir():
                    lines.append(f"📁 {item.name}/")
                else:
                    lines.append(f"📄 {item.name}")
            return "\n".join(lines[:40])  # cap at 40 entries
        except Exception:
            return ""
