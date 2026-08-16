"""
workspace_symbols.py — Read-only endpoints for symbol extraction and fuzzy file search.

Routes:
  GET /api/workspace/symbols?path=<rel_path>   -> list of symbols in a file
  GET /api/workspace/fuzzy-files?q=<query>     -> fuzzy-ranked list of file paths
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from ..cache import cached
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
        _index = WorkspaceIndex.get_instance(root)
    return _index


@router.get("/api/workspace/symbols")
@cached(ttl=600)
async def get_symbols(
    path: str | None = Query(None, description="Relative file path within workspace"),
    file: str | None = Query(None, description="Alternative relative file path parameter")
):
    """
    Extract code symbols (classes, functions, interfaces, etc.) from a workspace file.
    Returns a list of {name, kind, kindName, line, col} objects.
    """
    target_path = path or file
    if not target_path:
        raise HTTPException(status_code=422, detail="Missing required 'path' or 'file' query parameter.")

    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")

    try:
        import os
        from pathlib import Path
        abs_path = (Path(workspace_state.root) / target_path).resolve()
        root_path = Path(workspace_state.root).resolve()
        is_inside = False
        try:
            if abs_path.is_relative_to(root_path):
                is_inside = True
        except ValueError:
            pass
        if not is_inside:
            if os.name == "nt":
                is_inside = os.path.normcase(str(abs_path)).startswith(os.path.normcase(str(root_path)))
            else:
                is_inside = str(abs_path).startswith(str(root_path))
        if not is_inside:
            raise HTTPException(status_code=403, detail="Access denied: path outside workspace.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        idx = _get_index()
        symbols = idx.get_symbols(target_path)
        return {"symbols": symbols, "path": target_path}
    except Exception as e:
        logger.error(f"Error extracting symbols from {target_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/workspace/global-symbols")
@cached(ttl=600)
async def get_global_symbols(
    q: str = Query("", description="Symbol query string"),
    limit: int = Query(60, ge=1, le=200, description="Maximum results")
):
    """
    Search symbols (functions, classes, interfaces, methods) across all workspace files.
    Returns list of {name, kindName, line, col, file} objects.
    """
    if not workspace_state.root:
        return {"symbols": []}

    try:
        import os
        from pathlib import Path
        root_path = Path(workspace_state.root).resolve()
        exclude_dirs = {".git", "node_modules", "venv", ".venv", ".devpilot", "__pycache__", "dist", "build"}
        valid_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".c", ".cpp", ".rs"}
        
        query_l = q.strip().lower()
        idx = _get_index()
        all_symbols = []

        for root, dirs, file_list in os.walk(str(root_path)):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for f in file_list:
                fp = Path(root) / f
                if fp.suffix.lower() not in valid_exts:
                    continue
                rel_path = fp.relative_to(root_path).as_posix()
                try:
                    file_syms = idx.get_symbols(rel_path)
                    for sym in file_syms:
                        sym_name = sym.get("name", "")
                        if not query_l or query_l in sym_name.lower():
                            all_symbols.append({
                                "name": sym_name,
                                "kind": sym.get("kind", 0),
                                "kindName": sym.get("kindName", "function"),
                                "line": sym.get("line", 1),
                                "col": sym.get("col", 1),
                                "file": rel_path
                            })
                            if len(all_symbols) >= limit:
                                break
                except Exception:
                    continue
                if len(all_symbols) >= limit:
                    break
            if len(all_symbols) >= limit:
                break

        return {"symbols": all_symbols}
    except Exception as e:
        logger.error(f"Error extracting global workspace symbols: {e}")
        return {"symbols": []}


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

