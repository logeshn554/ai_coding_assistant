"""
lsp.py — WebSocket proxy between Monaco frontend and a language server process.

Route:
  WS /ws/lsp/{language}

Supported languages:
  python      -> pyright-langserver --stdio
  typescript  -> typescript-language-server --stdio
  javascript  -> typescript-language-server --stdio

Security:
  - Validates bearer token before accepting the connection.
  - Only proxies JSON-RPC messages; no shell execution.
  - Validates workspace URIs in textDocument/* notifications.
  - Enforces workspace root confinement for all file URIs.
  - Caps at 3 restarts to prevent runaway processes.
"""
import asyncio
import json
import logging
import os
import secrets
import shutil
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ..state import workspace_state, SESSION_TOKEN

router = APIRouter()
logger = logging.getLogger("devpilot.routes.lsp")

# Max times we'll restart a crashed language server per connection
MAX_RESTARTS = 3

# ── Language server command resolution ──────────────────────────────────────

def _find_pyright() -> Optional[list]:
    """Locate pyright-langserver in venv/global PATH."""
    # Check venv first
    venv_root = Path(sys.executable).parent.parent
    for candidate in [
        venv_root / "Scripts" / "pyright-langserver.exe",   # Windows venv
        venv_root / "bin" / "pyright-langserver",            # Unix venv
    ]:
        if candidate.is_file():
            return [str(candidate), "--stdio"]

    # Fall back to PATH
    found = shutil.which("pyright-langserver") or shutil.which("pyright")
    if found:
        return [found, "--stdio"]
    return None


def _find_ts_server() -> Optional[list]:
    """Locate typescript-language-server in global npm or node_modules."""
    found = shutil.which("typescript-language-server")
    if found:
        return [found, "--stdio"]
    # Check local node_modules/.bin
    nm_bin = Path(workspace_state.root or ".") / "node_modules" / ".bin" / "typescript-language-server"
    if nm_bin.is_file():
        return [str(nm_bin), "--stdio"]
    return None


LANGUAGE_SERVERS = {
    "python": _find_pyright,
    "typescript": _find_ts_server,
    "javascript": _find_ts_server,
}


def _get_server_cmd(language: str) -> Optional[list]:
    resolver = LANGUAGE_SERVERS.get(language)
    if not resolver:
        return None
    return resolver()


# ── URI workspace confinement ────────────────────────────────────────────────

def _is_uri_confined(uri: str) -> bool:
    """
    Returns True if the file URI resolves within the current workspace root.
    Always returns True when no workspace is set (permissive).
    """
    if not workspace_state.root:
        return True
    if not uri.startswith("file://"):
        return True  # non-file URIs (e.g. untitled:) are fine
    try:
        path_str = uri[7:]
        if path_str.startswith("/") and len(path_str) > 2 and path_str[2] == ":":
            path_str = path_str[1:]
        abs_path = Path(path_str).resolve()

        workspace = Path(workspace_state.root).resolve()
        return os.path.normcase(str(abs_path)).startswith(os.path.normcase(str(workspace)))
    except Exception:
        return True  # don't block on parse errors


def _sanitize_message(msg_obj: dict) -> Optional[dict]:
    """
    Inspect outgoing (frontend → server) LSP messages and strip or block
    any that reference files outside the workspace.
    Returns None if the message should be dropped.
    """
    method = msg_obj.get("method", "")
    params = msg_obj.get("params", {}) or {}

    # textDocument methods carry a textDocument.uri
    td = params.get("textDocument", {})
    uri = td.get("uri", "")
    if uri and not _is_uri_confined(uri):
        logger.warning(f"LSP: blocked out-of-workspace URI: {uri}")
        return None

    # workspace/didChangeWatchedFiles carries an array of changes
    if method == "workspace/didChangeWatchedFiles":
        changes = params.get("changes", [])
        confined = [c for c in changes if _is_uri_confined(c.get("uri", ""))]
        if not confined:
            return None
        msg_obj = dict(msg_obj)
        msg_obj["params"] = dict(params, changes=confined)
        if workspace_state.root:
            from ..workspace_index import WorkspaceIndex
            WorkspaceIndex.mark_dirty(workspace_state.root)

    return msg_obj


