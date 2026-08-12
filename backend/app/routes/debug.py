import os
import sys
import json
import socket
import logging
import asyncio
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from ..state import workspace_state, session_id_var
from ..processes import global_process_manager

logger = logging.getLogger("devpilot.routes.debug")
router = APIRouter()

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
    Thread-based Debug Adapter Protocol (DAP) client over a TCP socket.

    Uses a dedicated reader thread so that server-initiated events (stopped,
    output, terminated) and request responses can both be received without
    blocking the FastAPI event loop.
    """

    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._seq: int = 1
        self._lock = threading.Lock()
        self._pending: dict = {}      # seq → threading.Event | dict
        self._reader_thread: Optional[threading.Thread] = None
        self.connected: bool = False
        self.port: Optional[int] = None
        self.language: str = "python"

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _encode(self, body: dict) -> bytes:
        payload = json.dumps(body)
        header = f"Content-Length: {len(payload)}\r\n\r\n"
        return (header + payload).encode("utf-8")

    def _read_loop(self) -> None:
        """Background thread: reads all DAP messages and resolves pending events."""
        buf = b""
        while True:
            try:
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\r\n\r\n" in buf:
                    header_part, rest = buf.split(b"\r\n\r\n", 1)
                    content_len = 0
                    for line in header_part.decode("ascii", errors="ignore").split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_len = int(line.split(":", 1)[1].strip())
                            except ValueError:
                                pass
                    if len(rest) < content_len:
                        # Haven't received the full body yet — put bytes back
                        buf = header_part + b"\r\n\r\n" + rest
                        break
                    raw_body = rest[:content_len]
                    buf = rest[content_len:]
                    try:
                        msg = json.loads(raw_body.decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                    # Route to the matching pending request
                    seq = msg.get("request_seq") or msg.get("seq")
                    with self._lock:
                        waiter = self._pending.get(seq)
                    if isinstance(waiter, threading.Event):
                        with self._lock:
                            self._pending[seq] = msg  # replace Event with result
                        waiter.set()
            except Exception:
                break
        self.connected = False

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self, host: str = "127.0.0.1", port: int = 5678,
                timeout: float = 5.0) -> bool:
        self.port = port
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
            self._sock.settimeout(None)  # reader thread uses blocking recv
            self._reader_thread = threading.Thread(
                target=self._read_loop, daemon=True, name="dap-reader"
            )
            self._reader_thread.start()
            # Perform the mandatory DAP initialize handshake
            resp = self.send_request("initialize", {
                "adapterID": "devpilot",
                "clientID": "devpilot",
                "clientName": "DevPilot IDE",
                "linesStartAt1": True,
                "columnsStartAt1": True,
                "pathFormat": "path",
            })
            if resp is not None and resp.get("success", False):
                self.connected = True
                logger.info("DAP: connected to adapter at %s:%d and initialized.", host, port)
            else:
                logger.warning(
                    "DAP: initialize handshake failed (resp=%r). "
                    "connected remains False.", resp
                )
                self.connected = False
            return self.connected
        except Exception as e:
            logger.warning("DAP: connection to %s:%d failed: %s", host, port, e)
            self.connected = False
            return False

    def send_request(self, command: str,
                     args: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Send a DAP request and block up to 3 s for the response."""
        if not self._sock:
            return None
        with self._lock:
            seq = self._seq
            self._seq += 1
            evt = threading.Event()
            self._pending[seq] = evt

        msg = {
            "seq": seq,
            "type": "request",
            "command": command,
            "arguments": args or {},
        }
        try:
            with self._lock:
                self._sock.sendall(self._encode(msg))
        except Exception as e:
            logger.warning("DAP send_request '%s' failed: %s", command, e)
            with self._lock:
                self._pending.pop(seq, None)
            return None

        # Wait up to 3 s for the reader thread to resolve the response
        evt.wait(timeout=3.0)
        with self._lock:
            result = self._pending.pop(seq, None)
        return result if isinstance(result, dict) else None

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
        self.connected = False
        if self._sock:
            try:
                self.send_request("disconnect", {"restart": False, "terminateDebuggee": True})
                self._sock.close()
            except Exception:
                pass
            self._sock = None


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

# ── Debug Session Manager ────────────────────────────────────────────────────
class DebugSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.dap_client = DAPClient()
        self.active_breakpoints: List[Dict[str, Any]] = []
        self.watch_expressions: List[Dict[str, Any]] = []
        self.active_debug_process_id: Optional[str] = None

_debug_sessions: Dict[str, DebugSession] = {}

def get_debug_session() -> DebugSession:
    sid = session_id_var.get() or "default"
    if sid not in _debug_sessions:
        _debug_sessions[sid] = DebugSession(sid)
    return _debug_sessions[sid]

# ── API Routes ───────────────────────────────────────────────────────────────

