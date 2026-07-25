import os
import shutil
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..state import workspace_state, logger
from ..utils import run_cmd_async
from ..files import safe_path

router = APIRouter()

class GitActionRequest(BaseModel):
    action: str
    path: Optional[str] = None
    message: Optional[str] = None
    branch: Optional[str] = None

@router.get("/api/git/status")
async def get_git_status():
    if not workspace_state.root:
        return {"branch": "", "files": []}
    try:
        branch = await run_cmd_async("git rev-parse --abbrev-ref HEAD", workspace_state.root)
        if "fatal:" in branch:
            return {"branch": "Not a Git Repository", "files": []}
        branch = branch.strip()
        status_out = await run_cmd_async("git status --porcelain", workspace_state.root)
        if "fatal:" in status_out:
            return {"branch": "Not a Git Repository", "files": []}
        files = []
        for line in status_out.splitlines():
            if len(line) > 3:
                xy = line[:2]
                status = xy.strip()
                path = line[3:].strip().strip('"').strip("'")
                staged = xy[0] not in (' ', '?')
                files.append({"path": path, "status": status, "staged": staged})
        return {"branch": branch, "files": files}
    except Exception as e:
        return {"branch": "unknown", "files": [], "error": str(e)}

@router.get("/api/git/branches")
async def get_git_branches():
    if not workspace_state.root:
        return {"branches": []}
    try:
        out = await run_cmd_async("git branch -a", workspace_state.root)
        if "fatal:" in out:
            return {"branches": []}
        branches = [line.replace("*", "").strip() for line in out.splitlines() if line.strip()]
        return {"branches": branches}
    except Exception as e:
        return {"branches": [], "error": str(e)}

@router.get("/api/git/history")
async def get_git_history():
    if not workspace_state.root:
        return {"history": []}
    try:
        out = await run_cmd_async('git log -n 15 --pretty=format:"%h - %an, %ar : %s"', workspace_state.root)
        if "fatal:" in out:
            return {"history": []}
        history = [line.strip() for line in out.splitlines() if line.strip()]
        return {"history": history}
    except Exception as e:
        return {"history": [], "error": str(e)}

@router.get("/api/git/diff")
async def get_git_diff(
    path: Optional[str] = Query(default=None),
    staged: Optional[str] = Query(default=None),
):
    """
    GET /api/git/diff?path=<file>   -> unstaged diff for a single file
    GET /api/git/diff?staged=true   -> all staged changes (AI commit message)
    """
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        if staged and staged.lower() == "true":
            diff_out = await run_cmd_async("git diff --cached", workspace_state.root)
            if "fatal:" in diff_out:
                return {"diff": ""}
            return {"diff": diff_out}
        elif path:
            diff_out = await run_cmd_async(["git", "diff", "--", path], workspace_state.root)
            if not diff_out.strip():
                diff_out = await run_cmd_async(["git", "diff", "--cached", "--", path], workspace_state.root)
            return {"diff": diff_out}
        else:
            raise HTTPException(status_code=400, detail="Provide ?path=<file> or ?staged=true")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_git_diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/git/changes")
async def get_git_changes():
    if not workspace_state.root:
        return {"files": []}
    try:
        branch = await run_cmd_async("git rev-parse --abbrev-ref HEAD", workspace_state.root)
        if "fatal:" in branch:
            return {"files": []}
        status_out = await run_cmd_async("git status --porcelain", workspace_state.root)
        lines = status_out.splitlines()
        unstaged_numstat = {}
        try:
            numstat_out = await run_cmd_async("git diff --numstat", workspace_state.root)
            for line in numstat_out.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    ins, dels, p = parts[0], parts[1], parts[2]
                    unstaged_numstat[p] = (int(ins) if ins.isdigit() else 0, int(dels) if dels.isdigit() else 0)
        except Exception:
            pass
        staged_numstat = {}
        try:
            numstat_staged_out = await run_cmd_async("git diff --cached --numstat", workspace_state.root)
            for line in numstat_staged_out.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    ins, dels, p = parts[0], parts[1], parts[2]
                    staged_numstat[p] = (int(ins) if ins.isdigit() else 0, int(dels) if dels.isdigit() else 0)
        except Exception:
            pass
        files = []
        for line in lines:
            if len(line) < 3:
                continue
            status = line[:2].strip()
            path = line[3:].strip().strip('"').strip("'")
            insertions = 0
            deletions = 0
            if path in staged_numstat:
                insertions += staged_numstat[path][0]
                deletions += staged_numstat[path][1]
            if path in unstaged_numstat:
                insertions += unstaged_numstat[path][0]
                deletions += unstaged_numstat[path][1]
            if (status == "??" or status == "A") and insertions == 0 and deletions == 0:
                try:
                    full_path = os.path.join(workspace_state.root, path)
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines_count = sum(1 for _ in f)
                        insertions = lines_count
                except Exception:
                    pass
            files.append({"path": path, "name": os.path.basename(path), "status": status,
                          "insertions": insertions, "deletions": deletions})
        return {"files": files}
    except Exception as e:
        logger.error(f"Error in get_git_changes: {e}")
        return {"files": [], "error": str(e)}

@router.post("/api/git/action")
async def perform_git_action(req: GitActionRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        if req.action == "stage":
            await run_cmd_async(["git", "add", req.path], workspace_state.root)
        elif req.action == "unstage":
            await run_cmd_async(["git", "restore", "--staged", req.path], workspace_state.root)
        elif req.action == "commit":
            await run_cmd_async(["git", "commit", "-m", req.message], workspace_state.root)
        elif req.action == "push":
            await run_cmd_async(["git", "push"], workspace_state.root)
        elif req.action == "pull":
            await run_cmd_async(["git", "pull"], workspace_state.root)
        elif req.action == "checkout":
            await run_cmd_async(["git", "checkout", req.branch], workspace_state.root)
        elif req.action == "discard_file":
            status_out = await run_cmd_async(["git", "status", "--porcelain", req.path], workspace_state.root)
            is_untracked = any(l.strip().startswith("??") for l in status_out.splitlines())
            if is_untracked:
                abs_p = safe_path(workspace_state.root, req.path)
                if os.path.exists(abs_p):
                    shutil.rmtree(abs_p) if os.path.isdir(abs_p) else os.remove(abs_p)
            else:
                await run_cmd_async(["git", "restore", "--staged", req.path], workspace_state.root)
                await run_cmd_async(["git", "restore", req.path], workspace_state.root)
        elif req.action == "discard_all":
            await run_cmd_async(["git", "restore", "--staged", "."], workspace_state.root)
            await run_cmd_async(["git", "restore", "."], workspace_state.root)
            await run_cmd_async(["git", "clean", "-fd"], workspace_state.root)
        elif req.action == "accept_file":
            await run_cmd_async(["git", "add", req.path], workspace_state.root)
        elif req.action == "accept_all":
            await run_cmd_async(["git", "add", "."], workspace_state.root)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