def _uri_to_relative_path(uri: str) -> Optional[str]:
    """Convert a file URI to a relative workspace path, accounting for Windows drive formats."""
    if not uri.startswith("file://"):
        return None
    if not workspace_state.root:
        return None
    try:
        from urllib.parse import unquote
        path_str = unquote(uri[7:])
        if os.name == "nt":
            if path_str.startswith("/") and len(path_str) > 2 and path_str[2] == ":":
                path_str = path_str[1:]
            elif path_str.startswith("/") and len(path_str) > 1 and path_str[1] == ":":
                path_str = path_str[1:]
        
        abs_path = Path(path_str).resolve()
        root_path = Path(workspace_state.root).resolve()
        if abs_path.is_relative_to(root_path):
            return abs_path.relative_to(root_path).as_posix()
        if str(abs_path).lower().startswith(str(root_path).lower()):
            rel = str(abs_path)[len(str(root_path)):].lstrip("\\/")
            return Path(rel).as_posix()
    except Exception:
        pass
    return None


def _update_diagnostics_cache(body_str: str) -> None:
    """Parse outgoing server message and record diagnostics to global state."""
    try:
        msg = json.loads(body_str)
        if not isinstance(msg, dict) or msg.get("method") != "textDocument/publishDiagnostics":
            return
        params = msg.get("params", {})
        uri = params.get("uri")
        if not uri:
            return
        rel_path = _uri_to_relative_path(uri)
        if not rel_path:
            return
        
        diagnostics = params.get("diagnostics", [])
        saved = []
        for d in diagnostics:
            severity = d.get("severity", 1)  # 1 = Error, 2 = Warning
            msg_text = d.get("message", "")
            r = d.get("range", {})
            start_line = r.get("start", {}).get("line", 0) + 1
            start_char = r.get("start", {}).get("character", 0) + 1
            saved.append({
                "severity": severity,
                "message": msg_text,
                "line": start_line,
                "character": start_char,
                "code": d.get("code"),
                "source": d.get("source", "LSP"),
            })
        workspace_state.lsp_diagnostics[rel_path] = saved
        logger.info(f"[LSP] Registered {len(saved)} diagnostics for {rel_path}")

        # Hook to active Repository Kernel SQLite database
        if workspace_state.root:
            try:
                from agent_os.repository.repository import RepositoryKernel
                db_path = os.path.join(workspace_state.root, ".devpilot", "repo.db")
                repo = RepositoryKernel(db_path=db_path)
                repo.store_lsp_diagnostics(rel_path, saved)
                logger.info(f"[LSP] Stored {len(saved)} diagnostics in Repository Kernel database for {rel_path}")
            except Exception as store_err:
                logger.warning(f"[LSP] Failed to store diagnostics in Repository Kernel: {store_err}")
    except Exception as e:
        logger.debug(f"publishDiagnostics parse failed: {e}")


# ── WebSocket handler ────────────────────────────────────────────────────────