@router.post("/api/debug/start")
async def start_debug_session():
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")

    debug_session = get_debug_session()
    if debug_session.active_debug_process_id:
        proc = next((p for p in global_process_manager.get_running_processes() if p.id == debug_session.active_debug_process_id), None)
        if proc:
            return {"success": True, "message": "Debugger already running."}

    root = workspace_state.root
    pkg_json = os.path.join(root, "package.json")
    main_py = os.path.join(root, "main.py")
    run_py = os.path.join(root, "run.py")

    dap_port = _find_free_port()
    cmd = []
    is_python = False

    if os.path.exists(main_py):
        cmd = [sys.executable, "-m", "debugpy", "--listen", f"127.0.0.1:{dap_port}", "--wait-for-client", "main.py"]
        is_python = True
    elif os.path.exists(run_py):
        cmd = [sys.executable, "-m", "debugpy", "--listen", f"127.0.0.1:{dap_port}", "--wait-for-client", "run.py"]
        is_python = True
    elif os.path.exists(pkg_json):
        if os.path.exists(os.path.join(root, "node_modules")):
            cmd = ["node", f"--inspect-brk={dap_port}", "node_modules/.bin/vite"]
        else:
            cmd = ["node", f"--inspect={dap_port}", "server.js"]
    else:
        # BUG-011: Return unsupported_configuration instead of dummy sleep process
        return {"success": False, "error": "unsupported_configuration", "message": "No suitable entry point found (main.py, run.py, or package.json)."}

    try:
        proc = await global_process_manager.start_process(cmd, root, "Debug Session")
        debug_session.active_debug_process_id = proc.id

        if is_python:
            import time as _time
            connected = False
            start_poll_time = _time.monotonic()
            while _time.monotonic() - start_poll_time < 5.0:
                if proc.process and proc.process.returncode is not None:
                    logger.warning("Debug process died before DAP connection could be established.")
                    break
                try:
                    connected = debug_session.dap_client.connect("127.0.0.1", dap_port, timeout=1.0)
                    if connected:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.1)

            if connected:
                debug_session.dap_client.send_request("initialize", {
                    "clientID": "devpilot",
                    "clientName": "DevPilot IDE",
                    "adapterID": "python",
                    "linesStartAt1": True,
                    "columnsStartAt1": True,
                    "pathFormat": "path"
                })
                debug_session.dap_client.send_request("attach", {"name": "DevPilot Debug Attach"})
                debug_session.dap_client.sync_breakpoints(root, debug_session.active_breakpoints)
                debug_session.dap_client.send_request("configurationDone", {})

        cmd_str = " ".join(cmd)
        return {"success": True, "command": cmd_str, "dap_port": dap_port, "dap_connected": debug_session.dap_client.connected}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/api/debug/stop")
async def stop_debug_session():
    debug_session = get_debug_session()
    debug_session.dap_client.close()
    if debug_session.active_debug_process_id:
        try:
            await global_process_manager.stop_process(debug_session.active_debug_process_id)
            debug_session.active_debug_process_id = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": True, "message": "Debugger not running."}

@router.get("/api/debug/status")
def get_debug_status():
    debug_session = get_debug_session()
    running = False
    if debug_session.active_debug_process_id:
        proc = next((p for p in global_process_manager.get_running_processes() if p.id == debug_session.active_debug_process_id), None)
        running = proc is not None

    active_frame_desc = "Idle"

    if running:
        if debug_session.dap_client.connected:
            threads_resp = debug_session.dap_client.send_request("threads")
            threads = threads_resp.get("body", {}).get("threads", []) if threads_resp else []
            if threads:
                tid = threads[0]["id"]
                st_resp = debug_session.dap_client.send_request("stackTrace", {"threadId": tid, "startFrame": 0, "levels": 1})
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
        "dap_connected": debug_session.dap_client.connected,
        "breakpoints_count": len(debug_session.active_breakpoints),
        "active_frame": active_frame_desc
    }

@router.get("/api/debug/logs")
def get_debug_logs():
    debug_session = get_debug_session()
    logs = []
    if debug_session.active_debug_process_id:
        procs = global_process_manager.get_all_processes()
        proc = next((p for p in procs if p.id == debug_session.active_debug_process_id), None)
        if proc:
            logs = proc.logs
    stripped_logs = [line.rstrip("\r\n") for line in logs]
    return {"logs": stripped_logs}

@router.get("/api/debug/breakpoints")
def get_breakpoints():
    debug_session = get_debug_session()
    return {"breakpoints": debug_session.active_breakpoints}

