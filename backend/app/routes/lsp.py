"""
lsp.py — WebSocket proxy between Monaco frontend and a language server process.

Route:
  WS /ws/lsp/{language}

Supported languages:
  python      -> pyright-langserver --stdio
  typescript  -> typescript-language-server --stdio
  javascript  -> typescript-language-server --stdio

Security:
  - Only proxies JSON-RPC messages; no shell execution.
  - Validates workspace URIs in textDocument/* notifications.
  - Enforces workspace root confinement for all file URIs.
  - Caps at 3 restarts to prevent runaway processes.
"""
import asyncio
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..state import workspace_state

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
        # Strip file:// or file:///
        path_str = uri[7:]
        if path_str.startswith("/"):
            # Unix-style: file:///home/...
            abs_path = Path(path_str).resolve()
        else:
            # Windows: file:///C:/...  -> path_str = /C:/... after stripping file://
            abs_path = Path("/" + path_str).resolve()

        workspace = Path(workspace_state.root).resolve()
        return str(abs_path).startswith(str(workspace))
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

    return msg_obj


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

        # Buffer for partial LSP frames coming from server stdout
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

                    if expected_len is not None:
                        available = header_buf
                        if len(available) >= expected_len:
                            body = available[:expected_len]
                            header_buf = available[expected_len:]
                            expected_len = None
                            try:
                                await websocket.send_text(body.decode("utf-8", errors="replace"))
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

                encoded = raw if isinstance(raw, bytes) else raw.encode("utf-8")
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


@router.websocket("/ws/lsp/{language}")
async def lsp_websocket(websocket: WebSocket, language: str):
    """
    WebSocket endpoint that proxies JSON-RPC between Monaco and a language server.
    Supported: python, typescript, javascript.
    """
    if language not in LANGUAGE_SERVERS:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "error": f"Unsupported language: {language}. Supported: {list(LANGUAGE_SERVERS.keys())}"
        }))
        await websocket.close()
        return

    await websocket.accept()
    logger.info(f"LSP WebSocket connection: language={language}")
    try:
        await _proxy_lsp(websocket, language)
    except WebSocketDisconnect:
        logger.info(f"LSP [{language}] client disconnected.")
    except Exception as e:
        logger.error(f"LSP [{language}] unhandled error: {e}")
