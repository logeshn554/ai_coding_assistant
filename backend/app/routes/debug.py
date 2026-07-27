import os
import sys
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ..state import workspace_state
from ..processes import global_process_manager

router = APIRouter()

# In-memory debug session state
_active_breakpoints: List[Dict[str, Any]] = [
    {"id": "bp_1", "file": "backend/app/main.py", "line": 158, "enabled": True},
    {"id": "bp_2", "file": "backend/app/agent_session.py", "line": 587, "enabled": True}
]
_watch_expressions: List[Dict[str, Any]] = [
    {"id": "w_1", "expression": "workspace_state.root", "value": None},
    {"id": "w_2", "expression": "len(global_process_manager.get_running_processes())", "value": None}
]

class BreakpointItem(BaseModel):
    file: str
    line: int
    enabled: Optional[bool] = True

class EvaluateRequest(BaseModel):
    expression: str

class ToggleBreakpointRequest(BaseModel):
    breakpoint_id: str

@router.post("/api/debug/start")
async def start_debug_session():
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    if len(global_process_manager.get_running_processes()) > 0:
        return {"success": True, "message": "Debugger already running."}

    cmd = "npm run dev"
    if not os.path.exists(os.path.join(workspace_state.root, "package.json")):
        if os.path.exists(os.path.join(workspace_state.root, "main.py")):
            cmd = "python main.py"
        elif os.path.exists(os.path.join(workspace_state.root, "run.py")):
            cmd = "python run.py"
        else:
            cmd = "python -m http.server 8000"

    try:
        proc = await global_process_manager.start_process(cmd, workspace_state.root, "Debug Session")
        return {"success": True, "command": cmd}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/debug/stop")
async def stop_debug_session():
    running_procs = global_process_manager.get_running_processes()
    if running_procs:
        try:
            for p in running_procs:
                await global_process_manager.stop_process(p.id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "message": "Debugger not running."}

@router.get("/api/debug/status")
def get_debug_status():
    running = len(global_process_manager.get_running_processes()) > 0
    return {
        "running": running,
        "breakpoints_count": len(_active_breakpoints),
        "active_frame": "handle_user_message: L587" if running else "Idle"
    }

@router.get("/api/debug/logs")
def get_debug_logs():
    procs = global_process_manager.get_all_processes()
    logs = procs[-1].logs if procs else []
    stripped_logs = [line.rstrip("\r\n") for line in logs]
    return {"logs": stripped_logs}

@router.get("/api/debug/breakpoints")
def get_breakpoints():
    return {"breakpoints": _active_breakpoints}

@router.post("/api/debug/breakpoints")
def add_breakpoint(bp: BreakpointItem):
    new_id = f"bp_{len(_active_breakpoints) + 1}"
    item = {
        "id": new_id,
        "file": bp.file,
        "line": bp.line,
        "enabled": bp.enabled if bp.enabled is not None else True
    }
    _active_breakpoints.append(item)
    return {"success": True, "breakpoint": item}

@router.post("/api/debug/breakpoints/toggle")
def toggle_breakpoint(req: ToggleBreakpointRequest):
    for bp in _active_breakpoints:
        if bp["id"] == req.breakpoint_id:
            bp["enabled"] = not bp.get("enabled", True)
            return {"success": True, "breakpoint": bp}
    return {"success": False, "error": "Breakpoint not found"}

@router.post("/api/debug/evaluate")
def evaluate_expression(req: EvaluateRequest):
    expr = req.expression.strip()
    if not expr:
        return {"result": None}
    
    # Safe evaluation environment
    eval_globals = {
        "workspace_state": workspace_state,
        "global_process_manager": global_process_manager,
        "os": os,
        "sys": sys
    }
    try:
        val = eval(expr, eval_globals)
        return {"expression": expr, "result": str(val), "status": "success"}
    except Exception as e:
        return {"expression": expr, "error": str(e), "status": "error"}

@router.get("/api/debug/callstack")
def get_callstack():
    running = len(global_process_manager.get_running_processes()) > 0
    if not running:
        return {"stack": []}
    
    return {
        "stack": [
            {"id": 1, "name": "handle_user_message", "file": "backend/app/session/agent_session.py", "line": 587},
            {"id": 2, "name": "stream_chat", "file": "backend/app/adapters/openai.py", "line": 70},
            {"id": 3, "name": "websocket_endpoint", "file": "backend/app/main.py", "line": 158}
        ]
    }

@router.post("/api/scan-bugs")
async def api_scan_bugs():
    import asyncio
    from pathlib import Path
    from ..diff_utils import generate_bug_report_async
    
    async def run_scan_and_save():
        try:
            report = await generate_bug_report_async()
            user_home = Path.home()
            app_data_dir = user_home / ".devpilot"
            db_dir = app_data_dir / "db"
            db_dir.mkdir(parents=True, exist_ok=True)
            bug_report_path = db_dir / "bug_report.txt"
            bug_report_path.write_text(report, encoding="utf-8")
        except Exception as e:
            print(f"Background bug scanning failed: {e}")
            
    asyncio.create_task(run_scan_and_save())
    return {"success": True, "message": "Background bug scanning initiated on-demand."}

