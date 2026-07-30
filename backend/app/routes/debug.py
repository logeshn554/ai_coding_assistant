import os
import sys
import json
import socket
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from ..state import workspace_state
from ..processes import global_process_manager

logger = logging.getLogger("devpilot.routes.debug")
router = APIRouter()

# ── Dynamic Breakpoints State ────────────────────────────────────────────────
_active_breakpoints: List[Dict[str, Any]] = [
    {"id": "bp_1", "file": "main.py", "line": 10, "enabled": True}
]
_watch_expressions: List[Dict[str, Any]] = []

class BreakpointItem(BaseModel):
    file: str
    line: int
    enabled: Optional[bool] = True

class EvaluateRequest(BaseModel):
    expression: str

class ToggleBreakpointRequest(BaseModel):
    breakpoint_id: str

# ── DAP Protocol Socket Client ───────────────────────────────────────────────
class DAPClient:
    """
    Lightweight Debug Adapter Protocol (DAP) client over a TCP socket.
    Handles HTTP-header framed JSON-RPC messages (Content-Length: ...\r\n\r\n{...}).
    """
    def __init__(self):
        self.sock: Optional[socket.socket] = None
        self.seq = 1
        self.connected = False
        self.port: Optional[int] = None
        self.language: str = "python"

    def connect(self, host: str = "127.0.0.1", port: int = 5678, timeout: float = 3.0) -> bool:
        self.port = port
        try:
            self.sock = socket.create_connection((host, port), timeout=timeout)
            self.sock.settimeout(2.0)
            self.connected = True
            logger.info(f"DAP: Connected to adapter at {host}:{port}")
            return True
        except Exception as e:
            logger.warning(f"DAP: Failed connection to {host}:{port}: {e}")
            self.connected = False
            return False

    def send_request(self, command: str, args: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.sock or not self.connected:
            return None
        current_seq = self.seq
        self.seq += 1
        payload = {
            "seq": current_seq,
            "type": "request",
            "command": command,
            "arguments": args or {}
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(data_bytes)}\r\n\r\n".encode("ascii")
        try:
            self.sock.sendall(header + data_bytes)
            return self._read_response()
        except Exception as e:
            logger.warning(f"DAP request '{command}' failed: {e}")
            return None

    def _read_response(self, timeout_secs: float = 2.0) -> Optional[Dict[str, Any]]:
        if not self.sock:
            return None
        self.sock.settimeout(timeout_secs)
        buf = b""
        try:
            while b"\r\n\r\n" not in buf:
                chunk = self.sock.recv(2048)
                if not chunk:
                    return None
                buf += chunk

            header_part, body_part = buf.split(b"\r\n\r\n", 1)
            content_len = 0
            for line in header_part.decode("ascii", errors="ignore").split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_len = int(line.split(":")[1].strip())
                    break

            while len(body_part) < content_len:
                chunk = self.sock.recv(2048)
                if not chunk:
                    break
                body_part += chunk

            raw_json = body_part[:content_len].decode("utf-8", errors="replace")
            return json.loads(raw_json)
        except Exception:
            return None

    def sync_breakpoints(self, workspace_root: str, breakpoints: List[Dict[str, Any]]):
        """Send DAP setBreakpoints requests grouped by file."""
        if not self.connected:
            return
        files_map: Dict[str, List[int]] = {}
        for bp in breakpoints:
            if bp.get("enabled", True):
                abs_p = str(Path(workspace_root) / bp["file"]) if not os.path.isabs(bp["file"]) else bp["file"]
                files_map.setdefault(abs_p, []).append(bp["line"])

        for filepath, lines in files_map.items():
            self.send_request("setBreakpoints", {
                "source": {"path": filepath},
                "breakpoints": [{"line": l} for l in lines]
            })

    def close(self):
        if self.sock:
            try:
                self.send_request("disconnect", {"restart": False, "terminateDebuggee": True})
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.connected = False

# Global DAP client instance
dap_client = DAPClient()

def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

# ── API Routes ───────────────────────────────────────────────────────────────

@router.post("/api/debug/start")
async def start_debug_session():
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")

    running_procs = global_process_manager.get_running_processes()
    if running_procs:
        return {"success": True, "message": "Debugger already running."}

    root = workspace_state.root
    pkg_json = os.path.join(root, "package.json")
    main_py = os.path.join(root, "main.py")
    run_py = os.path.join(root, "run.py")

    dap_port = _find_free_port()
    cmd = ""
    is_python = False

    if os.path.exists(main_py):
        cmd = f"{sys.executable} -m debugpy --listen 127.0.0.1:{dap_port} --wait-for-client main.py"
        is_python = True
    elif os.path.exists(run_py):
        cmd = f"{sys.executable} -m debugpy --listen 127.0.0.1:{dap_port} --wait-for-client run.py"
        is_python = True
    elif os.path.exists(pkg_json):
        cmd = f"node --inspect-brk={dap_port} node_modules/.bin/vite" if os.path.exists(os.path.join(root, "node_modules")) else f"node --inspect={dap_port} server.js"
    else:
        cmd = f"{sys.executable} -m debugpy --listen 127.0.0.1:{dap_port} --wait-for-client -c \"import time; print('Debugging started...'); time.sleep(300)\""
        is_python = True

    try:
        proc = await global_process_manager.start_process(cmd, root, "Debug Session")

        if is_python:
            await asyncio.sleep(0.8)
            connected = dap_client.connect("127.0.0.1", dap_port, timeout=4.0)
            if connected:
                dap_client.send_request("initialize", {
                    "clientID": "devpilot",
                    "clientName": "DevPilot IDE",
                    "adapterID": "python",
                    "linesStartAt1": True,
                    "columnsStartAt1": True,
                    "pathFormat": "path"
                })
                dap_client.send_request("attach", {"name": "DevPilot Debug Attach"})
                dap_client.sync_breakpoints(root, _active_breakpoints)
                dap_client.send_request("configurationDone", {})

        return {"success": True, "command": cmd, "dap_port": dap_port, "dap_connected": dap_client.connected}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/debug/stop")
async def stop_debug_session():
    dap_client.close()
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
    active_frame_desc = "Idle"

    if running:
        if dap_client.connected:
            threads_resp = dap_client.send_request("threads")
            threads = threads_resp.get("body", {}).get("threads", []) if threads_resp else []
            if threads:
                tid = threads[0]["id"]
                st_resp = dap_client.send_request("stackTrace", {"threadId": tid, "startFrame": 0, "levels": 1})
                frames = st_resp.get("body", {}).get("stackFrames", []) if st_resp else []
                if frames:
                    top = frames[0]
                    active_frame_desc = f"{top.get('name', 'main')}: L{top.get('line', 1)}"
                else:
                    active_frame_desc = "Session Active (Running)"
            else:
                active_frame_desc = "Session Active (Running)"
        else:
            active_frame_desc = "Process Running (Standalone)"

    return {
        "running": running,
        "dap_connected": dap_client.connected,
        "breakpoints_count": len(_active_breakpoints),
        "active_frame": active_frame_desc
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
    if dap_client.connected and workspace_state.root:
        dap_client.sync_breakpoints(workspace_state.root, _active_breakpoints)
    return {"success": True, "breakpoint": item}

@router.post("/api/debug/breakpoints/toggle")
def toggle_breakpoint(req: ToggleBreakpointRequest):
    for bp in _active_breakpoints:
        if bp["id"] == req.breakpoint_id:
            bp["enabled"] = not bp.get("enabled", True)
            if dap_client.connected and workspace_state.root:
                dap_client.sync_breakpoints(workspace_state.root, _active_breakpoints)
            return {"success": True, "breakpoint": bp}
    return {"success": False, "error": "Breakpoint not found"}

@router.post("/api/debug/evaluate")
def evaluate_expression(req: EvaluateRequest):
    expr = req.expression.strip()
    if not expr:
        return {"result": None}

    # S2: Only evaluate via a connected DAP adapter — never fall back to
    # Python eval() with user-supplied expressions, which would allow RCE
    # (e.g. os.system("rm -rf /"), open("/etc/passwd").read(), etc.).
    if dap_client.connected:
        eval_resp = dap_client.send_request("evaluate", {"expression": expr, "context": "repl"})
        if eval_resp and eval_resp.get("success"):
            res_val = eval_resp.get("body", {}).get("result", "None")
            return {"expression": expr, "result": str(res_val), "status": "success"}
        # DAP responded but evaluation failed (e.g. NameError in the debuggee)
        err_body = eval_resp.get("body", {}) if eval_resp else {}
        return {
            "expression": expr,
            "error": err_body.get("error", {}).get("format", "Evaluation failed in debug adapter."),
            "status": "error"
        }

    # No active debug session — safe refusal
    return {
        "expression": expr,
        "error": "No active debug session. Start a debug session first.",
        "status": "no_session"
    }

@router.get("/api/debug/callstack")
def get_callstack():
    running = len(global_process_manager.get_running_processes()) > 0
    if not running:
        return {"stack": []}

    if dap_client.connected:
        threads_resp = dap_client.send_request("threads")
        threads = threads_resp.get("body", {}).get("threads", []) if threads_resp else []
        if threads:
            tid = threads[0]["id"]
            st_resp = dap_client.send_request("stackTrace", {"threadId": tid, "startFrame": 0, "levels": 20})
            raw_frames = st_resp.get("body", {}).get("stackFrames", []) if st_resp else []
            formatted = []
            for f in raw_frames:
                formatted.append({
                    "id": f.get("id", 1),
                    "name": f.get("name", "frame"),
                    "file": f.get("source", {}).get("path") or f.get("source", {}).get("name", "unknown"),
                    "line": f.get("line", 1)
                })
            if formatted:
                return {"stack": formatted}

    return {
        "stack": [
            {"id": 1, "name": "main", "file": "main.py", "line": 10}
        ]
    }

# ── Debug Execution Control Endpoints ────────────────────────────────────────

@router.post("/api/debug/step-over")
def debug_step_over():
    if dap_client.connected:
        dap_client.send_request("next", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/step-into")
def debug_step_into():
    if dap_client.connected:
        dap_client.send_request("stepIn", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/step-out")
def debug_step_out():
    if dap_client.connected:
        dap_client.send_request("stepOut", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/continue")
def debug_continue():
    if dap_client.connected:
        dap_client.send_request("continue", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/pause")
def debug_pause():
    if dap_client.connected:
        dap_client.send_request("pause", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/scan-bugs")
async def api_scan_bugs():
    from ..tools.scan_for_bugs import generate_bug_report_async

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
