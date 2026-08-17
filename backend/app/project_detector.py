"""
project_detector.py — AI-powered project analysis.

ALL detection is delegated to the LLM. Zero static rules.
The LLM reads the real file/directory listing and returns a JSON object
describing the framework, language, package manager, and run/build/test/install commands.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("loopix.project_detector")

# Files and directories to skip when listing the workspace
_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".loopix",
    "dist", "build", ".next", "target", "out", ".cache", "coverage",
    ".mypy_cache", ".pytest_cache", "htmlcov", ".tox",
}
_SKIP_EXTS = {
    ".lock", ".pyc", ".pyo", ".map", ".min.js", ".min.css",
    ".wasm", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico",
    ".ttf", ".woff", ".woff2", ".eot", ".pdf",
}

_SYSTEM_PROMPT = (
    "You are a senior DevOps / full-stack engineer. "
    "Analyse a workspace file listing and return a JSON object that describes "
    "the project so a developer can run it instantly. "
    "Be exact: only suggest scripts that actually exist in package.json. "
    "Never invent scripts. "
    "For multi-service projects (e.g. separate frontend/ and backend/ directories) "
    "include every runnable service in the 'runnables' array."
)

_USER_PROMPT_TEMPLATE = """\
Workspace root: {root_name}

Files and directories present:
{file_list}

Key file contents:
{file_contents}

Return a JSON object with EXACTLY these fields (no extra text):
{{
  "name": "<project name, inferred from directory or package.json>",
  "framework": "<detected framework(s), e.g. 'React + Vite', 'FastAPI', 'Django', 'Static HTML'>",
  "language": "<primary language(s), e.g. 'TypeScript', 'Python', 'HTML/CSS/JS'>",
  "packageManager": "<npm | yarn | pnpm | bun | pip | cargo | go | gradle | mvn | godot | npx | system>",
  "installCommand": "<exact install command, or empty string>",
  "runCommand": "<exact command to start / serve the project, newline-separated if multi-service>",
  "buildCommand": "<exact build command, or empty string>",
  "testCommand": "<exact test command, or empty string>",
  "runnables": [
    {{
      "framework": "<service framework>",
      "language": "<service language>",
      "packageManager": "<service package manager>",
      "runCommand": "<service run command>",
      "installCommand": "<service install command>",
      "buildCommand": "<service build command>",
      "testCommand": "<service test command>",
      "dir": "<relative directory, '.' for root>"
    }}
  ]
}}

