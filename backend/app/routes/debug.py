import os
from fastapi import APIRouter, HTTPException
from ..state import workspace_state
from ..processes import global_process_manager

router = APIRouter()

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
    return {"running": running}

@router.get("/api/debug/logs")
def get_debug_logs():
    procs = global_process_manager.get_all_processes()
    logs = procs[-1].logs if procs else []
    stripped_logs = [line.rstrip("\r\n") for line in logs]
    return {"logs": stripped_logs}

@router.post("/api/scan-bugs")
async def api_scan_bugs():
    import asyncio
    from pathlib import Path
    from ..diff_utils import generate_bug_report_async
    
    async def run_scan_and_save():
        try:
            report = await generate_bug_report_async()
            # Resolve db directory similarly to db.py
            user_home = Path.home()
            app_data_dir = user_home / ".gemini" / "antigravity-ide"
            db_dir = app_data_dir / "db"
            db_dir.mkdir(parents=True, exist_ok=True)
            bug_report_path = db_dir / "bug_report.txt"
            bug_report_path.write_text(report, encoding="utf-8")
        except Exception as e:
            print(f"Background bug scanning failed: {e}")
            
    asyncio.create_task(run_scan_and_save())
    return {"success": True, "message": "Background bug scanning initiated on-demand."}
