import asyncio
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..state import workspace_state
from ..utils import run_cmd_async

router = APIRouter()

class TestRunRequest(BaseModel):
    file: str | None = None

def _discover_sync(workspace_root: str) -> list[str]:
    test_files = []
    for root, dirs, files in os.walk(workspace_root):
        # Normalize slashes for comparison
        norm_root = root.replace("\\", "/")
        if any(f"/{d}" in norm_root or norm_root.endswith(d) for d in (".git", "node_modules", "venv", "__pycache__", ".loopix")):
            continue
        for f in files:
            if "test" in f.lower() and os.path.splitext(f)[1].lower() in {".py", ".ts", ".tsx", ".js", ".jsx"}:
                rel_path = os.path.relpath(os.path.join(root, f), workspace_root).replace("\\", "/")
                test_files.append(rel_path)
    return test_files

@router.get("/api/testing/discover")
async def discover_tests():
    if not workspace_state.root:
        return {"tests": []}
    
    # Run blocking os.walk in a background thread to avoid event loop starvation
    test_files = await asyncio.to_thread(_discover_sync, workspace_state.root)
    return {"tests": test_files}

@router.post("/api/testing/run")
async def run_tests(req: TestRunRequest):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    try:
        # Use lists for executing commands securely without spawning a shell (avoids command injection)
        if req.file:
            if req.file.endswith(".py"):
                cmd = ["python", "-m", "unittest", req.file]
            else:
                cmd = ["npm", "test", "--", req.file]
        else:
            pkg_json_exists = await asyncio.to_thread(os.path.exists, os.path.join(workspace_state.root, "package.json"))
            if pkg_json_exists:
                cmd = ["npm", "test"]
            else:
                cmd = ["pytest"]
        out = await run_cmd_async(cmd, workspace_state.root)
        passed = "FAIL" not in out and "ERROR" not in out and "failed" not in out.lower()
        return {"success": True, "passed": passed, "output": out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