Rules:
- If this is a plain static HTML project (index.html, no framework), use: npx serve .
- Only include 'npm run dev' if a 'dev' script exists in package.json.
- Only include 'npm start' if a 'start' script exists in package.json.
- For multi-service repos, set runCommand to each service command separated by newlines.
- runnables must have at least one entry.
- Respond with ONLY valid JSON, no markdown fences, no prose.
"""


def _collect_workspace_snapshot(workspace_root: str) -> tuple[list[str], dict[str, str]]:
    """
    Returns (files_list, key_file_contents).
    files_list  – relative paths of every non-skipped file (max 400).
    key_file_contents – content of important config files (package.json, requirements.txt, etc.).
    """
    root = Path(workspace_root)
    files: list[str] = []
    key_contents: dict[str, str] = {}

    KEY_FILES = {
        "package.json", "requirements.txt", "pyproject.toml",
        "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "build.gradle.kts", "project.godot", "index.html",
        "Makefile", "docker-compose.yml", "docker-compose.yaml",
    }

    def _walk(path: Path, depth: int = 0):
        if depth > 3:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in {".env", ".env.example"}:
                continue
            if entry.name in _SKIP_DIRS:
                continue

            rel = str(entry.relative_to(root)).replace("\\", "/")

            if entry.is_dir():
                files.append(rel + "/")
                _walk(entry, depth + 1)
            elif entry.is_file():
                if any(entry.name.endswith(ext) for ext in _SKIP_EXTS):
                    continue
                files.append(rel)
                if len(files) > 400:
                    return

                # Capture key file contents (truncated)
                if entry.name in KEY_FILES and rel not in key_contents:
                    try:
                        text = entry.read_text(encoding="utf-8", errors="ignore")[:3000]
                        key_contents[rel] = text
                    except Exception:
                        pass

    _walk(root)
    return files, key_contents


def _build_user_prompt(workspace_root: str) -> str:
    root_name = Path(workspace_root).name
    files_list, key_contents = _collect_workspace_snapshot(workspace_root)

    file_list_str = "\n".join(files_list) if files_list else "(empty workspace)"

    contents_str = ""
    if key_contents:
        parts = []
        for path, content in key_contents.items():
            parts.append(f"--- {path} ---\n{content}")
        contents_str = "\n\n".join(parts)
    else:
        contents_str = "(no key files found)"

    return _USER_PROMPT_TEMPLATE.format(
        root_name=root_name,
        file_list=file_list_str,
        file_contents=contents_str,
    )


async def detect_project_metadata_async(workspace_root: str) -> dict[str, Any]:
    """
    Ask the LLM to analyse the workspace and return project metadata.
    Falls back to a minimal unknown-project response if the LLM call fails.
    """
    proj_name = Path(workspace_root).name if workspace_root else "Project"

    _fallback: dict[str, Any] = {
        "projectId": f"proj_{abs(hash(workspace_root or ''))}",
        "name": proj_name,
        "framework": "Unknown — click ↻ to re-analyse",
        "language": "Unknown",
        "packageManager": "",
        "installCommand": "",
        "runCommand": "",
        "buildCommand": "",
        "testCommand": "",
        "workspace": workspace_root or "",
        "runnables": [],
    }

    if not workspace_root or not os.path.isdir(workspace_root):
        return _fallback

    try:
        from .adapters.router import ModelRouter
        from .config import config_manager as config

        profile = config.get_active_profile() or {}

        user_prompt = _build_user_prompt(workspace_root)

        router = ModelRouter()
        raw = await router.completion(
            profile,
            [{"role": "user", "content": user_prompt}],
            system_prompt=_SYSTEM_PROMPT,
            is_agent=False,
            task_type="project_detect",
        )

        # Strip markdown fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
        if clean.endswith("```"):
            clean = clean[: clean.rfind("```")]
        clean = clean.strip()

        parsed: dict = json.loads(clean)

        metadata: dict[str, Any] = {
            "projectId": f"proj_{abs(hash(workspace_root))}",
            "name": parsed.get("name") or proj_name,
            "framework": parsed.get("framework") or "Unknown",
            "language": parsed.get("language") or "Unknown",
            "packageManager": parsed.get("packageManager") or "",
            "installCommand": parsed.get("installCommand") or "",
            "runCommand": parsed.get("runCommand") or "",
            "buildCommand": parsed.get("buildCommand") or "",
            "testCommand": parsed.get("testCommand") or "",
            "workspace": workspace_root,
            "runnables": parsed.get("runnables") or [],
        }

        # Persist to .loopix/project.json
        try:
            loopix_dir = Path(workspace_root) / ".loopix"
            loopix_dir.mkdir(exist_ok=True)
            (loopix_dir / "project.json").write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Could not save project.json: {e}")

        return metadata

    except Exception as e:
        logger.error(f"AI project detection failed: {e}")
        return _fallback


# ─── Thin sync shim kept for backwards-compat ─────────────────────────────────
# Callers that cannot await should switch to detect_project_metadata_async.
# This version returns the cached .loopix/project.json if present, otherwise
# a stub that tells the user to click ↻ to trigger the async detection.

def detect_project_metadata(workspace_root: str) -> dict[str, Any]:
    """
    Sync shim: reads the last AI-generated project.json if it exists,
    otherwise returns a stub telling the user to trigger re-analysis.
    Use detect_project_metadata_async() for fresh AI-based detection.
    """
    proj_name = Path(workspace_root).name if workspace_root else "Project"

    if workspace_root and os.path.isdir(workspace_root):
        cached = Path(workspace_root) / ".loopix" / "project.json"
        if cached.is_file():
            try:
                data = json.loads(cached.read_text(encoding="utf-8", errors="ignore"))
                return data
            except Exception:
                pass

    return {
        "projectId": f"proj_{abs(hash(workspace_root or ''))}",
        "name": proj_name,
        "framework": "Click ↻ to analyse",
        "language": "—",
        "packageManager": "",
        "installCommand": "",
        "runCommand": "",
        "buildCommand": "",
        "testCommand": "",
        "workspace": workspace_root or "",
        "runnables": [],
    }
