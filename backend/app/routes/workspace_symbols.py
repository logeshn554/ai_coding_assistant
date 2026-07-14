"""
workspace_symbols.py — Read-only endpoints for symbol extraction and fuzzy file search.

Routes:
  GET /api/workspace/symbols?path=<rel_path>   -> list of symbols in a file
  GET /api/workspace/fuzzy-files?q=<query>     -> fuzzy-ranked list of file paths
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from ..state import workspace_state
from ..workspace_index import WorkspaceIndex

router = APIRouter()
logger = logging.getLogger("devpilot.routes.workspace_symbols")

# Module-level index instance (reuses workspace root from state on each request)
_index: WorkspaceIndex | None = None


def _get_index() -> WorkspaceIndex:
    """Return or create a WorkspaceIndex for the current workspace root."""
    global _index
    root = workspace_state.root or ""
    if _index is None or _index.workspace_root != root:
        _index = WorkspaceIndex(root)
    return _index


@router.get("/api/workspace/symbols")
def get_symbols(path: str = Query(..., description="Relative file path within workspace")):
    """
    Extract code symbols (classes, functions, interfaces, etc.) from a workspace file.
    Returns a list of {name, kind, kindName, line, col} objects.
    """
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")

    # Security: ensure path doesn't escape workspace
    try:
        import os
        from pathlib import Path
        abs_path = (Path(workspace_state.root) / path).resolve()
        if not str(abs_path).startswith(str(Path(workspace_state.root).resolve())):
            raise HTTPException(status_code=403, detail="Access denied: path outside workspace.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        idx = _get_index()
        symbols = idx.get_symbols(path)
        return {"symbols": symbols, "path": path}
    except Exception as e:
        logger.error(f"Error extracting symbols from {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/workspace/fuzzy-files")
def fuzzy_files(
    q: str = Query("", description="Fuzzy query string"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results")
):
    """
    Fuzzy-search workspace files by filename/path.
    Returns {files: [relative_path, ...]} ranked by match quality.
    Falls back to full flat list when query is empty.
    """
    if not workspace_state.root:
        return {"files": []}

    try:
        idx = _get_index()
        if q.strip():
            files = idx.fuzzy_search_files(q.strip(), max_results=limit)
        else:
            # No query — return all files (same as /api/files/flat)
            import os
            from pathlib import Path
            exclude_dirs = {".git", "node_modules", "venv", ".devpilot", "__pycache__", "dist", ".pytest_cache"}
            all_files = []
            root_path = Path(workspace_state.root).resolve()
            for root, dirs, file_list in os.walk(str(root_path)):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for f in file_list:
                    fp = Path(root) / f
                    rel = fp.relative_to(root_path).as_posix()
                    all_files.append(rel)
                    if len(all_files) >= limit:
                        break
                if len(all_files) >= limit:
                    break
            files = all_files
        return {"files": files}
    except Exception as e:
        logger.error(f"Error in fuzzy file search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
