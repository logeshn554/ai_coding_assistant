"""Live Server Tool – launches a static HTTP server to preview HTML files.

Exposes ``open_with_live_server(session, args)`` and ``find_free_port()``
as the agent-facing functions.
"""
from __future__ import annotations

import asyncio
import os
import random
import socket
from typing import Any


def find_free_port(start_port: int = 5500) -> int:
    """Find an available free TCP port using randomized selection to mitigate TOCTOU collisions."""
    ports = list(range(start_port, start_port + 1000))
    random.shuffle(ports)
    for port in ports[:50]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


async def open_with_live_server(session: Any, args: dict[str, Any]) -> str:
    """Launch or reuse a Live Server for an HTML file or static site in the workspace.

    Args:
        session: Active AgentSession providing workspace_root & send_ws_message.
        args:
            path (str, optional): Relative path of the HTML file to serve.
                If omitted, auto-detects ``index.html`` in the workspace.
            port (int, optional): Port to run the server on (default 5500).

    Returns:
        Message containing the Live Server localhost preview URL.
    """
    # Runtime Guard: Check if this is a modern build-based project (e.g. React/Vite/Next)
    pkg_json_path = os.path.join(session.workspace_root, "package.json")
    if os.path.exists(pkg_json_path):
        try:
            import json
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
            scripts = pkg_data.get("scripts", {})
            if "dev" in scripts or "start" in scripts:
                return (
                    "Error: This project has a package.json containing a build/dev script (e.g. 'dev' or 'start'). "
                    "This is a modern framework project, NOT a static HTML site. "
                    "Do NOT use open_with_live_server. Use run_terminal_command with 'npm run dev' or 'npm start' instead to launch the dev server."
                )
        except Exception:
            pass

    rel_path = args.get("path") or args.get("file") or args.get("filepath") or ""

    if not rel_path or not rel_path.endswith((".html", ".htm")):
        found_html = None
        for root, _, files in os.walk(session.workspace_root):
            for file in files:
                if file.endswith((".html", ".htm")):
                    rel_p = os.path.relpath(
                        os.path.join(root, file), session.workspace_root
                    ).replace("\\", "/")
                    if file == "index.html":
                        found_html = rel_p
                        break
                    elif not found_html:
                        found_html = rel_p
            if found_html and found_html.endswith("index.html"):
                break
        rel_path = found_html or "index.html"

    from ..processes import global_process_manager

    # Check if Live Server is already running for this workspace
    running_procs = global_process_manager.get_running_processes()
    for p in running_procs:
        if p.cwd == session.workspace_root and (
            "http.server" in p.command or "Live Server" in (p.name or "")
        ):
            port = p.port or 5500
            live_url = f"http://localhost:{port}/{rel_path}".rstrip("/")
            res_msg = f"Server process already active on port {port} ({live_url})"
            return res_msg

    # Find an available free port
    requested_port = args.get("port") or 5500
    port = find_free_port(requested_port)
    import sys
    command = [sys.executable, "-m", "http.server", str(port)]

    proc = await global_process_manager.start_process(
        command, session.workspace_root, name="Live Server (Static HTML)", session=session
    )
    _monitor_task = asyncio.create_task(session.monitor_and_stream_events(proc))
    _tasks = getattr(session, "_monitor_tasks", None)
    if _tasks is not None:
        _tasks.append(_monitor_task)

    live_url = f"http://localhost:{port}/{rel_path}".rstrip("/")
    res_msg = f"Started server process on port {port} for file '{rel_path}' at {live_url}"
    return res_msg