@router.post("/api/debug/breakpoints")
def add_breakpoint(bp: BreakpointItem):
    if not workspace_state.root:
        raise HTTPException(status_code=400, detail="No workspace open.")
    
    # Validate workspace confinement
    workspace_path = Path(workspace_state.root).resolve()
    bp_file_path = Path(bp.file)
    if not bp_file_path.is_absolute():
        bp_file_path = Path(workspace_state.root) / bp_file_path
    bp_file_path = bp_file_path.resolve()

    is_inside = False
    try:
        if bp_file_path.is_relative_to(workspace_path):
            is_inside = True
    except ValueError:
        pass
    if not is_inside:
        import os
        if os.name == "nt":
            is_inside = os.path.normcase(str(bp_file_path)).startswith(os.path.normcase(str(workspace_path)))
        else:
            is_inside = str(bp_file_path).startswith(str(workspace_path))
    if not is_inside:
        raise HTTPException(status_code=403, detail="Access Denied: Breakpoint file must be within the workspace root.")

    debug_session = get_debug_session()
    new_id = f"bp_{len(debug_session.active_breakpoints) + 1}"
    item = {
        "id": new_id,
        "file": bp.file,
        "line": bp.line,
        "enabled": bp.enabled if bp.enabled is not None else True
    }
    debug_session.active_breakpoints.append(item)
    if debug_session.dap_client.connected and workspace_state.root:
        debug_session.dap_client.sync_breakpoints(workspace_state.root, debug_session.active_breakpoints)
    return {"success": True, "breakpoint": item}

@router.post("/api/debug/breakpoints/toggle")
def toggle_breakpoint(req: ToggleBreakpointRequest):
    debug_session = get_debug_session()
    for bp in debug_session.active_breakpoints:
        if bp["id"] == req.breakpoint_id:
            bp["enabled"] = not bp.get("enabled", True)
            if debug_session.dap_client.connected and workspace_state.root:
                debug_session.dap_client.sync_breakpoints(workspace_state.root, debug_session.active_breakpoints)
            return {"success": True, "breakpoint": bp}
    return {"success": False, "error": "Breakpoint not found"}

@router.post("/api/debug/evaluate")
def evaluate_expression(req: EvaluateRequest):
    expr = req.expression.strip()
    if not expr:
        return {"result": None}

    debug_session = get_debug_session()
    if debug_session.dap_client.connected:
        eval_resp = debug_session.dap_client.send_request("evaluate", {"expression": expr, "context": "repl"})
        if eval_resp and eval_resp.get("success"):
            res_val = eval_resp.get("body", {}).get("result", "None")
            return {"expression": expr, "result": str(res_val), "status": "success"}
        err_body = eval_resp.get("body", {}) if eval_resp else {}
        return {
            "expression": expr,
            "error": err_body.get("error", {}).get("format", "Evaluation failed in debug adapter."),
            "status": "error"
        }

    raise HTTPException(
        status_code=400,
        detail="No active debug session. Start a debug session first."
    )

@router.get("/api/debug/callstack")
def get_callstack():
    debug_session = get_debug_session()
    running = False
    if debug_session.active_debug_process_id:
        proc = next((p for p in global_process_manager.get_running_processes() if p.id == debug_session.active_debug_process_id), None)
        running = proc is not None

    if not running:
        return {"stack": []}

    if debug_session.dap_client.connected:
        threads_resp = debug_session.dap_client.send_request("threads")
        threads = threads_resp.get("body", {}).get("threads", []) if threads_resp else []
        if threads:
            tid = threads[0]["id"]
            st_resp = debug_session.dap_client.send_request("stackTrace", {"threadId": tid, "startFrame": 0, "levels": 20})
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

    return {"stack": []}

@router.post("/api/debug/step-over")
def debug_step_over():
    debug_session = get_debug_session()
    if debug_session.dap_client.connected:
        debug_session.dap_client.send_request("next", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/step-into")
def debug_step_into():
    debug_session = get_debug_session()
    if debug_session.dap_client.connected:
        debug_session.dap_client.send_request("stepIn", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/step-out")
def debug_step_out():
    debug_session = get_debug_session()
    if debug_session.dap_client.connected:
        debug_session.dap_client.send_request("stepOut", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/continue")
def debug_continue():
    debug_session = get_debug_session()
    if debug_session.dap_client.connected:
        debug_session.dap_client.send_request("continue", {"threadId": 1})
        return {"success": True}
    return {"success": False, "error": "Debugger session not connected to DAP"}

@router.post("/api/debug/pause")
def debug_pause():
    debug_session = get_debug_session()
    if debug_session.dap_client.connected:
        debug_session.dap_client.send_request("pause", {"threadId": 1})
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


@router.get("/api/context/debug")
async def api_context_debug(query: str = "", workspace_root: Optional[str] = None):
    """Context Engine Debug & Provenance inspection endpoint (Step 22)."""
    from ..agent.context_engine import ContextEngine
    root = workspace_root or workspace_state.root_path or os.getcwd()
    engine = ContextEngine.get_instance(root)
    info = await engine.get_debug_info(query)
    return info