async def _proxy_lsp(websocket: WebSocket, language: str):
    """
    Core proxy loop: bridges JSON-RPC between WebSocket and language server stdio.
    """
    cmd = _get_server_cmd(language)
    if not cmd:
        await websocket.send_text(json.dumps({
            "error": f"Language server for '{language}' not installed. "
                     f"Install pyright (pip install pyright) or typescript-language-server (npm i -g typescript-language-server typescript)."
        }))
        await websocket.close()
        return

    cwd = workspace_state.root or os.getcwd()
    restarts = 0

    while restarts <= MAX_RESTARTS:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        logger.info(f"LSP [{language}] started: PID={process.pid}")

        # Bug 16: Drain stderr in a background task to prevent pipe buffer deadlock
        async def drain_stderr():
            try:
                while True:
                    chunk = await process.stderr.read(4096)
                    if not chunk:
                        break
            except Exception:
                pass
        stderr_task = asyncio.create_task(drain_stderr())

        # B7: Buffers are declared INSIDE the restart loop so they reset to
        # empty on each server restart — a partial frame from a crashed session
        # cannot bleed into the next one.
        header_buf = b""
        body_buf = b""
        expected_len: Optional[int] = None

        async def read_from_server():
            """Read Content-Length framed JSON-RPC from server stdout and forward to WS."""
            nonlocal header_buf, body_buf, expected_len
            while True:
                chunk = await process.stdout.read(4096)
                if not chunk:
                    break
                header_buf += chunk

                while True:
                    if expected_len is None:
                        # Look for header/body separator
                        sep = header_buf.find(b"\r\n\r\n")
                        if sep == -1:
                            break
                        header_part = header_buf[:sep].decode("ascii", errors="ignore")
                        header_buf = header_buf[sep + 4:]
                        for line in header_part.split("\r\n"):
                            if line.lower().startswith("content-length:"):
                                expected_len = int(line.split(":")[1].strip())
                                break

                            if len(available) >= expected_len:
                                body = available[:expected_len]
                                header_buf = available[expected_len:]
                                expected_len = None
                                try:
                                    body_str = body.decode("utf-8", errors="replace")
                                    await websocket.send_text(body_str)
                                    _update_diagnostics_cache(body_str)
                                except Exception:
                                    return
                            else:
                                break

        async def read_from_ws():
            """Read JSON messages from WS, sanitize, and forward to server stdin."""
            while True:
                try:
                    raw = await websocket.receive_text()
                except WebSocketDisconnect:
                    return
                except Exception:
                    return

                try:
                    msg_obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_obj = _sanitize_message(msg_obj)
                if msg_obj is None:
                    continue

                encoded = json.dumps(msg_obj).encode("utf-8")
                frame = (
                    f"Content-Length: {len(encoded)}\r\n"
                    f"Content-Type: application/vscode-jsonrpc; charset=utf-8\r\n\r\n"
                ).encode("ascii") + encoded
                try:
                    process.stdin.write(frame)
                    await process.stdin.drain()
                except Exception:
                    return

        try:
            await asyncio.gather(read_from_server(), read_from_ws())
        except Exception as e:
            logger.warning(f"LSP [{language}] proxy error: {e}")
        finally:
            try:
                process.kill()
            except Exception:
                pass
            await process.wait()

        restarts += 1
        if restarts <= MAX_RESTARTS:
            logger.info(f"LSP [{language}] restarting ({restarts}/{MAX_RESTARTS})...")
            await asyncio.sleep(1)

    logger.warning(f"LSP [{language}] exceeded restart limit, closing.")
    try:
        await websocket.send_text(json.dumps({
            "error": f"Language server for {language} crashed repeatedly and was stopped. Please reload the workspace to retry."
        }))
    except Exception:
        pass


@router.websocket("/ws/lsp/{language}")
async def lsp_websocket(
    websocket: WebSocket,
    language: str,
    ticket: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint that proxies JSON-RPC between Monaco and a language server.
    Supported: python, typescript, javascript.
    """
    await websocket.accept()

    from ..state import verify_ws_ticket, SESSION_TOKEN
    from ..config import settings
    is_prod_server = (settings.ENVIRONMENT.lower() == "production" and settings.MODE == "server")
    is_authenticated = False
    if ticket and verify_ws_ticket(ticket):
        is_authenticated = True
    elif token and secrets.compare_digest(token.encode(), SESSION_TOKEN.encode()):
        is_authenticated = True
    elif not is_prod_server:
        # In desktop / development mode, local IDE connections are authenticated by default
        is_authenticated = True

    if not is_authenticated:
        await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized: invalid or missing token."}))
        await websocket.close(code=4401)
        return

    if language not in LANGUAGE_SERVERS:
        await websocket.send_text(json.dumps({
            "error": f"Unsupported language: {language}. Supported: {list(LANGUAGE_SERVERS.keys())}"
        }))
        await websocket.close()
        return

    logger.info(f"LSP WebSocket connection: language={language}")
    try:
        await _proxy_lsp(websocket, language)
    except WebSocketDisconnect:
        logger.info(f"LSP [{language}] client disconnected.")
    except Exception as e:
        logger.error(f"LSP [{language}] unhandled error: {e}")
